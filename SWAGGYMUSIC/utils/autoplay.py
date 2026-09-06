"""
Autoplay helper - ported from Meera Music (ShiviMusic) reference.

Primary: fetch YouTube "Mix"/radio playlist ("RD" + videoID) for the seed
track and pick a random candidate. Fallback: title-text search via
youtubesearchpython. Per-chat history (in-memory, 50 entries) prevents
repeating a song that was already autoplayed in that chat.

Resilience (added to fix the "autoplay suddenly stops" bug):
  - All exceptions are logged through LOGGER so failures show up in Heroku
    logs instead of being silently printed to stdout and lost.
  - Mix extraction is retried once on failure (transient YouTube/network
    errors are common).
  - The caller (Swaggy.autoplay_start in core/call.py) now tries EVERY
    candidate in the returned list (not just the first 3), and if a
    candidate's download OR play call fails it undoes the queue insertion
    and moves on to the next candidate. Only NoActiveGroupCall (voice
    chat genuinely gone) aborts the whole step.
  - On top of that, Swaggy._try_autoplay_with_retry wraps autoplay_start
    with up to 3 total attempts (2 retries, 5s apart) so a transient
    YouTube API/network failure no longer kills the autoplay loop.
  - There is NO hard cap on the number of autoplay tracks per chat. The
    only constant (_HISTORY_LIMIT) is a per-chat dedup history, not a play
    counter; it auto-resets when all candidates are exhausted.
"""

import asyncio
import glob
import os
import random

import yt_dlp
from youtubesearchpython.__future__ import VideosSearch

from SWAGGYMUSIC.logging import LOGGER

_HISTORY_LIMIT = 50
# Note: the actual download-attempt cap is now in core/call.py's
# autoplay_start, which iterates over ALL candidates returned here.
# This constant is kept for backward compatibility / documentation only.
_MAX_DOWNLOAD_ATTEMPTS = 3

_played_history: dict[int, list[str]] = {}


def remember_played(chat_id: int, vidid: str):
    if not vidid:
        return
    hist = _played_history.setdefault(chat_id, [])
    if vidid in hist:
        hist.remove(vidid)
    hist.append(vidid)
    if len(hist) > _HISTORY_LIMIT:
        del hist[: len(hist) - _HISTORY_LIMIT]


def _history(chat_id: int) -> list:
    return _played_history.get(chat_id, [])


def clear_history(chat_id: int):
    _played_history.pop(chat_id, None)


def _cookie_file():
    """Pick a random cookies.txt from SWAGGYMUSIC/assets (Lustify path)."""
    folder = os.path.join(os.getcwd(), "SWAGGYMUSIC", "assets")
    txt_files = glob.glob(os.path.join(folder, "*.txt"))
    if not txt_files:
        return None
    return random.choice(txt_files)


def _fetch_mix_sync(video_id: str, limit: int = 20) -> list:
    ydl_opts = {
        "quiet": True,
        "extract_flat": True,
        "skip_download": True,
        "playlistend": limit,
        "no_warnings": True,
    }
    cookiefile = _cookie_file()
    if cookiefile:
        ydl_opts["cookiefile"] = cookiefile
    url = f"https://www.youtube.com/watch?v={video_id}&list=RD{video_id}"
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
    return (info or {}).get("entries") or []


def _extract_mix_candidates(entries, chat_id: int, skip_history: bool):
    candidates = []
    played = [] if skip_history else _history(chat_id)
    for e in entries or []:
        if not e:
            continue
        vidid = e.get("id")
        title = e.get("title")
        if not (vidid and title):
            continue
        if vidid in played:
            continue
        duration = e.get("duration")
        if isinstance(duration, (int, float)):
            m, s = divmod(int(duration), 60)
            duration_min = f"{m}:{s:02d}"
        else:
            duration_min = str(duration) if duration else "Live"
        candidates.append(
            {
                "vidid": vidid,
                "title": title,
                "link": f"https://www.youtube.com/watch?v={vidid}",
                "duration_min": duration_min,
                "thumb": e.get("thumbnail")
                or f"https://i.ytimg.com/vi/{vidid}/hqdefault.jpg",
            }
        )
    return candidates


async def _fetch_mix_candidates(chat_id: int, seed_vidid: str) -> list:
    """Fetch the YouTube Mix playlist for `seed_vidid` and return a list
    of candidate tracks (excluding already-played ones). Retries once on
    failure because yt-dlp Mix extraction is flaky — a single transient
    YouTube/network error should NOT permanently kill autoplay."""
    loop = asyncio.get_event_loop()
    last_err = None
    for attempt in range(2):  # 1 try + 1 retry
        try:
            entries = await loop.run_in_executor(
                None, _fetch_mix_sync, seed_vidid, 20
            )
            candidates = _extract_mix_candidates(
                entries, chat_id, skip_history=False
            )
            if candidates:
                return candidates
            # No candidates — either the Mix was empty or all entries are
            # already in history. Reset history and try once more so
            # autoplay doesn't silently stall after 50 plays.
            if attempt == 0:
                clear_history(chat_id)
                candidates = _extract_mix_candidates(
                    entries, chat_id, skip_history=True
                )
                if candidates:
                    return candidates
            # If still empty, fall through to retry / fallback.
            return []
        except Exception as e:
            last_err = e
            LOGGER(__name__).warning(
                f"[AUTOPLAY MIX] attempt {attempt+1} failed for seed "
                f"{seed_vidid}: {type(e).__name__}: {e}"
            )
            if attempt == 0:
                # Brief pause before retry to avoid hammering YouTube.
                await asyncio.sleep(1)
    if last_err:
        LOGGER(__name__).warning(
            f"[AUTOPLAY MIX] giving up on seed {seed_vidid} after retries: "
            f"{type(last_err).__name__}"
        )
    return []


def _extract_candidates(results, chat_id: int, skip_history: bool):
    candidates = []
    played = [] if skip_history else _history(chat_id)
    for video in results:
        vidid = video.get("id")
        title = video.get("title")
        link = video.get("link")
        duration = video.get("duration")
        if not (vidid and title and link and duration):
            continue
        if vidid in played:
            continue
        thumbs = video.get("thumbnails") or []
        thumb = thumbs[0].get("url", "").split("?")[0] if thumbs else None
        candidates.append(
            {
                "vidid": vidid,
                "title": title,
                "link": link,
                "duration_min": duration,
                "thumb": thumb,
            }
        )
    return candidates


async def _fetch_search_candidates(chat_id: int, seed_title: str) -> list:
    """Fallback: title-text search via youtubesearchpython.VideosSearch.
    Used when the Mix playlist extraction fails or returns no
    candidates."""
    if not seed_title:
        return []
    try:
        search = VideosSearch(seed_title, limit=20)
        data = await search.next()
        results = data.get("result", []) if isinstance(data, dict) else []
    except Exception as e:
        LOGGER(__name__).warning(
            f"[AUTOPLAY SEARCH] failed for '{seed_title}': "
            f"{type(e).__name__}: {e}"
        )
        return []
    candidates = _extract_candidates(results, chat_id, skip_history=False)
    if not candidates:
        # All search results already played — reset history and retry.
        clear_history(chat_id)
        candidates = _extract_candidates(results, chat_id, skip_history=True)
    return candidates


async def fetch_autoplay_track(chat_id: int, seed_title: str, seed_vidid: str = None):
    """
    Primary: YouTube Mix ("RD" + videoID). Fallback: title-text search.
    Returns a list of candidate tracks (best match first), or [] if both
    sources failed. The caller is expected to try downloading each
    candidate in turn so a single bad video ID doesn't kill autoplay.

    (Previously returned a single dict; now returns a list so the caller
    can iterate. Kept backward-compatible by also being callable as before
    via fetch_autoplay_track_one for callers that only want one.)
    """
    candidates = []
    if seed_vidid:
        candidates = await _fetch_mix_candidates(chat_id, seed_vidid)
        if candidates:
            # Shuffle so the same seed doesn't always pick the same next
            # track, but keep the full list so the caller can fall through.
            random.shuffle(candidates)
            return candidates
        LOGGER(__name__).info(
            f"[AUTOPLAY] Mix empty for seed {seed_vidid}, falling back to "
            f"title search"
        )

    if not seed_title:
        return []

    candidates = await _fetch_search_candidates(chat_id, seed_title)
    if candidates:
        random.shuffle(candidates)
    return candidates


async def fetch_autoplay_track_one(chat_id: int, seed_title: str, seed_vidid: str = None):
    """Backward-compatible wrapper: returns a single candidate dict, or
    None. Existing callers (call.py, skip.py, callback.py) use this."""
    candidates = await fetch_autoplay_track(chat_id, seed_title, seed_vidid)
    return candidates[0] if candidates else None
