import asyncio
import os
from datetime import datetime, timedelta
from typing import Union

from ntgcalls import ConnectionNotFound, TelegramServerError
from pyrogram import Client
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from pytgcalls import PyTgCalls, exceptions, types
from pytgcalls.pytgcalls_session import PyTgCallsSession

import config
from SWAGGYMUSIC import LOGGER, YouTube, app
from SWAGGYMUSIC.misc import db
from SWAGGYMUSIC.utils.database import (add_active_chat, add_active_video_chat,
                                       get_lang, get_loop, group_assistant,
                                       is_autoend, is_autoplay_on, is_thumb_on,
                                       music_on, remove_active_chat,
                                       remove_active_video_chat, set_loop)
from SWAGGYMUSIC.utils.autoplay import fetch_autoplay_track, remember_played
from SWAGGYMUSIC.utils.exceptions import AssistantErr
from SWAGGYMUSIC.utils.formatters import (check_duration, seconds_to_min,
                                         speed_converter)
from SWAGGYMUSIC.utils.inline.play import stream_markup
from SWAGGYMUSIC.utils.stream.autoclear import auto_clean
from SWAGGYMUSIC.utils.stream.queue import put_queue
from SWAGGYMUSIC.utils.thumbnails import get_thumb
from strings import get_string


async def delete_old_message(chat_id: int):
    try:
        old = db.get(chat_id, [{}])[0].get("mystic")
        if old:
            await old.delete()
    except:
        pass


autoend = {}
counter = {}


async def _clear_(chat_id: int):
    db[chat_id] = []
    await remove_active_video_chat(chat_id)
    await remove_active_chat(chat_id)


class Call(PyTgCalls):
    def __init__(self):
        PyTgCallsSession.notice_displayed = True

        self.userbot1 = Client(
            name="SwaggyXAss1",
            api_id=config.API_ID,
            api_hash=config.API_HASH,
            session_string=str(config.STRING1),
        )
        self.one = PyTgCalls(self.userbot1, cache_duration=100)

        self.userbot2 = Client(
            name="SwaggyXAss2",
            api_id=config.API_ID,
            api_hash=config.API_HASH,
            session_string=str(config.STRING2),
        )
        self.two = PyTgCalls(self.userbot2, cache_duration=100)

        self.userbot3 = Client(
            name="SwaggyXAss3",
            api_id=config.API_ID,
            api_hash=config.API_HASH,
            session_string=str(config.STRING3),
        )
        self.three = PyTgCalls(self.userbot3, cache_duration=100)

        self.userbot4 = Client(
            name="SwaggyXAss4",
            api_id=config.API_ID,
            api_hash=config.API_HASH,
            session_string=str(config.STRING4),
        )
        self.four = PyTgCalls(self.userbot4, cache_duration=100)

        self.userbot5 = Client(
            name="SwaggyXAss5",
            api_id=config.API_ID,
            api_hash=config.API_HASH,
            session_string=str(config.STRING5),
        )
        self.five = PyTgCalls(self.userbot5, cache_duration=100)
        # Per-chat locks to serialize change_stream calls and prevent
        # concurrent queue mutations from racing (e.g. PyTgCalls firing
        # StreamEnded twice, or a user clicking Skip at the exact moment
        # a track ends).
        self._change_stream_locks = {}

    def _build_stream(
        self,
        source: str,
        video: bool,
        ffmpeg: str | None = None,
    ) -> types.MediaStream:
        return types.MediaStream(
            media_path=source,
            audio_parameters=types.AudioQuality.HIGH,
            video_parameters=types.VideoQuality.HD_720p,
            audio_flags=types.MediaStream.Flags.REQUIRED,
            video_flags=(
                types.MediaStream.Flags.AUTO_DETECT
                if video
                else types.MediaStream.Flags.IGNORE
            ),
            ffmpeg_parameters=ffmpeg,
        )

    
    async def _play_on_assistant(
        self,
        client: PyTgCalls,
        chat_id: int,
        stream: types.MediaStream,
    ):
        try:
            await client.play(
                chat_id=chat_id,
                stream=stream,
                config=types.GroupCallConfig(auto_start=False),
            )
        except exceptions.NoActiveGroupCall:
            raise
        except exceptions.NoAudioSourceFound:
            raise
        except (ConnectionNotFound, TelegramServerError):
            raise
        except Exception:
            raise

    
    async def pause_stream(self, chat_id: int):
        await delete_old_message(chat_id)
        assistant = await group_assistant(self, chat_id)
        await assistant.pause(chat_id)

    
    async def resume_stream(self, chat_id: int):
        await delete_old_message(chat_id)
        assistant = await group_assistant(self, chat_id)
        await assistant.resume(chat_id)

    
    async def stop_stream(self, chat_id: int):
        await delete_old_message(chat_id)
        assistant = await group_assistant(self, chat_id)
        try:
            await _clear_(chat_id)
            await assistant.leave_call(chat_id, close=False)
        except Exception:
            pass

    
    async def stop_stream_force(self, chat_id: int):
        for string, client in [
            (config.STRING1, self.one),
            (config.STRING2, self.two),
            (config.STRING3, self.three),
            (config.STRING4, self.four),
            (config.STRING5, self.five),
        ]:
            if not string:
                continue
            try:
                await client.leave_call(chat_id, close=False)
            except Exception:
                pass
        try:
            await _clear_(chat_id)
        except Exception:
            pass

    
    async def speedup_stream(self, chat_id: int, file_path, speed, playing):
        assistant = await group_assistant(self, chat_id)
        if str(speed) != "1.0":
            base = os.path.basename(file_path)
            chatdir = os.path.join(os.getcwd(), "playback", str(speed))
            if not os.path.isdir(chatdir):
                os.makedirs(chatdir)
            out = os.path.join(chatdir, base)
            if not os.path.isfile(out):
                if str(speed) == "0.5":
                    vs = 2.0
                elif str(speed) == "0.75":
                    vs = 1.35
                elif str(speed) == "1.5":
                    vs = 0.68
                elif str(speed) == "2.0":
                    vs = 0.5
                else:
                    vs = 1.0
                proc = await asyncio.create_subprocess_shell(
                    cmd=(
                        "ffmpeg "
                        "-i "
                        f"{file_path} "
                        "-filter:v "
                        f"setpts={vs}*PTS "
                        "-filter:a "
                        f"atempo={speed} "
                        f"{out}"
                    ),
                    stdin=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                await proc.communicate()
        else:
            out = file_path
        dur = await asyncio.get_event_loop().run_in_executor(None, check_duration, out)
        dur = int(dur)
        played, con_seconds = speed_converter(playing[0]["played"], speed)
        duration = seconds_to_min(dur)
        xx = f"-ss {played} -to {duration}"
        video_mode = playing[0]["streamtype"] == "video"
        stream = self._build_stream(out, video=video_mode, ffmpeg=xx)
        if str(db[chat_id][0]["file"]) == str(file_path):
            await self._play_on_assistant(assistant, chat_id, stream)
        else:
            raise AssistantErr("Umm")
        if str(db[chat_id][0]["file"]) == str(file_path):
            exis = (playing[0]).get("old_dur")
            if not exis:
                db[chat_id][0]["old_dur"] = db[chat_id][0]["dur"]
                db[chat_id][0]["old_second"] = db[chat_id][0]["seconds"]
            db[chat_id][0]["played"] = con_seconds
            db[chat_id][0]["dur"] = duration
            db[chat_id][0]["seconds"] = dur
            db[chat_id][0]["speed_path"] = out
            db[chat_id][0]["speed"] = speed

    async def force_stop_stream(self, chat_id: int):
        await delete_old_message(chat_id)
        assistant = await group_assistant(self, chat_id)
        try:
            check = db.get(chat_id)
            check.pop(0)
        except Exception:
            pass
        await remove_active_video_chat(chat_id)
        await remove_active_chat(chat_id)
        try:
            await assistant.leave_call(chat_id, close=False)
        except Exception:
            pass

    
    async def skip_stream(
        self,
        chat_id: int,
        link: str,
        video: Union[bool, str] = None,
        image: Union[bool, str] = None,
    ):
        assistant = await group_assistant(self, chat_id)
        stream = self._build_stream(link, video=bool(video))
        await self._play_on_assistant(assistant, chat_id, stream)

    
    async def seek_stream(self, chat_id, file_path, to_seek, duration, mode):
        assistant = await group_assistant(self, chat_id)
        ffmpeg = f"-ss {to_seek} -to {duration}"
        video_mode = mode == "video"
        stream = self._build_stream(
            file_path,
            video=video_mode,
            ffmpeg=ffmpeg,
        )
        await self._play_on_assistant(assistant, chat_id, stream)

    
    async def stream_call(self, link):
        assistant = await group_assistant(self, config.LOGGER_ID)
        stream = self._build_stream(link, video=True)
        await self._play_on_assistant(assistant, config.LOGGER_ID, stream)
        await asyncio.sleep(0.2)
        try:
            await assistant.leave_call(config.LOGGER_ID, close=False)
        except Exception:
            pass

    
    async def join_call(
        self,
        chat_id: int,
        original_chat_id: int,
        link,
        video: Union[bool, str] = None,
        image: Union[bool, str] = None,
    ):
        assistant = await group_assistant(self, chat_id)
        language = await get_lang(chat_id)
        _ = get_string(language)
        stream = self._build_stream(link, video=bool(video))
        try:
            await self._play_on_assistant(assistant, chat_id, stream)
        except exceptions.NoActiveGroupCall:
            raise AssistantErr(_["call_8"])
        except exceptions.NoAudioSourceFound:
            raise AssistantErr(_["call_10"])
        except (ConnectionNotFound, TelegramServerError):
            raise AssistantErr(_["call_10"])
        except Exception:
            raise AssistantErr(_["call_10"])
        await add_active_chat(chat_id)
        await music_on(chat_id)
        if video:
            await add_active_video_chat(chat_id)
        if await is_autoend():
            counter[chat_id] = {}
            users = len(await assistant.get_participants(chat_id))
            if users == 1:
                autoend[chat_id] = datetime.now() + timedelta(minutes=1)

    
    async def autoplay_start(
        self,
        chat_id: int,
        original_chat_id: int,
        seed_title: str,
        seed_vidid: str = None,
        client: PyTgCalls = None,
    ) -> bool:
        """Ported from Meera Music. Fetches a related track via YouTube Mix
        (fallback: title search), queues it with forceplay=True, starts
        playback, and sends a now-playing message. Returns True on success,
        False on failure (caller should fall back to leave_call).

        Resilience (added to fix the "autoplay suddenly stops" bug):
          - Fetches a *list* of candidate tracks and tries each one in turn
            until a download + play succeeds. A single bad video ID, a
            transient YouTube API failure, or a YouTube block no longer
            kills the whole autoplay loop.
          - All failures are logged through LOGGER so they appear in Heroku
            logs instead of being silently swallowed.
          - There is NO hard limit on the number of autoplay tracks per
            chat; the only constant is a per-chat dedup history (50
            entries) which auto-resets when exhausted."""
        if seed_vidid:
            remember_played(chat_id, seed_vidid)

        status_msg = None
        try:
            status_msg = await app.send_message(
                original_chat_id,
                "ʜσʟᴅ ση...\n\nᴅσᴡηʟσᴧᴅɪηɢ ηєxᴛ ϻєᴅɪᴧ ғʀσϻ ᴛʜє ǫυєυє.",
            )
        except Exception:
            status_msg = None

        async def _fail() -> bool:
            if status_msg:
                try:
                    await status_msg.delete()
                except Exception:
                    pass
            return False

        LOGGER(__name__).info(
            f"[AUTOPLAY] autoplay_start called for chat {chat_id} "
            f"(seed_vidid={seed_vidid}, seed_title={seed_title!r})"
        )

        # Fetch a list of candidates so we can fall through to the next
        # one if the first download/play fails. This is the key resilience
        # fix: a single bad video ID no longer kills autoplay.
        try:
            candidates = await fetch_autoplay_track(
                chat_id, seed_title, seed_vidid
            )
        except Exception as e:
            LOGGER(__name__).warning(
                f"[AUTOPLAY] fetch_autoplay_track raised: "
                f"{type(e).__name__}: {e}"
            )
            candidates = []

        if not candidates:
            LOGGER(__name__).warning(
                f"[AUTOPLAY] no candidates for chat {chat_id} "
                f"(seed_vidid={seed_vidid}, seed_title={seed_title!r})"
            )
            return await _fail()

        LOGGER(__name__).info(
            f"[AUTOPLAY] found {len(candidates)} candidates for chat {chat_id}"
        )

        language = await get_lang(chat_id)
        _ = get_string(language)

        # Try EACH candidate in turn (not just the first 3). If a
        # candidate's download fails OR the play call fails with a
        # transient error, log it and move on to the next candidate.
        # Only NoActiveGroupCall (voice chat genuinely gone) aborts the
        # whole step — every other failure tries the next candidate.
        chosen_track = None
        for i, track in enumerate(candidates):
            vidid = track.get("vidid")
            try:
                file_path, direct = await YouTube.download(
                    vidid, None, videoid=True
                )
                if not file_path:
                    LOGGER(__name__).warning(
                        f"[AUTOPLAY] candidate {i+1}/{len(candidates)} "
                        f"vidid={vidid} returned no file_path"
                    )
                    continue
            except Exception as e:
                LOGGER(__name__).warning(
                    f"[AUTOPLAY] candidate {i+1}/{len(candidates)} "
                    f"vidid={vidid} download raised: "
                    f"{type(e).__name__}: {e}"
                )
                continue

            # Download succeeded — queue it, then try to play it.
            remember_played(chat_id, vidid)
            title = track["title"].title()
            duration_min = track["duration_min"]

            await put_queue(
                chat_id,
                original_chat_id,
                file_path if direct else f"vid_{vidid}",
                title,
                duration_min,
                "🔁 𝐀ᴜᴛᴏᴘʟᴀʏ",
                vidid,
                1,
                "audio",
                forceplay=True,
            )
            if db.get(chat_id):
                db[chat_id][0]["played"] = 0
                db[chat_id][0]["seconds"] = 0
                db[chat_id][0]["speed"] = 1.0
                db[chat_id][0]["speed_path"] = None
                db[chat_id][0]["old_dur"] = None
                db[chat_id][0]["old_second"] = 0

            stream = self._build_stream(file_path, video=False)
            assistant = client or await group_assistant(self, chat_id)
            try:
                await self._play_on_assistant(assistant, chat_id, stream)
            except exceptions.NoActiveGroupCall as e:
                # Voice chat is gone — trying more candidates won't help.
                LOGGER(__name__).warning(
                    f"[AUTOPLAY] _play_on_assistant failed with "
                    f"NoActiveGroupCall for chat {chat_id} — voice chat "
                    f"is gone, stopping autoplay"
                )
                # Undo the queue insertion we just did so db[chat_id]
                # stays consistent.
                try:
                    db[chat_id].pop(0)
                except Exception:
                    pass
                return await _fail()
            except Exception as e:
                LOGGER(__name__).warning(
                    f"[AUTOPLAY] _play_on_assistant failed for "
                    f"vidid={vidid}: {type(e).__name__}: {e} "
                    f"— trying next candidate"
                )
                # Undo the queue insertion and try the next candidate.
                try:
                    db[chat_id].pop(0)
                except Exception:
                    pass
                continue

            # Success!
            chosen_track = track
            LOGGER(__name__).info(
                f"[AUTOPLAY] candidate {i+1}/{len(candidates)} "
                f"vidid={vidid} playing successfully"
            )
            break

        if not chosen_track:
            LOGGER(__name__).warning(
                f"[AUTOPLAY] all {len(candidates)} candidates failed for "
                f"chat {chat_id}"
            )
            return await _fail()

        track = chosen_track
        title = track["title"].title()
        duration_min = track["duration_min"]

        try:
            thumb_on_now = await is_thumb_on(chat_id)
            button = stream_markup(
                _,
                chat_id,
                autoplay_status=await is_autoplay_on(chat_id),
                thumb_status=thumb_on_now,
            )
            caption = _["stream_1"].format(
                f"https://t.me/{app.username}?start=info_{track['vidid']}",
                title[:23],
                duration_min,
                "𝐀ᴜᴛᴏᴘʟᴀʏ 🚩",
            )
            if thumb_on_now:
                img = await get_thumb(
                    track["vidid"],
                    title=title,
                    duration=duration_min,
                )
                run = await app.send_photo(
                    chat_id=original_chat_id,
                    photo=img,
                    has_spoiler=True,
                    caption=caption,
                    reply_markup=InlineKeyboardMarkup(button),
                )
            else:
                run = await app.send_message(
                    chat_id=original_chat_id,
                    text=caption,
                    disable_web_page_preview=True,
                    reply_markup=InlineKeyboardMarkup(button),
                )
            db[chat_id][0]["mystic"] = run
            db[chat_id][0]["markup"] = "stream"
        except Exception as e:
            LOGGER(__name__).warning(
                f"[AUTOPLAY] failed to send now-playing message for "
                f"chat {chat_id}: {type(e).__name__}: {e} (playback continues)"
            )

        if status_msg:
            try:
                await status_msg.delete()
            except Exception:
                pass

        try:
            await add_active_chat(chat_id)
            await music_on(chat_id)
        except Exception:
            pass

        LOGGER(__name__).info(
            f"[AUTOPLAY] autoplay_start succeeded for chat {chat_id} "
            f"(vidid={track['vidid']})"
        )
        return True

    async def _try_autoplay_with_retry(
        self,
        chat_id: int,
        popped: dict | None,
        client: PyTgCalls,
        max_retries: int = 2,
    ) -> bool:
        """Try autoplay_start up to max_retries+1 times with a brief delay
        between attempts. Returns True if any attempt succeeded, False
        otherwise.

        This is the key resilience fix: a single transient YouTube API/
        network failure no longer kills the autoplay loop. The caller
        should only fall through to 'Queue Has Ended' after this returns
        False."""
        if not popped:
            return False
        if not await is_autoplay_on(chat_id):
            LOGGER(__name__).info(
                f"[AUTOPLAY] autoplay is OFF for chat {chat_id} — not "
                f"attempting autoplay_start"
            )
            return False

        total = max_retries + 1
        for attempt in range(total):
            try:
                LOGGER(__name__).info(
                    f"[AUTOPLAY] attempt {attempt+1}/{total} for chat {chat_id} "
                    f"(seed_vidid={popped.get('vidid')})"
                )
                started = await self.autoplay_start(
                    chat_id,
                    popped.get("chat_id", chat_id),
                    popped.get("title"),
                    popped.get("vidid"),
                    client=client,
                )
                if started:
                    LOGGER(__name__).info(
                        f"[AUTOPLAY] attempt {attempt+1}/{total} succeeded "
                        f"for chat {chat_id}"
                    )
                    return True
                LOGGER(__name__).warning(
                    f"[AUTOPLAY] attempt {attempt+1}/{total} returned False "
                    f"for chat {chat_id}"
                )
            except Exception as e:
                LOGGER(__name__).warning(
                    f"[AUTOPLAY] attempt {attempt+1}/{total} raised for "
                    f"chat {chat_id}: {type(e).__name__}: {e}"
                )
            if attempt < max_retries:
                LOGGER(__name__).info(
                    f"[AUTOPLAY] retrying in 5s for chat {chat_id}"
                )
                await asyncio.sleep(5)
        LOGGER(__name__).warning(
            f"[AUTOPLAY] all {total} attempts failed for chat {chat_id} "
            f"— autoplay giving up"
        )
        return False

    async def _handle_queue_ended(
        self, chat_id: int, client: PyTgCalls
    ):
        """Send the 'Queue Has Ended' message and leave the voice call.
        Only called when autoplay is OFF or all autoplay retries have
        failed."""
        await _clear_(chat_id)
        try:
            buttons = InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "✙ ʌᴅᴅ ϻє вᴧʙʏ ✙",
                            url=f"https://t.me/{app.username}?startgroup=true",
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            "⋞ ᴄʟᴏsє ⋟", callback_data="close_message"
                        ),
                    ],
                ]
            )
            await app.send_message(
                chat_id,
                """
🎵 𝐓ʜᴇ 𝐌ᴜsɪᴄ 𝐐ᴜᴇᴜᴇ 𝐇𝴀s 𝐄ɴᴅᴇ𝐝.
➤ 𝐔𝐬𝐞 /play 𝐓𝐨 𝐀𝴅ᴅ 𝐌ᴏʀ𝴇 𝐒ᴏɴɢs 🎶
""",
                reply_markup=buttons,
            )
        except Exception as e:
            LOGGER(__name__).warning(
                f"[AUTOPLAY] failed to send 'Queue Has Ended' message for "
                f"chat {chat_id}: {type(e).__name__}: {e}"
            )
        try:
            return await client.leave_call(chat_id, close=False)
        except Exception as e:
            LOGGER(__name__).warning(
                f"[AUTOPLAY] leave_call failed for chat {chat_id}: "
                f"{type(e).__name__}: {e}"
            )
            return None

    async def change_stream(self, client: PyTgCalls, chat_id: int):
        """Called by PyTgCalls when the current track's audio stream ends.
        Pops the finished track, then either plays the next queued track or
        (if the queue is empty) starts autoplay / shows 'Queue Has Ended'.

        Resilience fixes:
          - Per-chat asyncio.Lock prevents concurrent change_stream calls
            from racing on db[chat_id] mutations (e.g. PyTgCalls firing
            StreamEnded twice, or a user clicking Skip at the exact moment
            a track ends).
          - When autoplay is ON, retries autoplay_start up to 2 times (3
            total attempts) with a 5s delay before falling through to
            'Queue Has Ended'. A single transient YouTube API/network
            failure no longer kills the autoplay loop.
          - All branches log through LOGGER so failures are diagnosable.
        """
        LOGGER(__name__).info(
            f"[AUTOPLAY] change_stream (track finished) for chat {chat_id}"
        )
        await delete_old_message(chat_id)

        # Per-chat lock to prevent concurrent change_stream races.
        lock = self._change_stream_locks.get(chat_id)
        if lock is None:
            lock = asyncio.Lock()
            self._change_stream_locks[chat_id] = lock
        async with lock:
            await self._change_stream_inner(client, chat_id)

    async def _change_stream_inner(self, client: PyTgCalls, chat_id: int):
        check = db.get(chat_id)
        popped = None
        loop = await get_loop(chat_id)
        try:
            if loop == 0:
                popped = check.pop(0)
            else:
                loop = loop - 1
                await set_loop(chat_id, loop)
            await auto_clean(popped)
            if not check:
                # Queue is empty after popping. If autoplay is on, try to
                # start a related track (with retries). Otherwise, show
                # 'Queue Has Ended' and leave.
                if await self._try_autoplay_with_retry(chat_id, popped, client):
                    return
                LOGGER(__name__).warning(
                    f"[AUTOPLAY] autoplay failed or off for chat {chat_id} "
                    f"— showing 'Queue Has Ended'"
                )
                return await self._handle_queue_ended(chat_id, client)
        except Exception as e:
            LOGGER(__name__).warning(
                f"[AUTOPLAY] change_stream entered except-branch for chat "
                f"{chat_id}: {type(e).__name__}: {e}"
            )
            try:
                if await self._try_autoplay_with_retry(chat_id, popped, client):
                    return
                LOGGER(__name__).warning(
                    f"[AUTOPLAY] autoplay failed in except-branch for chat "
                    f"{chat_id} — showing 'Queue Has Ended'"
                )
                return await self._handle_queue_ended(chat_id, client)
            except Exception as e2:
                LOGGER(__name__).error(
                    f"[AUTOPLAY] change_stream fatal error in except-branch "
                    f"for chat {chat_id}: {type(e2).__name__}: {e2}"
                )
                return
        queued = check[0]["file"]
        language = await get_lang(chat_id)
        _ = get_string(language)
        title = (check[0]["title"]).title()
        user = check[0]["by"]
        original_chat_id = check[0]["chat_id"]
        streamtype = check[0]["streamtype"]
        videoid = check[0]["vidid"]
        db[chat_id][0]["played"] = 0
        exis = (check[0]).get("old_dur")
        if exis:
            db[chat_id][0]["dur"] = exis
            db[chat_id][0]["seconds"] = check[0]["old_second"]
            db[chat_id][0]["speed_path"] = None
            db[chat_id][0]["speed"] = 1.0
        video = True if str(streamtype) == "video" else False
        if "live_" in queued:
            n, link = await YouTube.video(videoid, True)
            if n == 0:
                return await app.send_message(
                    original_chat_id,
                    text=_["call_6"],
                )
            stream = self._build_stream(link, video=video)
            try:
                await self._play_on_assistant(client, chat_id, stream)
            except Exception:
                return await app.send_message(
                    original_chat_id,
                    text=_["call_6"],
                )
            img = await get_thumb(
                videoid,
                title=title,
                duration=check[0]["dur"],
            )
            thumb_on_now = await is_thumb_on(chat_id)
            button = stream_markup(
                _,
                chat_id,
                autoplay_status=await is_autoplay_on(chat_id),
                thumb_status=thumb_on_now,
            )
            caption = _["stream_1"].format(
                f"https://t.me/{app.username}?start=info_{videoid}",
                title[:23],
                check[0]["dur"],
                user,
            )
            if thumb_on_now:
                run = await app.send_photo(
                    chat_id=original_chat_id,
                    photo=img,
                    has_spoiler=True,
                    caption=caption,
                    reply_markup=InlineKeyboardMarkup(button),
                )
            else:
                run = await app.send_message(
                    chat_id=original_chat_id,
                    text=caption,
                    disable_web_page_preview=True,
                    reply_markup=InlineKeyboardMarkup(button),
                )
            db[chat_id][0]["mystic"] = run
            db[chat_id][0]["markup"] = "tg"
        elif "vid_" in queued:
            mystic = await app.send_message(original_chat_id, _["call_7"])
            try:
                file_path, direct = await YouTube.download(
                    videoid,
                    mystic,
                    videoid=True,
                    video=video,
                )
            except Exception as e:
                LOGGER(__name__).warning(
                    f"[AUTOPLAY] download failed for queued vid_ track "
                    f"{videoid} in chat {chat_id}: {type(e).__name__}: {e} "
                    f"— trying autoplay fallback"
                )
                try:
                    await mystic.delete()
                except Exception:
                    pass
                # Download failed for this queued track. If autoplay is on,
                # try to start a related track instead of leaving the bot
                # stuck in voice chat with nothing playing. This prevents
                # the "AutoPlay stops after a few songs" scenario where a
                # single bad queued track killed the whole session.
                if popped and await is_autoplay_on(chat_id):
                    if await self._try_autoplay_with_retry(chat_id, popped, client):
                        return
                return await self._handle_queue_ended(chat_id, client)
            if not file_path:
                LOGGER(__name__).warning(
                    f"[AUTOPLAY] download returned no file for queued vid_ "
                    f"track {videoid} in chat {chat_id} — trying autoplay "
                    f"fallback"
                )
                try:
                    await mystic.delete()
                except Exception:
                    pass
                if popped and await is_autoplay_on(chat_id):
                    if await self._try_autoplay_with_retry(chat_id, popped, client):
                        return
                return await self._handle_queue_ended(chat_id, client)
            stream = self._build_stream(file_path, video=video)
            try:
                await self._play_on_assistant(client, chat_id, stream)
            except Exception as e:
                LOGGER(__name__).warning(
                    f"[AUTOPLAY] _play_on_assistant failed for queued vid_ "
                    f"track {videoid} in chat {chat_id}: "
                    f"{type(e).__name__}: {e} — trying autoplay fallback"
                )
                try:
                    await mystic.delete()
                except Exception:
                    pass
                if popped and await is_autoplay_on(chat_id):
                    if await self._try_autoplay_with_retry(chat_id, popped, client):
                        return
                return await self._handle_queue_ended(chat_id, client)
            img = await get_thumb(
                videoid,
                title=title,
                duration=check[0]["dur"],
            )
            thumb_on_now = await is_thumb_on(chat_id)
            button = stream_markup(
                _,
                chat_id,
                autoplay_status=await is_autoplay_on(chat_id),
                thumb_status=thumb_on_now,
            )
            await mystic.delete()
            caption = _["stream_1"].format(
                f"https://t.me/{app.username}?start=info_{videoid}",
                title[:23],
                check[0]["dur"],
                user,
            )
            if thumb_on_now:
                run = await app.send_photo(
                    chat_id=original_chat_id,
                    photo=img,
                    has_spoiler=True,
                    caption=caption,
                    reply_markup=InlineKeyboardMarkup(button),
                )
            else:
                run = await app.send_message(
                    chat_id=original_chat_id,
                    text=caption,
                    disable_web_page_preview=True,
                    reply_markup=InlineKeyboardMarkup(button),
                )
            db[chat_id][0]["mystic"] = run
            db[chat_id][0]["markup"] = "stream"

        elif "index_" in queued:
            stream = self._build_stream(videoid, video=video)
            try:
                await self._play_on_assistant(client, chat_id, stream)
            except Exception:
                return await app.send_message(
                    original_chat_id,
                    text=_["call_6"],
                )
            thumb_on_now = await is_thumb_on(chat_id)
            button = stream_markup(
                _,
                chat_id,
                autoplay_status=await is_autoplay_on(chat_id),
                thumb_status=thumb_on_now,
            )
            caption = _["stream_2"].format(user)
            if thumb_on_now:
                run = await app.send_photo(
                    chat_id=original_chat_id,
                    photo=config.STREAM_IMG_URL,
                    has_spoiler=True,
                    caption=caption,
                    reply_markup=InlineKeyboardMarkup(button),
                )
            else:
                run = await app.send_message(
                    chat_id=original_chat_id,
                    text=caption,
                    disable_web_page_preview=True,
                    reply_markup=InlineKeyboardMarkup(button),
                )
            db[chat_id][0]["mystic"] = run
            db[chat_id][0]["markup"] = "tg"
        else:
            stream = self._build_stream(queued, video=video)
            try:
                await self._play_on_assistant(client, chat_id, stream)
            except Exception:
                return await app.send_message(
                    original_chat_id,
                    text=_["call_6"],
                )
            if videoid == "telegram":
                thumb_on_now = await is_thumb_on(chat_id)
                button = stream_markup(
                    _,
                    chat_id,
                    autoplay_status=await is_autoplay_on(chat_id),
                    thumb_status=thumb_on_now,
                )
                caption = _["stream_1"].format(
                    config.SUPPORT_CHAT, title[:23], check[0]["dur"], user
                )
                if thumb_on_now:
                    run = await app.send_photo(
                        chat_id=original_chat_id,
                        photo=(
                            config.TELEGRAM_AUDIO_URL
                            if str(streamtype) == "audio"
                            else config.TELEGRAM_VIDEO_URL
                        ),
                        caption=caption,
                        reply_markup=InlineKeyboardMarkup(button),
                    )
                else:
                    run = await app.send_message(
                        chat_id=original_chat_id,
                        text=caption,
                        disable_web_page_preview=True,
                        reply_markup=InlineKeyboardMarkup(button),
                    )
                db[chat_id][0]["mystic"] = run
                db[chat_id][0]["markup"] = "tg"
            elif videoid == "soundcloud":
                thumb_on_now = await is_thumb_on(chat_id)
                button = stream_markup(
                    _,
                    chat_id,
                    autoplay_status=await is_autoplay_on(chat_id),
                    thumb_status=thumb_on_now,
                )
                caption = _["stream_1"].format(
                    config.SUPPORT_CHAT, title[:23], check[0]["dur"], user
                )
                if thumb_on_now:
                    run = await app.send_photo(
                        chat_id=original_chat_id,
                        photo=config.SOUNCLOUD_IMG_URL,
                        caption=caption,
                        reply_markup=InlineKeyboardMarkup(button),
                    )
                else:
                    run = await app.send_message(
                        chat_id=original_chat_id,
                        text=caption,
                        disable_web_page_preview=True,
                        reply_markup=InlineKeyboardMarkup(button),
                    )
                db[chat_id][0]["mystic"] = run
                db[chat_id][0]["markup"] = "tg"
            else:
                thumb_on_now = await is_thumb_on(chat_id)
                button = stream_markup(
                    _,
                    chat_id,
                    autoplay_status=await is_autoplay_on(chat_id),
                    thumb_status=thumb_on_now,
                )
                caption = _["stream_1"].format(
                    f"https://t.me/{app.username}?start=info_{videoid}",
                    title[:23],
                    check[0]["dur"],
                    user,
                )
                if thumb_on_now:
                    img = await get_thumb(
                        videoid,
                        title=title,
                        duration=check[0]["dur"],
                    )
                    run = await app.send_photo(
                        chat_id=original_chat_id,
                        photo=img,
                        has_spoiler=True,
                        caption=caption,
                        reply_markup=InlineKeyboardMarkup(button),
                    )
                else:
                    run = await app.send_message(
                        chat_id=original_chat_id,
                        text=caption,
                        disable_web_page_preview=True,
                        reply_markup=InlineKeyboardMarkup(button),
                    )
                db[chat_id][0]["mystic"] = run
                db[chat_id][0]["markup"] = "stream"

    
    async def ping(self):
        pings = []
        if config.STRING1:
            pings.append(self.one.ping)
        if config.STRING2:
            pings.append(self.two.ping)
        if config.STRING3:
            pings.append(self.three.ping)
        if config.STRING4:
            pings.append(self.four.ping)
        if config.STRING5:
            pings.append(self.five.ping)
        return str(round(sum(pings) / len(pings), 3)) if pings else "0"

    
    async def start(self):
        LOGGER(__name__).info("Starting PyTgCalls Client...\n")
        if config.STRING1:
            await self.one.start()
        if config.STRING2:
            await self.two.start()
        if config.STRING3:
            await self.three.start()
        if config.STRING4:
            await self.four.start()
        if config.STRING5:
            await self.five.start()

    
    async def decorators(self):
        for string, client in [
            (config.STRING1, self.one),
            (config.STRING2, self.two),
            (config.STRING3, self.three),
            (config.STRING4, self.four),
            (config.STRING5, self.five),
        ]:
            if not string:
                continue

            @client.on_update()
            async def _update_handler(_, update: types.Update, _client=client):
                if isinstance(update, types.StreamEnded):
                    if update.stream_type == types.StreamEnded.Type.AUDIO:
                        try:
                            await self.change_stream(_client, update.chat_id)
                        except Exception as e:
                            LOGGER(__name__).error(
                                f"[AUTOPLAY] change_stream raised in "
                                f"StreamEnded handler for chat "
                                f"{update.chat_id}: {type(e).__name__}: {e}"
                            )
                elif isinstance(update, types.ChatUpdate):
                    if update.status in [
                        types.ChatUpdate.Status.KICKED,
                        types.ChatUpdate.Status.LEFT_GROUP,
                        types.ChatUpdate.Status.CLOSED_VOICE_CHAT,
                    ]:
                        await self.stop_stream(update.chat_id)


Swaggy = Call()
