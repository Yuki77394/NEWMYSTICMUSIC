import asyncio
import os
from typing import Union

from SWAGGYMUSIC.misc import db
from SWAGGYMUSIC.utils.formatters import check_duration, seconds_to_min
from config import autoclean, time_to_seconds


async def put_queue(
    chat_id,
    original_chat_id,
    file,
    title,
    duration,
    user,
    vidid,
    user_id,
    stream,
    forceplay: Union[bool, str] = None,
):
    title = title.title()
    try:
        duration_in_seconds = time_to_seconds(duration) - 3
    except:
        duration_in_seconds = 0
    put = {
        "title": title,
        "dur": duration,
        "streamtype": stream,
        "by": user,
        "user_id": user_id,
        "chat_id": original_chat_id,
        "file": file,
        "vidid": vidid,
        "seconds": duration_in_seconds,
        "played": 0,
    }
    if forceplay:
        check = db.get(chat_id)
        if check:
            check.insert(0, put)
        else:
            db[chat_id] = []
            db[chat_id].append(put)
    else:
        db[chat_id].append(put)
    autoclean.append(file)

    # ------------------------------------------------------------------
    # Central Music Archive trigger (audio only, deterministic ownership).
    #
    # Fires AFTER ``autoclean.append(file)`` — playback ownership is
    # already established. The archive worker adds its own ref (count
    # >= 2), uploads to Telegram, and releases its ref via auto_clean()
    # in finally. auto_clean deletes the file only when count == 0
    # (both refs released). No polling, no timeout.
    #
    # Guards:
    #   - stream == "audio"  → video streams are never archived.
    #   - file is a real .mp3 → skips placeholders like "vid_{vidid}".
    #   - vidid is non-empty  → YouTube video ID for dedup.
    # The trigger is non-blocking (schedules a background task). Any
    # archive failure is caught and logged inside the worker — put_queue
    # is never affected.
    # ------------------------------------------------------------------
    if stream == "audio" and file and vidid:
        try:
            if (
                isinstance(file, str)
                and file.lower().endswith(".mp3")
                and os.path.isfile(file)
            ):
                from SWAGGYMUSIC.utils.central_music_archive import (
                    archive_youtube_audio,
                )
                archive_youtube_audio(
                    file_path=file,
                    video_id=str(vidid),
                    title=title,
                    duration=duration_in_seconds + 3 if duration_in_seconds > 0 else None,
                )
        except Exception:
            pass


async def put_queue_index(
    chat_id,
    original_chat_id,
    file,
    title,
    duration,
    user,
    vidid,
    stream,
    forceplay: Union[bool, str] = None,
):
    if "20.212.146.162" in vidid:
        try:
            dur = await asyncio.get_event_loop().run_in_executor(
                None, check_duration, vidid
            )
            duration = seconds_to_min(dur)
        except:
            duration = "ᴜʀʟ sᴛʀᴇᴀᴍ"
            dur = 0
    else:
        dur = 0
    put = {
        "title": title,
        "dur": duration,
        "streamtype": stream,
        "by": user,
        "chat_id": original_chat_id,
        "file": file,
        "vidid": vidid,
        "seconds": dur,
        "played": 0,
    }
    if forceplay:
        check = db.get(chat_id)
        if check:
            check.insert(0, put)
        else:
            db[chat_id] = []
            db[chat_id].append(put)
    else:
        db[chat_id].append(put)
