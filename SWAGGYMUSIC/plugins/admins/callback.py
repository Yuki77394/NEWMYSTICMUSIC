import asyncio
from telegram import CallbackQuery
from pyrogram import filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from SWAGGYMUSIC import LOGGER, YouTube, app
from SWAGGYMUSIC.core.call import Swaggy
from SWAGGYMUSIC.misc import SUDOERS, db
from SWAGGYMUSIC.utils.database import (
    autoplay_off,
    autoplay_on,
    get_active_chats,
    get_lang,
    get_upvote_count,
    is_active_chat,
    is_autoplay_on,
    is_music_playing,
    is_nonadmin_chat,
    is_thumb_on,
    music_off,
    music_on,
    set_loop,
    thumb_off,
    thumb_on,
)
from pyrogram.errors import (
    ChatAdminRequired,
    InviteRequestSent,
    UserAlreadyParticipant,
    UserNotParticipant,
)
from SWAGGYMUSIC.utils.database import get_assistant
from SWAGGYMUSIC.utils.decorators.language import languageCB
from SWAGGYMUSIC.utils.formatters import seconds_to_min
from SWAGGYMUSIC.utils.inline import close_markup, stream_markup, stream_markup_timer
from SWAGGYMUSIC.utils.stream.autoclear import auto_clean
from SWAGGYMUSIC.utils.thumbnails import get_thumb
from config import (
    BANNED_USERS,
    SOUNCLOUD_IMG_URL,
    STREAM_IMG_URL,
    TELEGRAM_AUDIO_URL,
    TELEGRAM_VIDEO_URL,
    adminlist,
    confirmer,
    votemode,
)
from strings import get_string

checker = {}
upvoters = {}



@app.on_callback_query(filters.regex("unban_assistant"))
async def unban_assistant(_, callback: CallbackQuery):
    chat_id = callback.message.chat.id
    userbot = await get_assistant(chat_id)
    
    try:
        await app.unban_chat_member(chat_id, userbot.id)
        await callback.answer("𝖬𝖸 𝖠𝖲𝖲𝖨𝖲𝖳𝖠𝖬𝖳 𝖨𝖣 𝖴𝖭𝖡𝖠𝖭𝖭𝖤𝖣 𝖲𝖴𝖢𝖢𝖤𝖲𝖲𝖥𝖴𝖫𝖫𝖸\n\n➻ 𝖭𝖮𝖶 𝖸𝖮𝖴 𝖢𝖠𝖭 𝖯𝖫𝖠𝖸 𝖲𝖮𝖭𝖦𝖲\n\n𝖳𝖧𝖠𝖭𝖪 𝖸𝖮𝖴 𝖣𝖠𝖱𝖫𝖨𝖭𝖦", show_alert=True)
    except Exception as e:
        await callback.answer(f"𝖥𝖠𝖨𝖫𝖤𝖣 𝖳𝖮 𝖴𝖭𝖡𝖠𝖭 𝖬𝖸 𝖠𝖲𝖲𝖨𝖲𝖳𝖠𝖭𝖳 𝖡𝖤𝖢𝖠𝖴𝖲𝖤 𝖨 𝖣𝖮𝖭𝖳 𝖧𝖠𝖵𝖤 𝖡𝖠𝖭 𝖯𝖮𝖶𝖤𝖱\n\n➻ 𝖯𝖫𝖤𝖠𝖲𝖤 𝖯𝖱𝖮𝖵𝖨𝖣𝖤 𝖬𝖤 𝖡𝖠𝖭 𝖯𝖮𝖶𝖤𝖱 𝖲𝖮 𝖳𝖧𝖠𝖳 𝖨 𝖢𝖠𝖭 𝖴𝖭𝖡𝖠𝖭 𝖬𝖸 𝖠𝖲𝖲𝖨𝖲𝖳𝖠𝖭𝖳 𝖨𝖣", show_alert=True)


@app.on_callback_query(filters.regex("ADMIN") & ~BANNED_USERS)
@languageCB
async def del_back_playlist(client, CallbackQuery, _):
    callback_data = CallbackQuery.data.strip()
    callback_request = callback_data.split(None, 1)[1]
    command, chat = callback_request.split("|")
    if "_" in str(chat):
        bet = chat.split("_")
        chat = bet[0]
        counter = bet[1]
    chat_id = int(chat)
    if not await is_active_chat(chat_id):
        return await CallbackQuery.answer(_["general_5"], show_alert=True)
    mention = CallbackQuery.from_user.mention
    if command == "UpVote":
        if chat_id not in votemode:
            votemode[chat_id] = {}
        if chat_id not in upvoters:
            upvoters[chat_id] = {}

        voters = (upvoters[chat_id]).get(CallbackQuery.message.id)
        if not voters:
            upvoters[chat_id][CallbackQuery.message.id] = []

        vote = (votemode[chat_id]).get(CallbackQuery.message.id)
        if not vote:
            votemode[chat_id][CallbackQuery.message.id] = 0

        if CallbackQuery.from_user.id in upvoters[chat_id][CallbackQuery.message.id]:
            (upvoters[chat_id][CallbackQuery.message.id]).remove(
                CallbackQuery.from_user.id
            )
            votemode[chat_id][CallbackQuery.message.id] -= 1
        else:
            (upvoters[chat_id][CallbackQuery.message.id]).append(
                CallbackQuery.from_user.id
            )
            votemode[chat_id][CallbackQuery.message.id] += 1
        upvote = await get_upvote_count(chat_id)
        get_upvotes = int(votemode[chat_id][CallbackQuery.message.id])
        if get_upvotes >= upvote:
            votemode[chat_id][CallbackQuery.message.id] = upvote
            try:
                exists = confirmer[chat_id][CallbackQuery.message.id]
                current = db[chat_id][0]
            except:
                return await CallbackQuery.edit_message_text(f"ғᴀɪʟᴇᴅ.")
            try:
                if current["vidid"] != exists["vidid"]:
                    return await CallbackQuery.edit_message.text(_["admin_35"])
                if current["file"] != exists["file"]:
                    return await CallbackQuery.edit_message.text(_["admin_35"])
            except:
                return await CallbackQuery.edit_message_text(_["admin_36"])
            try:
                await CallbackQuery.edit_message_text(_["admin_37"].format(upvote))
            except:
                pass
            command = counter
            mention = "ᴜᴘᴠᴏᴛᴇs"
        else:
            if (
                CallbackQuery.from_user.id
                in upvoters[chat_id][CallbackQuery.message.id]
            ):
                await CallbackQuery.answer(_["admin_38"], show_alert=True)
            else:
                await CallbackQuery.answer(_["admin_39"], show_alert=True)
            upl = InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            text=f"👍 {get_upvotes}",
                            callback_data=f"ADMIN  UpVote|{chat_id}_{counter}",
                        )
                    ]
                ]
            )
            await CallbackQuery.answer(_["admin_40"], show_alert=True)
            return await CallbackQuery.edit_message_reply_markup(reply_markup=upl)
    else:
        is_non_admin = await is_nonadmin_chat(CallbackQuery.message.chat.id)
        if not is_non_admin:
            if CallbackQuery.from_user.id not in SUDOERS:
                admins = adminlist.get(CallbackQuery.message.chat.id)
                if not admins:
                    return await CallbackQuery.answer(_["admin_13"], show_alert=True)
                else:
                    if CallbackQuery.from_user.id not in admins:
                        return await CallbackQuery.answer(
                            _["admin_14"], show_alert=True
                        )
    if command == "Pause":
        if not await is_music_playing(chat_id):
            return await CallbackQuery.answer(_["admin_1"], show_alert=True)
        await CallbackQuery.answer()
        await music_off(chat_id)
        await Swaggy.pause_stream(chat_id)
        await CallbackQuery.message.reply_text(
            _["admin_2"].format(mention), reply_markup=close_markup(_)
        )
    elif command == "Resume":
        if await is_music_playing(chat_id):
            return await CallbackQuery.answer(_["admin_3"], show_alert=True)
        await CallbackQuery.answer()
        await music_on(chat_id)
        await Swaggy.resume_stream(chat_id)
        await CallbackQuery.message.reply_text(
            _["admin_4"].format(mention), reply_markup=close_markup(_)
        )
    elif command == "Stop" or command == "End":
        await CallbackQuery.answer()
        await Swaggy.stop_stream(chat_id)
        await set_loop(chat_id, 0)
        # Reset autoplay for this chat (matches /autoplay help text:
        # "autoplay setting resets when music ended or stopped by someone").
        try:
            await autoplay_off(chat_id)
        except Exception:
            pass
        await CallbackQuery.message.reply_text(
            _["admin_5"].format(mention), reply_markup=close_markup(_)
        )
        await CallbackQuery.message.delete()
    elif command == "AutoPlay":
        # Toggle autoplay for this chat using the DB-backed store (same
        # source of truth as /autoplay command and natural song-end).
        if await is_autoplay_on(chat_id):
            await autoplay_off(chat_id)
            await CallbackQuery.answer("ᴀᴜᴛᴏᴘʟᴀʏ ᴅɪsᴀʙʟᴇᴅ!", show_alert=True)
        else:
            await autoplay_on(chat_id)
            await CallbackQuery.answer("ᴀᴜᴛᴏᴘʟᴀʏ ᴇɴᴀʙʟᴇᴅ!", show_alert=True)
        # Immediately update the button text to reflect the new status,
        # so the user sees ON/OFF without waiting for markup_timer refresh.
        try:
            new_status = await is_autoplay_on(chat_id)
            new_thumb = await is_thumb_on(chat_id)
            await CallbackQuery.edit_message_reply_markup(
                reply_markup=InlineKeyboardMarkup(
                    stream_markup(
                        _,
                        chat_id,
                        autoplay_status=new_status,
                        thumb_status=new_thumb,
                    )
                )
            )
        except Exception:
            pass
    elif command == "Thumbnail":
        # Toggle thumbnail for this chat using the DB-backed store
        # (same pattern as AutoPlay above). When off, the next now-playing
        # message is sent as plain text instead of a photo+caption.
        if await is_thumb_on(chat_id):
            await thumb_off(chat_id)
            await CallbackQuery.answer("ᴛʜᴜᴍʙɴᴀɪʟ ᴅɪsᴀʙʟᴇᴅ", show_alert=True)
        else:
            await thumb_on(chat_id)
            await CallbackQuery.answer("ᴛʜᴜᴍʙɴᴀɪʟ ᴇɴᴀʙʟᴇᴅ", show_alert=True)
        try:
            new_ap = await is_autoplay_on(chat_id)
            new_th = await is_thumb_on(chat_id)
            await CallbackQuery.edit_message_reply_markup(
                reply_markup=InlineKeyboardMarkup(
                    stream_markup(
                        _,
                        chat_id,
                        autoplay_status=new_ap,
                        thumb_status=new_th,
                    )
                )
            )
        except Exception:
            pass
    elif command == "Skip" or command == "Replay":
        check = db.get(chat_id)
        if command == "Skip":
            txt = f"➻ sᴛʀᴇᴀᴍ sᴋɪᴩᴩᴇᴅ 🎄\n│ \n└ʙʏ : {mention} 🥀"
            popped = None
            try:
                popped = check.pop(0)
                if popped:
                    await auto_clean(popped)
                if not check:
                    # Autoplay: try to start a related track before
                    # stopping playback. Uses the same retry helper as
                    # natural song-end so a transient failure doesn't
                    # kill autoplay.
                    if popped and await is_autoplay_on(chat_id):
                        if await Swaggy._try_autoplay_with_retry(
                            chat_id, popped, None
                        ):
                            await CallbackQuery.edit_message_text(txt, reply_markup=close_markup(_))
                            return
                    await CallbackQuery.edit_message_text(
                        f"➻ sᴛʀᴇᴀᴍ sᴋɪᴩᴩᴇᴅ 🎄\n│ \n└ʙʏ : {mention} 🥀"
                    )
                    await CallbackQuery.message.reply_text(
                        text=_["admin_6"].format(
                            mention, CallbackQuery.message.chat.title
                        ),
                        reply_markup=close_markup(_),
                    )
                    try:
                        return await Swaggy.stop_stream(chat_id)
                    except:
                        return
            except:
                try:
                    # Autoplay fallback in the except branch too.
                    if popped and await is_autoplay_on(chat_id):
                        if await Swaggy._try_autoplay_with_retry(
                            chat_id, popped, None
                        ):
                            await CallbackQuery.edit_message_text(txt, reply_markup=close_markup(_))
                            return
                    await CallbackQuery.edit_message_text(
                        f"➻ sᴛʀᴇᴀᴍ sᴋɪᴩᴩᴇᴅ 🎄\n│ \n└ʙʏ : {mention} 🥀"
                    )
                    await CallbackQuery.message.reply_text(
                        text=_["admin_6"].format(
                            mention, CallbackQuery.message.chat.title
                        ),
                        reply_markup=close_markup(_),
                    )
                    return await Swaggy.stop_stream(chat_id)
                except:
                    return
        else:
            txt = f"➻ sᴛʀᴇᴀᴍ ʀᴇ-ᴘʟᴀʏᴇᴅ 🎄\n│ \n└ʙʏ : {mention} 🥀"
        await CallbackQuery.answer()
        queued = check[0]["file"]
        title = (check[0]["title"]).title()
        user = check[0]["by"]
        duration = check[0]["dur"]
        streamtype = check[0]["streamtype"]
        videoid = check[0]["vidid"]
        status = True if str(streamtype) == "video" else None
        db[chat_id][0]["played"] = 0
        exis = (check[0]).get("old_dur")
        if exis:
            db[chat_id][0]["dur"] = exis
            db[chat_id][0]["seconds"] = check[0]["old_second"]
            db[chat_id][0]["speed_path"] = None
            db[chat_id][0]["speed"] = 1.0
        if "live_" in queued:
            n, link = await YouTube.video(videoid, True)
            if n == 0:
                return await CallbackQuery.message.reply_text(
                    text=_["admin_7"].format(title),
                    reply_markup=close_markup(_),
                )
            try:
                image = await YouTube.thumbnail(videoid, True)
            except:
                image = None
            try:
                await Swaggy.skip_stream(chat_id, link, video=status, image=image)
            except:
                return await CallbackQuery.message.reply_text(_["call_6"])
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
                duration,
                user,
            )
            if thumb_on_now:
                img = await get_thumb(
                    videoid,
                    title=title,
                    duration=duration,
                )
                run = await CallbackQuery.message.reply_photo(
                    photo=img,
                    caption=caption,
                    reply_markup=InlineKeyboardMarkup(button),
                )
            else:
                run = await CallbackQuery.message.reply_text(
                    caption,
                    disable_web_page_preview=True,
                    reply_markup=InlineKeyboardMarkup(button),
                )
            db[chat_id][0]["mystic"] = run
            db[chat_id][0]["markup"] = "tg"
            await CallbackQuery.edit_message_text(txt, reply_markup=close_markup(_))
        elif "vid_" in queued:
            mystic = await CallbackQuery.message.reply_text(
                _["call_7"], disable_web_page_preview=True
            )
            try:
                file_path, direct = await YouTube.download(
                    videoid,
                    mystic,
                    videoid=True,
                    video=status,
                )
            except:
                return await mystic.edit_text(_["call_6"])
            try:
                image = await YouTube.thumbnail(videoid, True)
            except:
                image = None
            try:
                await Swaggy.skip_stream(chat_id, file_path, video=status, image=image)
            except:
                return await mystic.edit_text(_["call_6"])
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
                duration,
                user,
            )
            if thumb_on_now:
                img = await get_thumb(
                    videoid,
                    title=title,
                    duration=duration,
                )
                run = await CallbackQuery.message.reply_photo(
                    photo=img,
                    caption=caption,
                    reply_markup=InlineKeyboardMarkup(button),
                )
            else:
                run = await CallbackQuery.message.reply_text(
                    caption,
                    disable_web_page_preview=True,
                    reply_markup=InlineKeyboardMarkup(button),
                )
            db[chat_id][0]["mystic"] = run
            db[chat_id][0]["markup"] = "stream"
            await CallbackQuery.edit_message_text(txt, reply_markup=close_markup(_))
            await mystic.delete()
        elif "index_" in queued:
            try:
                await Swaggy.skip_stream(chat_id, videoid, video=status)
            except:
                return await CallbackQuery.message.reply_text(_["call_6"])
            thumb_on_now = await is_thumb_on(chat_id)
            button = stream_markup(
                _,
                chat_id,
                autoplay_status=await is_autoplay_on(chat_id),
                thumb_status=thumb_on_now,
            )
            caption = _["stream_2"].format(user)
            if thumb_on_now:
                run = await CallbackQuery.message.reply_photo(
                    photo=STREAM_IMG_URL,
                    caption=caption,
                    reply_markup=InlineKeyboardMarkup(button),
                )
            else:
                run = await CallbackQuery.message.reply_text(
                    caption,
                    disable_web_page_preview=True,
                    reply_markup=InlineKeyboardMarkup(button),
                )
            db[chat_id][0]["mystic"] = run
            db[chat_id][0]["markup"] = "tg"
            await CallbackQuery.edit_message_text(txt, reply_markup=close_markup(_))
        else:
            if videoid == "telegram":
                image = None
            elif videoid == "soundcloud":
                image = None
            else:
                try:
                    image = await YouTube.thumbnail(videoid, True)
                except:
                    image = None
            try:
                await Swaggy.skip_stream(chat_id, queued, video=status, image=image)
            except:
                return await CallbackQuery.message.reply_text(_["call_6"])
            if videoid == "telegram":
                thumb_on_now = await is_thumb_on(chat_id)
                button = stream_markup(
                    _,
                    chat_id,
                    autoplay_status=await is_autoplay_on(chat_id),
                    thumb_status=thumb_on_now,
                )
                caption = _["stream_1"].format(
                    config.SUPPORT_CHAT, title[:23], duration, user
                )
                if thumb_on_now:
                    run = await CallbackQuery.message.reply_photo(
                        photo=TELEGRAM_AUDIO_URL
                        if str(streamtype) == "audio"
                        else TELEGRAM_VIDEO_URL,
                        caption=caption,
                        reply_markup=InlineKeyboardMarkup(button),
                    )
                else:
                    run = await CallbackQuery.message.reply_text(
                        caption,
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
                    config.SUPPORT_CHAT, title[:23], duration, user
                )
                if thumb_on_now:
                    run = await CallbackQuery.message.reply_photo(
                        photo=SOUNCLOUD_IMG_URL
                        if str(streamtype) == "audio"
                        else TELEGRAM_VIDEO_URL,
                        caption=caption,
                        reply_markup=InlineKeyboardMarkup(button),
                    )
                else:
                    run = await CallbackQuery.message.reply_text(
                        caption,
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
                    duration,
                    user,
                )
                if thumb_on_now:
                    img = await get_thumb(
                        videoid,
                        title=title,
                        duration=duration,
                    )
                    run = await CallbackQuery.message.reply_photo(
                        photo=img,
                        caption=caption,
                        reply_markup=InlineKeyboardMarkup(button),
                    )
                else:
                    run = await CallbackQuery.message.reply_text(
                        caption,
                        disable_web_page_preview=True,
                        reply_markup=InlineKeyboardMarkup(button),
                    )
                db[chat_id][0]["mystic"] = run
                db[chat_id][0]["markup"] = "stream"
            await CallbackQuery.edit_message_text(txt, reply_markup=close_markup(_))


async def markup_timer():
    while not await asyncio.sleep(7):
        active_chats = await get_active_chats()
        for chat_id in active_chats:
            try:
                if not await is_music_playing(chat_id):
                    continue
                playing = db.get(chat_id)
                if not playing:
                    continue
                duration_seconds = int(playing[0]["seconds"])
                if duration_seconds == 0:
                    continue
                try:
                    mystic = playing[0]["mystic"]
                except:
                    continue
                try:
                    check = checker[chat_id][mystic.id]
                    if check is False:
                        continue
                except:
                    pass
                try:
                    language = await get_lang(chat_id)
                    _ = get_string(language)
                except:
                    _ = get_string("en")
                try:
                    ap_status = await is_autoplay_on(chat_id)
                    th_status = await is_thumb_on(chat_id)
                    buttons = stream_markup_timer(
                        _,
                        chat_id,
                        seconds_to_min(playing[0]["played"]),
                        playing[0]["dur"],
                        autoplay_status=ap_status,
                        thumb_status=th_status,
                    )
                    await mystic.edit_reply_markup(
                        reply_markup=InlineKeyboardMarkup(buttons)
                    )
                except:
                    continue
            except:
                continue


asyncio.create_task(markup_timer())
