import asyncio
import importlib

from pyrogram import idle
from pytgcalls.exceptions import NoActiveGroupCall

import config
from SWAGGYMUSIC import LOGGER, app, userbot
from SWAGGYMUSIC.core.call import Swaggy
from SWAGGYMUSIC.core.prewarm import prewarm_all
from SWAGGYMUSIC.misc import sudo
from SWAGGYMUSIC.plugins import ALL_MODULES
from SWAGGYMUSIC.utils.central_music_archive import init_central_archive
from SWAGGYMUSIC.utils.database import get_banned_users, get_gbanned
from config import BANNED_USERS


async def init():
    if (
        not config.STRING1
        and not config.STRING2
        and not config.STRING3
        and not config.STRING4
        and not config.STRING5
    ):
        LOGGER(__name__).error("𝐒𝐭𝐫𝐢𝐧𝐠 𝐒𝐞𝐬𝐬𝐢𝐨𝐧 𝐍𝐨𝐭 𝐅𝐢𝐥𝐥𝐞𝐝, 𝐏𝐥𝐞𝐚𝐬𝐞 𝐅𝐢𝐥𝐥 𝐀 𝐏𝐲𝐫𝐨𝐠𝐫𝐚𝐦 𝐒𝐞𝐬𝐬𝐢𝐨𝐧")
        exit()
    await sudo()
    try:
        users = await get_gbanned()
        for user_id in users:
            BANNED_USERS.add(user_id)
        users = await get_banned_users()
        for user_id in users:
            BANNED_USERS.add(user_id)
    except:
        pass
    await app.start()
    for all_module in ALL_MODULES:
        importlib.import_module("SWAGGYMUSIC.plugins" + all_module)
    LOGGER("SWAGGYMUSIC.plugins").info("𝐀𝐥𝐥 𝐅𝐞𝐚𝐭𝐮𝐫𝐞𝐬 𝐋𝐨𝐚𝐝𝐞𝐝 𝐁𝐚𝐛𝐲🥳...")

    # Best-effort init for the Central Music Archive (optional, isolated).
    # If the central Mongo URI / storage channel are not configured, this
    # is a no-op. If they are configured but unreachable, the archive is
    # disabled for this process and the bot continues normally. Never
    # blocks startup on its own — runs in the background with a hard
    # timeout so a slow Mongo cluster can't stall the bot banner.
    archive_init_task = asyncio.create_task(init_central_archive())
    archive_init_task.add_done_callback(
        lambda t: t.exception() and LOGGER(__name__).warning(
            f"central archive init error: {t.exception()}"
        )
    )
    # Prewarm expensive resources (YouTube API, youtubesearchpython, yt-dlp,
    # i.ytimg) concurrently with userbot/Swaggy startup so the first /play
    # after a restart doesn't pay the cold-start penalty. Best-effort:
    # failures are logged but never block startup.
    prewarm_task = asyncio.create_task(prewarm_all())
    await userbot.start()
    await Swaggy.start()
    # Don't block the banner on prewarm — it has its own internal timeouts
    # (max 10s) and runs in the background. If it's not done by the time
    # we need to play, the first /play will just fall back to the cold path
    # for whatever resource wasn't prewarmed yet.
    prewarm_task.add_done_callback(
        lambda t: t.exception() and LOGGER(__name__).warning(
            f"prewarm task error: {t.exception()}"
        )
    )
    try:
        await Swaggy.stream_call("https://te.legra.ph/file/29f784eb49d230ab62e9e.mp4")
    except NoActiveGroupCall:
        LOGGER("SWAGGYMUSIC").error(
            "𝗣𝗹𝗭 𝗦𝗧𝗔𝗥𝗧 𝗬𝗢𝗨𝗥 𝗟𝗢𝗚 𝗚𝗥𝗢𝗨𝗣 𝗩𝗢𝗜𝗖𝗘𝗖𝗛𝗔𝗧\𝗖𝗛𝗔𝗡𝗡𝗘𝗟\n\n𝗧𝗛𝗨𝗡𝗗𝗘𝗥 𝗕𝗢𝗧 𝗦𝗧𝗢𝗣........"
        )
        exit()
    except:
        pass
    await Swaggy.decorators()
    LOGGER("SWAGGYMUSIC").info(
        "╔═════ஜ۩۞۩ஜ════╗\n  ☠︎︎𝗠𝗔𝗗𝗘 𝗕𝗬 𝗔𝗟𝗣𝗛𝗔☠︎︎\n╚═════ஜ۩۞۩ஜ════╝"
    )
    await idle()
    # Best-effort graceful shutdown of the Central Music Archive: cancels
    # any pending background upload tasks (with a 5s grace window) and
    # closes the central Mongo client. Never raises — safe to call even
    # if archive was never initialized.
    try:
        from SWAGGYMUSIC.utils.central_music_archive import (
            shutdown_central_archive,
        )
        await shutdown_central_archive()
    except Exception as e:
        LOGGER(__name__).warning(
            f"central archive shutdown error (ignored): "
            f"{type(e).__name__}: {e}"
        )
    await app.stop()
    await userbot.stop()
    LOGGER("SWAGGYMUSIC").info("𝗦𝗧𝗢𝗣 𝗦𝗢𝗡𝗔𝗟𝗜 𝗠𝗨𝗦𝗜𝗖 𝗕𝗢𝗧..")


if __name__ == "__main__":
    asyncio.get_event_loop().run_until_complete(init())
