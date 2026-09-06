import random

from pyrogram import filters
from pyrogram.types import ChatPermissions, ChatPrivileges

from SWAGGYMUSIC import app
from SWAGGYMUSIC.misc import SUDOERS
from SWAGGYMUSIC.utils.Swaggy_BAN import admin_filter


Yumikoo_text = [
    "hey please don't disturb me.",
    "who are you",
    "aap kon ho",
    "aap mere owner to nhi lgte",
    "hey tum mera name kyu le rhe ho meko sone do",
    "ha bolo kya kaam hai",
    "dekho abhi mai busy hu",
    "hey i am busy",
    "aapko smj nhi aata kya",
    "leave me alone",
    "dude what happend",
]


strict_txt = [
    "i can't restrict against my besties",
    "are you serious? i am not going to restrict my friends",
    "hey, apne dost ko kyun restrict karu?",
    "i can't, this is my closest friend",
    "i love him, please don't restrict this user",
]


ban = ["ban", "boom"]
unban = ["unban"]

mute = ["mute", "silent", "shut"]
unmute = ["unmute", "speak", "free"]

kick = ["kick", "out", "nikaal", "nikal"]

promote = ["promote", "adminship"]
fullpromote = ["fullpromote", "fulladmin"]

demote = ["demote", "lelo"]


# =========================================================
# COMMAND FILTER
# Swaggy + Mystical
# =========================================================

command_filter = (
    filters.command(["waggy"], prefixes=["S"])
    | filters.command(["ystical"], prefixes=["M"])
)


# =========================================================
# NORMAL RANDOM REPLY
# ANY MEMBER CAN USE:
# Swaggy
# Mystical
# =========================================================

@app.on_message(command_filter)
async def random_reply_handler(_, message):

    if not message.text:
        return

    parts = message.text.split()

    # Only command without action
    if len(parts) == 1:
        return await message.reply(
            random.choice(Yumikoo_text)
        )


# =========================================================
# ADMIN MODERATION COMMANDS
# ONLY ADMINS CAN USE:
#
# Swaggy ban
# Mystical ban
# Swaggy mute
# Mystical mute
# etc.
#
# Must reply to target user's message
# =========================================================

@app.on_message(command_filter & admin_filter)
async def restriction_app(_, message):

    if not message.text:
        return

    parts = message.text.split()

    # No action -> handled by random_reply_handler
    if len(parts) < 2:
        return

    reply = message.reply_to_message

    if not reply or not reply.from_user:
        return await message.reply(
            "Kisi user ke message ko reply karke command use karo."
        )

    chat_id = message.chat.id
    user_id = reply.from_user.id

    command_args = message.text.split(
        maxsplit=1
    )[1].lower()

    data = command_args.split()


    # =====================================================
    # BAN
    # =====================================================

    if any(word in ban for word in data):

        if user_id in SUDOERS:
            return await message.reply(
                random.choice(strict_txt)
            )

        await app.ban_chat_member(
            chat_id,
            user_id
        )

        return await message.reply(
            "User ko ban kar diya."
        )


    # =====================================================
    # UNBAN
    # =====================================================

    if any(word in unban for word in data):

        await app.unban_chat_member(
            chat_id,
            user_id
        )

        return await message.reply(
            "User ko unban kar diya."
        )


    # =====================================================
    # KICK
    # =====================================================

    if any(word in kick for word in data):

        if user_id in SUDOERS:
            return await message.reply(
                random.choice(strict_txt)
            )

        # Telegram kick:
        # temporarily ban then immediately unban
        await app.ban_chat_member(
            chat_id,
            user_id
        )

        await app.unban_chat_member(
            chat_id,
            user_id
        )

        return await message.reply(
            "User ko group se kick kar diya."
        )


    # =====================================================
    # MUTE
    # =====================================================

    if any(word in mute for word in data):

        if user_id in SUDOERS:
            return await message.reply(
                random.choice(strict_txt)
            )

        permissions = ChatPermissions(
            can_send_messages=False
        )

        await message.chat.restrict_member(
            user_id,
            permissions
        )

        return await message.reply(
            "User ko mute kar diya."
        )


    # =====================================================
    # UNMUTE
    # =====================================================

    if any(word in unmute for word in data):

        permissions = ChatPermissions(
            can_send_messages=True,
            can_send_media_messages=True,
            can_send_other_messages=True,
            can_add_web_page_previews=True,
        )

        await message.chat.restrict_member(
            user_id,
            permissions
        )

        return await message.reply(
            "User ko unmute kar diya."
        )


    # =====================================================
    # PROMOTE
    # =====================================================

    if any(word in promote for word in data):

        await app.promote_chat_member(
            chat_id,
            user_id,
            privileges=ChatPrivileges(
                can_change_info=False,
                can_invite_users=True,
                can_delete_messages=True,
                can_restrict_members=False,
                can_pin_messages=True,
                can_promote_members=False,
                can_manage_chat=True,
                can_manage_video_chats=True,
            )
        )

        return await message.reply(
            "User ko promote kar diya."
        )


    # =====================================================
    # FULL PROMOTE
    # =====================================================

    if any(word in fullpromote for word in data):

        await app.promote_chat_member(
            chat_id,
            user_id,
            privileges=ChatPrivileges(
                can_change_info=True,
                can_invite_users=True,
                can_delete_messages=True,
                can_restrict_members=True,
                can_pin_messages=True,
                can_promote_members=True,
                can_manage_chat=True,
                can_manage_video_chats=True,
            )
        )

        return await message.reply(
            "User ko full admin promote kar diya."
        )


    # =====================================================
    # DEMOTE
    # =====================================================

    if any(word in demote for word in data):

        await app.promote_chat_member(
            chat_id,
            user_id,
            privileges=ChatPrivileges(
                can_change_info=False,
                can_invite_users=False,
                can_delete_messages=False,
                can_restrict_members=False,
                can_pin_messages=False,
                can_promote_members=False,
                can_manage_chat=False,
                can_manage_video_chats=False,
            )
        )

        return await message.reply(
            "User ko demote kar diya."
        )


    return await message.reply(
        "Ye command samajh nahi aayi."
    )
