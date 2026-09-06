"""
Central Music Archive — isolated, non-blocking background archival of YouTube
audio tracks to a shared central MongoDB + Telegram storage channel.

CRITICAL INVARIANTS
-------------------
1. Never blocks playback. All archive work runs in background asyncio tasks.
2. Audio only. Video / MP4 is never archived (caller filters this).
3. Completely separate from the existing bot's MongoDB. Uses its own
   database (default: ``music_archive``) inside the cluster pointed to by
   ``CENTRAL_MONGO_DB_URI``.
4. Three layers of deduplication
     a. MongoDB unique index on (video_id, media_type) — cross-process /
        cross-bot safety.
     b. In-process task map keyed by (video_id, "audio") — concurrent
        request safety inside this process.
     c. Pre-upload Mongo lookup — skip upload entirely if already archived.
5. File lifecycle (DETERMINISTIC — no polling, no timeout):
   The archive trigger fires INSIDE ``put_queue()``, AFTER
   ``autoclean.append(file)`` has already established playback ownership.
   The archive adds its own ref (count >= 2), uploads, and releases its
   ref via ``auto_clean()`` in ``finally``. ``auto_clean`` deletes the
   file only when count reaches 0 — which requires BOTH the archive's
   ref AND playback's ref to have been released. No timing assumptions.
6. Failure isolation: EVERY entry point is wrapped in try/except. Archive
   errors are logged and swallowed. Playback is never affected.
7. Mongo failure policy: if the central Mongo lookup FAILS (network error,
   timeout, connection drop), the archive DOES NOT UPLOAD. A Mongo error
   is never treated as equivalent to "song not found". This prevents
   duplicate Telegram uploads during Mongo outages.
8. Orphan handling: if a Telegram upload succeeds but the Mongo insert
   fails, the worker re-queries Mongo:
     - Record points to our upload → keep (write went through).
     - Record points to another upload → delete our orphan.
     - Mongo healthy, no record → insert confirmed failed → delete orphan.
     - Mongo unreachable → keep upload (can't determine). In-process
       dedup prevents repeated uploads in this process.

This module is intentionally self-contained. The only edits to the rest of
the codebase are:
  - ``config.py``: read the new env vars.
  - ``sample.env``: document them.
  - ``utils/stream/queue.py``: trigger call inside ``put_queue()`` AFTER
    ``autoclean.append(file)`` — this is the deterministic ownership point.
  - ``platforms/Youtube.py``: reverted to original (no archive trigger).
  - ``__main__.py``: optional best-effort init call at startup.
  - ``utils/stream/autoclear.py``: untouched (we reuse ``auto_clean`` as-is).
"""

import asyncio
import os
from datetime import datetime, timezone
from typing import Optional

from config import (
    autoclean,
    CENTRAL_ARCHIVE_SOURCE_BOT,
    CENTRAL_MONGO_DB_URI,
    CENTRAL_MUSIC_ARCHIVE_COLL,
    CENTRAL_MUSIC_ARCHIVE_DB,
    CENTRAL_MUSIC_ARCHIVE_ENABLED,
    STORAGE_CHANNEL_ID,
)

from SWAGGYMUSIC.logging import LOGGER


# ---------------------------------------------------------------------------
# Sentinel for Mongo query errors
# ---------------------------------------------------------------------------

class _MongoError:
    """Sentinel returned by ``_lookup_existing`` when the Mongo query
    FAILED (network error, timeout, connection drop). This is distinct
    from ``None`` which means "query succeeded, no record found".

    The archive worker uses this distinction to decide whether to upload:
      - ``None`` (confirmed not found) → safe to upload.
      - ``_MongoError`` (query failed) → DO NOT upload (prevents
        duplicate uploads during Mongo outages).
      - ``dict`` (record found) → skip upload (already archived).
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __repr__(self):
        return "<MongoError>"

    def __bool__(self):
        return False


_MONGO_ERROR = _MongoError()


# ---------------------------------------------------------------------------
# Module-level state
# ---------------------------------------------------------------------------

_central_client = None
_central_coll = None
_init_lock: Optional[asyncio.Lock] = None

# --- Retry/cooldown state for central Mongo initialization -----------------
#
# OLD BEHAVIOR (BUG): ``_init_attempted = True`` was set before the first
# init attempt, permanently locking the archive into "disabled" if Mongo
# was temporarily unavailable at startup. The bot required a restart to
# reconnect.
#
# NEW BEHAVIOR: ``_init_attempted`` records the timestamp of the last
# failed init. After a cooldown (``_INIT_RETRY_COOLDOWN_SECONDS``), a new
# init attempt is allowed. ``_init_in_progress`` (derived from the
# async lock being held) ensures only ONE concurrent init attempt runs
# at a time; concurrent archive requests skip safely without waiting.
#
# State transitions:
#   _central_coll is not None  → CONNECTED (use normally)
#   _central_coll is None      → check cooldown:
#     (now - _init_attempted) < cooldown  → skip (recently failed)
#     (now - _init_attempted) >= cooldown  → allow ONE retry (under lock)
#
# This is intentionally simple. No exponential backoff, no jitter — just
# a fixed cooldown. The archive is secondary; playback never waits.
_init_attempted: float = 0.0  # monotonic timestamp of last FAILED init (0 = never)
_INIT_RETRY_COOLDOWN_SECONDS: float = 30.0  # controlled retry interval

# In-process dedup: maps (video_id, "audio") -> running asyncio.Task.
_active_uploads: dict = {}

# Strong references to pending background tasks so CPython's GC doesn't
# reap them while they're still running.
_pending_tasks: set = set()


def _get_init_lock() -> asyncio.Lock:
    global _init_lock
    if _init_lock is None:
        _init_lock = asyncio.Lock()
    return _init_lock


# ---------------------------------------------------------------------------
# Config / enablement
# ---------------------------------------------------------------------------

def is_archive_enabled() -> bool:
    if not CENTRAL_MUSIC_ARCHIVE_ENABLED:
        return False
    if not CENTRAL_MONGO_DB_URI:
        return False
    if not STORAGE_CHANNEL_ID:
        return False
    return True


# ---------------------------------------------------------------------------
# Central Mongo initialization
# ---------------------------------------------------------------------------

async def _ensure_initialized():
    """Lazy-init the central Mongo client and create the unique dedup index.

    Implements a controlled retry/cooldown so that a TEMPORARY Mongo
    outage at startup does NOT permanently disable the archive. The bot
    does NOT require a restart to reconnect.

    Concurrency model
    -----------------
    Uses an ``asyncio.Lock`` so that only ONE init attempt runs at a
    time. Concurrent archive requests that arrive while an init is in
    progress do NOT wait — they return ``None`` immediately (skip
    archive safely). This guarantees playback is never blocked.

    Cooldown model
    --------------
    If init fails, ``_init_attempted`` is set to the current monotonic
    timestamp. Subsequent calls within ``_INIT_RETRY_COOLDOWN_SECONDS``
    return ``None`` immediately (no Mongo connection attempt). After the
    cooldown expires, the next call is allowed to attempt a retry.

    Returns
    -------
    collection object  — init succeeded (or was already done).
    None                — init not yet attempted, in cooldown, in
                          progress (concurrent), or failed on this
                          retry. The archive worker treats None as
                          "Mongo unavailable" → no Telegram upload.
    """
    global _central_client, _central_coll, _init_attempted

    # Fast path: already connected.
    if _central_coll is not None:
        return _central_coll

    # Cooldown check: if we recently failed, skip immediately without
    # touching the lock or the network. This prevents 100 song requests
    # from creating 100 Mongo connection attempts.
    now = asyncio.get_event_loop().time()
    if _init_attempted > 0:
        elapsed = now - _init_attempted
        if elapsed < _INIT_RETRY_COOLDOWN_SECONDS:
            return None  # in cooldown — skip safely

    # Try to acquire the init lock NON-BLOCKING. If another init is
    # already running, we skip (do NOT wait) — playback must never block.
    lock = _get_init_lock()
    if lock.locked():
        # Another init is in progress. Skip this request safely.
        return None

    async with lock:
        # Re-check inside the lock (another coroutine may have completed
        # init while we were waiting to acquire).
        if _central_coll is not None:
            return _central_coll

        # Re-check cooldown inside the lock (another coroutine may have
        # just failed init and updated _init_attempted).
        now = asyncio.get_event_loop().time()
        if _init_attempted > 0:
            elapsed = now - _init_attempted
            if elapsed < _INIT_RETRY_COOLDOWN_SECONDS:
                return None

        # Mark that an attempt is starting. We set _init_attempted BEFORE
        # the try block so that if the attempt itself hangs or crashes
        # the process, the cooldown still applies to future calls.
        # (On success, _central_coll is set and _init_attempted is
        # irrelevant — the fast path returns immediately.)
        _init_attempted = now

        try:
            from motor.motor_asyncio import AsyncIOMotorClient

            client = AsyncIOMotorClient(
                CENTRAL_MONGO_DB_URI,
                serverSelectionTimeoutMS=5000,
            )
            await client.admin.command("ping")

            db = client[CENTRAL_MUSIC_ARCHIVE_DB]
            coll = db[CENTRAL_MUSIC_ARCHIVE_COLL]

            await coll.create_index(
                [("video_id", 1), ("media_type", 1)],
                unique=True,
                name="uniq_video_id_media_type",
            )

            _central_client = client
            _central_coll = coll
            LOGGER(__name__).info(
                "[CENTRAL_ARCHIVE] initialized — "
                f"db={CENTRAL_MUSIC_ARCHIVE_DB} "
                f"coll={CENTRAL_MUSIC_ARCHIVE_COLL}"
            )
            return _central_coll
        except Exception as e:
            # Init failed. _init_attempted is already set to `now` (above),
            # so the cooldown applies. The next retry is allowed after
            # _INIT_RETRY_COOLDOWN_SECONDS. NO permanent lock.
            #
            # Resource cleanup: if a local ``client`` was constructed before
            # the failure (ping / index creation raised), close it
            # best-effort so repeated failed inits don't leak Motor
            # connection resources. ``client.close()`` is synchronous and
            # non-blocking per Motor docs. If the local ``client`` variable
            # was never assigned (e.g. ``AsyncIOMotorClient`` itself raised)
            # or if ``close()`` raises, we swallow that — the original init
            # failure is what matters. ``_central_client`` / ``_central_coll``
            # are NOT set (they remain None) so no stale healthy state.
            try:
                client.close()
            except Exception:
                pass
            LOGGER(__name__).warning(
                f"[CENTRAL_ARCHIVE] init failed: "
                f"{type(e).__name__}: {e} — archive temporarily disabled, "
                f"will retry in {_INIT_RETRY_COOLDOWN_SECONDS:.0f}s"
            )
            return None


def _mark_central_unhealthy(reason: str = "") -> None:
    """Invalidate the current central Mongo client/collection and engage
    the cooldown so the next ``_ensure_initialized()`` call will attempt
    a fresh reconnect after ``_INIT_RETRY_COOLDOWN_SECONDS``.

    This is the RUNTIME recovery path — called when a previously-healthy
    Mongo client starts failing on actual operations (find_one /
    insert_one). Without this, the ``_ensure_initialized()`` fast path
    (``if _central_coll is not None: return _central_coll``) would keep
    returning the stale, broken client forever, and the archive would
    never recover without a bot restart.

    Behavior:
      - Discards ``_central_client`` (closes it best-effort — closing is
        synchronous and non-blocking per Motor docs).
      - Sets ``_central_coll = None`` so the fast path stops returning it.
      - Sets ``_init_attempted = now`` so the cooldown engages. The next
        reconnect attempt is allowed after the cooldown, naturally
        triggered by the next archive request (no background thread).

    Concurrency:
      - Safe to call from multiple coroutines simultaneously — all writes
        are simple attribute assignments (GIL-atomic in CPython).
      - Idempotent — calling twice is harmless (second call is a no-op
        since _central_coll is already None).
      - Does NOT block. Does NOT acquire the init lock.
    """
    global _central_client, _central_coll, _init_attempted
    if _central_coll is None and _central_client is None:
        # Already unhealthy — nothing to invalidate. Avoid refreshing
        # the cooldown timestamp so an in-progress cooldown isn't reset
        # by every failing operation.
        return
    try:
        if _central_client is not None:
            try:
                _central_client.close()
            except Exception:
                pass
    finally:
        _central_client = None
        _central_coll = None
        _init_attempted = asyncio.get_event_loop().time()
        LOGGER(__name__).warning(
            f"[CENTRAL_ARCHIVE] central Mongo marked unhealthy"
            f"{f' ({reason})' if reason else ''} — will retry in "
            f"{_INIT_RETRY_COOLDOWN_SECONDS:.0f}s"
        )


# ---------------------------------------------------------------------------
# Local file validation
# ---------------------------------------------------------------------------

def _validate_local_file(file_path: str) -> bool:
    """Lightweight validation: file exists, is a regular file, non-zero
    size, and has an .mp3 extension."""
    try:
        if not file_path:
            return False
        if not os.path.isfile(file_path):
            return False
        if os.path.getsize(file_path) <= 0:
            return False
        if not file_path.lower().endswith(".mp3"):
            return False
        return True
    except Exception:
        return False


# ---------------------------------------------------------------------------
# File protection (deterministic — no polling, no timeout)
# ---------------------------------------------------------------------------

def _protect_file(file_path: str) -> None:
    """Add an archive reference to the shared ``autoclean`` list. This
    works in conjunction with playback's ref (added by ``put_queue()``)
    to ensure the file is not deleted while the archive upload is reading
    it.

    The trigger fires INSIDE ``put_queue()`` AFTER playback's ref is
    already in place, so at this point count >= 1 (playback). We add
    our ref → count >= 2. When the archive releases its ref via
    ``auto_clean()``, count goes to >= 1 (playback's ref remains), so
    the file is NOT deleted. The file is only deleted when playback's
    ref is also released (track ends/skips) and count reaches 0.
    """
    try:
        autoclean.append(file_path)
    except Exception:
        pass


async def _release_file(file_path: str) -> None:
    """Release the archive's reference on the file by calling the existing
    ``auto_clean()`` machinery. This removes one occurrence from
    ``autoclean`` and deletes the file IF AND ONLY IF count reaches 0
    (meaning playback has also released its ref).

    This is fully deterministic:
      - If playback's ref still exists (count >= 2 before release):
        count goes to >= 1. No deletion. File survives for playback. ✓
      - If playback's ref was already released (count == 1 before
        release, meaning the track ended while we were uploading):
        count goes to 0. File is deleted. ✓ (playback no longer needs it)
      - If playback never added a ref (shouldn't happen since the trigger
        is inside put_queue, but defensive): count goes from 1 to 0.
        File is deleted. This is safe because put_queue() already
        returned, meaning the caller has the file path and join_call()
        has been called. PyTgCalls reads the file via a separate
        process/thread, and if it already read it, deletion is fine.
        If it hasn't read it yet... this case is prevented by the
        trigger being inside put_queue (playback's ref ALWAYS exists).
    """
    try:
        from SWAGGYMUSIC.utils.stream.autoclear import auto_clean
        await auto_clean({"file": file_path})
    except Exception as e:
        LOGGER(__name__).warning(
            f"[CENTRAL_ARCHIVE] release_file error for {file_path}: "
            f"{type(e).__name__}: {e}"
        )
        # Fallback: remove our ref directly. This won't delete the file
        # (direct removal doesn't trigger os.remove), but prevents a
        # ref leak. The file may be orphaned (cleaned at restart).
        try:
            autoclean.remove(file_path)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Central Mongo operations
# ---------------------------------------------------------------------------

async def _lookup_existing(video_id: str):
    """Return the existing archive record for (video_id, "audio").

    Returns
    -------
    dict           — record found (already archived).
    None           — query SUCCEEDED, no record found (safe to upload).
    _MONGO_ERROR   — query FAILED (network error, timeout, connection
                     drop). DO NOT upload — prevents duplicate Telegram
                     uploads during Mongo outages.

    On operation failure, the central Mongo state is invalidated via
    ``_mark_central_unhealthy()`` so that the next ``_ensure_initialized()``
    call will attempt a fresh reconnect after the cooldown. This handles
    RUNTIME connection loss (Mongo was healthy at init but drops later).
    """
    coll = await _ensure_initialized()
    if coll is None:
        # Init failed / in cooldown / in progress — treat as Mongo error.
        return _MONGO_ERROR
    try:
        return await coll.find_one(
            {"video_id": video_id, "media_type": "audio"}
        )
    except Exception as e:
        LOGGER(__name__).warning(
            f"[CENTRAL_ARCHIVE] lookup FAILED for video_id={video_id}: "
            f"{type(e).__name__}: {e} — treating as Mongo error "
            f"(NOT as 'not found'). Upload will be skipped."
        )
        # Invalidate the stale client so a fresh reconnect is attempted
        # after the cooldown. Without this, the fast path in
        # _ensure_initialized() would keep returning the broken coll.
        _mark_central_unhealthy(f"lookup failure: {type(e).__name__}")
        return _MONGO_ERROR


async def _insert_record(record: dict):
    """Attempt to insert ``record``.

    Returns
    -------
    "inserted"     — insert succeeded.
    "duplicate"    — DuplicateKeyError; another process/bot won the race.
    "error"        — other failure (timeout, connection drop, uncertain
                     write). Caller must re-query to determine ground truth.

    On non-duplicate operation failure, the central Mongo state is
    invalidated via ``_mark_central_unhealthy()`` so that the next
    ``_ensure_initialized()`` call will attempt a fresh reconnect after
    the cooldown. DuplicateKeyError is NOT a connection failure — it
    means the insert reached Mongo and was rejected by the unique index,
    so the client is still healthy.
    """
    coll = await _ensure_initialized()
    if coll is None:
        return "error"
    try:
        await coll.insert_one(record)
        return "inserted"
    except Exception as e:
        try:
            from pymongo.errors import DuplicateKeyError
        except Exception:
            DuplicateKeyError = ()  # type: ignore
        if isinstance(e, DuplicateKeyError):
            # Duplicate-key is NOT a connection failure — the insert
            # reached Mongo and was rejected by the unique index. The
            # client is still healthy. Do NOT invalidate.
            LOGGER(__name__).info(
                f"[CENTRAL_ARCHIVE] duplicate-key on insert for "
                f"video_id={record.get('video_id')} — another process/bot "
                f"won the race"
            )
            return "duplicate"
        LOGGER(__name__).warning(
            f"[CENTRAL_ARCHIVE] insert FAILED for "
            f"video_id={record.get('video_id')}: "
            f"{type(e).__name__}: {e}"
        )
        # Invalidate the stale client so a fresh reconnect is attempted
        # after the cooldown. This is the runtime-recovery path for
        # connection drops / timeouts during insert.
        _mark_central_unhealthy(f"insert failure: {type(e).__name__}")
        return "error"


# ---------------------------------------------------------------------------
# Background archive worker
# ---------------------------------------------------------------------------

async def _archive_worker(
    file_path: str,
    video_id: str,
    title: Optional[str],
    duration: Optional[int],
    thumbnail: Optional[str],
) -> None:
    """Background worker. Protects the file, uploads to Telegram, inserts
    the Mongo record, and handles every race condition. All exceptions are
    caught and logged. NEVER re-raises into the caller (except
    CancelledError for clean shutdown)."""
    LOGGER(__name__).info(
        f"[CENTRAL_ARCHIVE] worker started — video_id={video_id} "
        f"file={file_path}"
    )
    protected = False
    sent_message = None
    try:
        # 0. (Removed) The old check ``if _central_coll is None and
        #    _init_attempted`` was a PERMANENT block (the bug fixed in
        #    this pass). Now _ensure_initialized() handles cooldown/retry
        #    transparently — _lookup_existing() calls it and returns
        #    _MONGO_ERROR if Mongo is unavailable (in cooldown, init in
        #    progress, or init failed on this retry). The worker's step 2
        #    handles _MONGO_ERROR correctly (skip upload). No permanent
        #    block here.

        # 1. Validate local file.
        if not _validate_local_file(file_path):
            LOGGER(__name__).warning(
                f"[CENTRAL_ARCHIVE] file invalid/missing at worker start: "
                f"{file_path}"
            )
            return

        # 2. Pre-upload Mongo lookup.
        #    This calls _ensure_initialized() internally, which applies
        #    the cooldown/retry logic. Returns:
        #      dict         — record found (already archived)
        #      None         — Mongo healthy, no record (safe to upload)
        #      _MONGO_ERROR — Mongo unavailable (cooldown, init in
        #                     progress, or init failed). DO NOT upload.
        existing = await _lookup_existing(video_id)
        if existing is _MONGO_ERROR:
            # Mongo unavailable (in cooldown, init in progress, or init
            # failed on this retry). Do NOT upload — prevents duplicate
            # uploads during Mongo outages.
            LOGGER(__name__).warning(
                f"[CENTRAL_ARCHIVE] Mongo unavailable for "
                f"video_id={video_id} — skipping upload to prevent "
                f"duplicate channel uploads"
            )
            return
        if existing:
            LOGGER(__name__).info(
                f"[CENTRAL_ARCHIVE] already archived "
                f"(video_id={video_id}) — skipping upload"
            )
            return

        # 2b. Re-check _central_coll (could have been set to None by a
        #     concurrent shutdown between the lookup and here).
        if _central_coll is None:
            LOGGER(__name__).info(
                f"[CENTRAL_ARCHIVE] central Mongo unavailable after lookup "
                f"— skipping upload for video_id={video_id}"
            )
            return

        # 3. Re-validate after the lookup (network round-trip elapsed).
        if not _validate_local_file(file_path):
            LOGGER(__name__).warning(
                f"[CENTRAL_ARCHIVE] file disappeared after lookup: "
                f"{file_path}"
            )
            return

        # 4. Protect the file from autoclean deletion during upload.
        #    At this point, playback's ref already exists (the trigger
        #    fires inside put_queue after autoclean.append). We add our
        #    own ref → count >= 2.
        _protect_file(file_path)
        protected = True

        # 5. Upload to the Telegram storage channel using the MAIN bot.
        from SWAGGYMUSIC import app

        send_kwargs: dict = {
            "chat_id": STORAGE_CHANNEL_ID,
            "audio": file_path,
        }
        if title:
            send_kwargs["title"] = str(title)[:256]
        if duration and isinstance(duration, int) and duration > 0:
            send_kwargs["duration"] = duration

        sent_message = await app.send_audio(**send_kwargs)

        if not (sent_message and getattr(sent_message, "audio", None)):
            LOGGER(__name__).warning(
                f"[CENTRAL_ARCHIVE] send_audio returned no audio object "
                f"for video_id={video_id} — treating as upload failure"
            )
            return

        audio_obj = sent_message.audio
        record = {
            "video_id": video_id,
            "media_type": "audio",
            "file_id": audio_obj.file_id,
            "file_unique_id": audio_obj.file_unique_id,
            "channel_id": STORAGE_CHANNEL_ID,
            "message_id": sent_message.id,
            "title": title,
            "duration": getattr(audio_obj, "duration", None) or duration,
            "thumbnail": thumbnail,
            "source_bot": CENTRAL_ARCHIVE_SOURCE_BOT,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }

        # 6. Insert the Mongo record. Handle all failure modes.
        status = await _insert_record(record)

        if status == "inserted":
            LOGGER(__name__).info(
                f"[CENTRAL_ARCHIVE] archived video_id={video_id} "
                f"msg_id={sent_message.id}"
            )
            return

        if status == "duplicate":
            # Another process/bot won the race. Re-query to find the
            # winning record and decide orphan cleanup.
            existing = await _lookup_existing(video_id)
            await _handle_duplicate_orphan(
                app, video_id, sent_message, existing
            )
            return

        # status == "error" — uncertain write (timeout, connection drop).
        # Re-query to determine ground truth.
        LOGGER(__name__).warning(
            f"[CENTRAL_ARCHIVE] uncertain Mongo write for "
            f"video_id={video_id} — re-querying to decide orphan cleanup"
        )
        existing = await _lookup_existing(video_id)

        if existing is _MONGO_ERROR:
            # Mongo unreachable after the write. Can't determine if the
            # insert went through. KEEP the upload — deleting would risk
            # losing a valid record. In-process dedup prevents repeated
            # uploads in this process. Cross-process safety relies on
            # the unique index.
            LOGGER(__name__).warning(
                f"[CENTRAL_ARCHIVE] Mongo unreachable after uncertain "
                f"write for video_id={video_id} — keeping Telegram "
                f"upload msg_id={sent_message.id} (cannot determine "
                f"ground truth)"
            )
            return

        if existing is None:
            # Mongo is healthy and confirms NO record exists. The insert
            # definitely failed. Our Telegram upload is an orphan —
            # delete it to prevent accumulation.
            LOGGER(__name__).warning(
                f"[CENTRAL_ARCHIVE] Mongo confirms no record after "
                f"uncertain write for video_id={video_id} — insert "
                f"definitely failed. Cleaning orphan upload msg_id="
                f"{sent_message.id}"
            )
            await _safe_delete_message(app, sent_message.id)
            return

        # A Mongo record exists. Does it point to OUR upload?
        await _handle_duplicate_orphan(
            app, video_id, sent_message, existing
        )

    except asyncio.CancelledError:
        LOGGER(__name__).info(
            f"[CENTRAL_ARCHIVE] worker cancelled for video_id={video_id}"
        )
        raise
    except Exception as e:
        LOGGER(__name__).warning(
            f"[CENTRAL_ARCHIVE] worker error for video_id={video_id}: "
            f"{type(e).__name__}: {e}"
        )
    finally:
        # Always release file protection. This is deterministic — no
        # polling, no timeout. auto_clean removes our ref and deletes
        # the file only if count == 0 (playback's ref also released).
        if protected:
            await _release_file(file_path)


async def _handle_duplicate_orphan(
    app,
    video_id: str,
    sent_message,
    existing,
) -> None:
    """Decide what to do with our Telegram upload when a Mongo record
    already exists (either from a duplicate-key insert or a re-query).

    - existing is _MONGO_ERROR → keep upload (can't determine).
    - existing points to OUR upload → keep (we are canonical).
    - existing points to ANOTHER upload → delete our orphan.
    - existing is None → no record found (shouldn't happen here, but
      keep upload as conservative fallback).
    """
    if existing is _MONGO_ERROR:
        LOGGER(__name__).warning(
            f"[CENTRAL_ARCHIVE] Mongo unreachable during orphan check "
            f"for video_id={video_id} — keeping Telegram upload "
            f"msg_id={sent_message.id}"
        )
        return

    if existing is None:
        LOGGER(__name__).warning(
            f"[CENTRAL_ARCHIVE] no record found during orphan check "
            f"for video_id={video_id} — keeping Telegram upload "
            f"msg_id={sent_message.id}"
        )
        return

    if (
        existing.get("channel_id") == STORAGE_CHANNEL_ID
        and existing.get("message_id") == sent_message.id
    ):
        # Our upload is the canonical record. Keep it.
        LOGGER(__name__).info(
            f"[CENTRAL_ARCHIVE] our upload video_id={video_id} "
            f"msg_id={sent_message.id} is canonical — keeping"
        )
        return

    # The existing record points to a DIFFERENT upload. Our upload is
    # an orphan — safe to delete.
    LOGGER(__name__).info(
        f"[CENTRAL_ARCHIVE] another record won for video_id={video_id} "
        f"— cleaning orphan upload msg_id={sent_message.id}"
    )
    await _safe_delete_message(app, sent_message.id)


async def _safe_delete_message(app, message_id: int) -> None:
    """Delete a Telegram message from the storage channel. Logs but
    never raises."""
    try:
        await app.delete_messages(
            chat_id=STORAGE_CHANNEL_ID,
            message_ids=message_id,
        )
    except Exception as e:
        LOGGER(__name__).warning(
            f"[CENTRAL_ARCHIVE] failed to delete message {message_id}: "
            f"{type(e).__name__}: {e}"
        )


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def archive_youtube_audio(
    file_path: str,
    video_id: str,
    title: Optional[str] = None,
    duration: Optional[int] = None,
    thumbnail: Optional[str] = None,
) -> None:
    """Non-blocking entry point. Schedules a background archive task.

    MUST be called AFTER playback ownership has been established (i.e.,
    after ``put_queue()`` has called ``autoclean.append(file)``). This
    is the deterministic ownership guarantee — no polling or timeout
    needed.

    Returns immediately. Never raises.
    """
    try:
        if not is_archive_enabled():
            return
        if not video_id or not isinstance(video_id, str) or len(video_id) < 3:
            return
        if not _validate_local_file(file_path):
            return

        key = (video_id, "audio")
        existing_task = _active_uploads.get(key)
        if existing_task is not None and not existing_task.done():
            return

        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            return

        task = loop.create_task(
            _archive_worker(file_path, video_id, title, duration, thumbnail)
        )
        _active_uploads[key] = task
        _pending_tasks.add(task)

        def _cleanup(t, k=key):
            _pending_tasks.discard(t)
            cur = _active_uploads.get(k)
            if cur is t:
                _active_uploads.pop(k, None)

        task.add_done_callback(_cleanup)
    except Exception as e:
        LOGGER(__name__).warning(
            f"[CENTRAL_ARCHIVE] trigger error for video_id={video_id}: "
            f"{type(e).__name__}: {e}"
        )


# ---------------------------------------------------------------------------
# Startup / shutdown hooks
# ---------------------------------------------------------------------------

async def init_central_archive() -> None:
    """Best-effort initialization hook for startup."""
    if not is_archive_enabled():
        LOGGER(__name__).info(
            "[CENTRAL_ARCHIVE] disabled — "
            "CENTRAL_MUSIC_ARCHIVE_ENABLED is false OR "
            "CENTRAL_MONGO_DB_URI / STORAGE_CHANNEL_ID is unset. "
            "Bot will run normally without archiving."
        )
        return
    await _ensure_initialized()


async def shutdown_central_archive() -> None:
    """Best-effort graceful shutdown."""
    tasks = list(_pending_tasks)
    for t in tasks:
        if not t.done():
            try:
                t.cancel()
            except Exception:
                pass
    if tasks:
        try:
            await asyncio.wait_for(
                asyncio.gather(*tasks, return_exceptions=True),
                timeout=5.0,
            )
        except (asyncio.TimeoutError, Exception):
            pass

    global _central_client, _central_coll, _init_attempted
    if _central_client is not None:
        try:
            _central_client.close()
        except Exception:
            pass
    _central_client = None
    _central_coll = None
    _init_attempted = 0.0  # reset cooldown — allows fresh init on next start
