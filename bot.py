import os
import re
import json
from pathlib import Path

from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ChatPermissions
from pyrogram.enums import ChatMemberStatus
from pyrogram.errors import ChatAdminRequired, UserAdminInvalid, RPCError

API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")
BOT_TOKEN = os.getenv("BOT_TOKEN", "8999750576:AAEHat76G7Dt9hkalIxn0GZX28fZDkPezdE")
OWNER_ID = int(os.getenv("OWNER_ID", "8250224070"))

OWNER_URL = os.getenv("OWNER_URL", "https://t.me/govind_official_mp13")
GROUP_URL = os.getenv("GROUP_URL", "https://t.me/yourgroup")
CHANNEL_URL = os.getenv("CHANNEL_URL", "https://t.me/yourchannel")
BOT_USERNAME = os.getenv("BOT_USERNAME", "").lstrip("@Gp_testingbot")

DATA_FILE = Path("moderation_data.json")

if not all([API_ID, API_HASH, BOT_TOKEN, OWNER_ID]):
    raise RuntimeError(
        "Set API_ID, API_HASH, BOT_TOKEN and OWNER_ID environment variables."
    )

app = Client(
    "group_manager_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)


def load_data():
    try:
        data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
        return {
            "global_bans": {str(x) for x in data.get("global_bans", [])},
            "global_mutes": {str(x) for x in data.get("global_mutes", [])}
        }
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {"global_bans": set(), "global_mutes": set()}


DATA = load_data()


def save_data():
    DATA_FILE.write_text(
        json.dumps({
            "global_bans": sorted(DATA["global_bans"]),
            "global_mutes": sorted(DATA["global_mutes"])
        }, indent=2),
        encoding="utf-8"
    )


def buttons():
    add_url = (
        f"https://t.me/{BOT_USERNAME}?startgroup=true"
        if BOT_USERNAME else "https://t.me/"
    )

    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("👤 Owner", url=OWNER_URL),
            InlineKeyboardButton("➕ Add Me To Your Group", url=add_url)
        ],
        [
            InlineKeyboardButton("📢 Group / Channel", url=GROUP_URL),
            InlineKeyboardButton("📡 Updates Channel", url=CHANNEL_URL)
        ]
    ])


async def is_admin(message):
    if not message.from_user:
        return False

    try:
        member = await app.get_chat_member(
            message.chat.id, message.from_user.id
        )
        return member.status in (
            ChatMemberStatus.OWNER,
            ChatMemberStatus.ADMINISTRATOR
        )
    except RPCError:
        return False


async def command_allowed(message):
    if message.chat.type.value not in ("group", "supergroup"):
        await message.reply_text("⚠️ Ye command group mein use karein.")
        return False

    if not await is_admin(message):
        await message.reply_text(
            "❌ Sirf group admins ye command use kar sakte hain."
        )
        return False

    return True


async def get_target(message):
    if message.reply_to_message and message.reply_to_message.from_user:
        return message.reply_to_message.from_user

    args = (message.text or "").split()
    if len(args) < 2:
        return None

    value = args[1]

    try:
        if value.startswith("@"):
            return await app.get_users(value)

        if re.fullmatch(r"-?\d+", value):
            return await app.get_users(int(value))
    except RPCError:
        return None

    return None


async def reason_from_message(message):
    args = (message.text or "").split(maxsplit=2)

    if message.reply_to_message:
        return args[1] if len(args) > 1 else "No reason provided"

    return args[2] if len(args) > 2 else "No reason provided"


async def mute_user(chat_id, user_id):
    await app.restrict_chat_member(
        chat_id,
        user_id,
        ChatPermissions(
            can_send_messages=False,
            can_send_audios=False,
            can_send_documents=False,
            can_send_photos=False,
            can_send_videos=False,
            can_send_video_notes=False,
            can_send_voice_notes=False,
            can_send_polls=False,
            can_send_other_messages=False,
            can_add_web_page_previews=False
        )
    )


async def unmute_user(chat_id, user_id):
    await app.restrict_chat_member(
        chat_id,
        user_id,
        ChatPermissions(
            can_send_messages=True,
            can_send_audios=True,
            can_send_documents=True,
            can_send_photos=True,
            can_send_videos=True,
            can_send_video_notes=True,
            can_send_voice_notes=True,
            can_send_polls=True,
            can_send_other_messages=True,
            can_add_web_page_previews=True
        )
    )


@app.on_message(filters.command("start"))
async def start_handler(_, message):
    name = message.from_user.first_name if message.from_user else "there"

    await message.reply_text(
        f"👋 Hello {name}!\n\n"
        "🤖 **Telegram Group Management Bot**\n"
        "Mujhe apne group mein add karein aur admin rights dein.\n\n"
        "Commands: `/ban`, `/unban`, `/mute`, `/unmute`, "
        "`/gban`, `/ungban`, `/gmute`, `/ungmute`",
        reply_markup=buttons(),
        disable_web_page_preview=True
    )


@app.on_message(filters.command(["help", "commands"]))
async def help_handler(_, message):
    await message.reply_text(
        "**Moderation Commands**\n\n"
        "`/ban` - User ko group se ban karein\n"
        "`/unban` - Group ban remove karein\n"
        "`/mute` - User ko mute karein\n"
        "`/unmute` - User ka mute remove karein\n"
        "`/gban` - Global ban list mein add karein\n"
        "`/ungban` - Global ban list se remove karein\n"
        "`/gmute` - Global mute list mein add karein\n"
        "`/ungmute` - Global mute list se remove karein\n"
        "`/id` - User aur chat ID dekhein\n\n"
        "User ke message par reply karein ya @username dein.",
        reply_markup=buttons()
    )


@app.on_message(filters.command([
    "ban", "unban", "mute", "unmute",
    "gban", "ungban", "gmute", "ungmute"
]))
async def moderation_handler(_, message):
    command = message.command[0].lower()

    if not await command_allowed(message):
        return

    target = await get_target(message)

    if not target:
        await message.reply_text(
            "⚠️ User ke message par reply karein ya @username dein.\n"
            "Example: `/ban @username spam`"
        )
        return

    if target.is_bot:
        await message.reply_text("❌ Bot accounts ko moderate nahi kar sakte.")
        return

    if message.from_user and target.id == message.from_user.id:
        await message.reply_text("❌ Aap khud par ye action nahi kar sakte.")
        return

    reason = await reason_from_message(message)

    try:
        if command == "ban":
            await app.ban_chat_member(message.chat.id, target.id)
            result = f"🔨 {target.mention} ko group se ban kar diya."

        elif command == "unban":
            await app.unban_chat_member(
                message.chat.id, target.id, only_if_banned=True
            )
            result = f"✅ {target.mention} ka group ban remove kar diya."

        elif command == "mute":
            await mute_user(message.chat.id, target.id)
            result = f"🔇 {target.mention} ko mute kar diya."

        elif command == "unmute":
            await unmute_user(message.chat.id, target.id)
            result = f"🔊 {target.mention} ka mute remove kar diya."

        elif command == "gban":
            DATA["global_bans"].add(str(target.id))
            save_data()
            await app.ban_chat_member(message.chat.id, target.id)
            result = f"🌍 {target.mention} global ban list mein add hua."

        elif command == "ungban":
            DATA["global_bans"].discard(str(target.id))
            save_data()
            result = (
                f"✅ {target.mention} global ban list se remove hua. "
                "Existing group ban ke liye /unban chalayein."
            )

        elif command == "gmute":
            DATA["global_mutes"].add(str(target.id))
            save_data()
            await mute_user(message.chat.id, target.id)
            result = f"🌍🔇 {target.mention} global mute."

        else:
            DATA["global_mutes"].discard(str(target.id))
            save_data()
            result = (
                f"🔊 {target.mention} global mute list se remove hua. "
                "Current group mein /unmute bhi chalayein."
            )

        await message.reply_text(
            f"{result}\n\n📝 Reason: {reason}"
        )

    except (ChatAdminRequired, UserAdminInvalid):
        await message.reply_text(
            "❌ Bot ko admin banayein aur Ban Users / Restrict Members "
            "permissions dein."
        )
    except RPCError as error:
        await message.reply_text(
            f"❌ Telegram error: {error.__class__.__name__}"
        )


@app.on_message(filters.group & ~filters.service, group=1)
async def enforce_global_lists(_, message):
    if not message.from_user:
        return

    user_id = str(message.from_user.id)

    try:
        if user_id in DATA["global_bans"]:
            await app.ban_chat_member(
                message.chat.id, message.from_user.id
            )
            return

        if user_id in DATA["global_mutes"]:
            await message.delete()

    except RPCError:
        pass


@app.on_message(filters.new_chat_members, group=2)
async def check_new_members(_, message):
    for user in message.new_chat_members:
        try:
            if str(user.id) in DATA["global_bans"]:
                await app.ban_chat_member(message.chat.id, user.id)
        except RPCError:
            pass


@app.on_message(filters.command("id"))
async def id_handler(_, message):
    if message.reply_to_message and message.reply_to_message.from_user:
        await message.reply_text(
            f"User ID: `{message.reply_to_message.from_user.id}`\n"
            f"Chat ID: `{message.chat.id}`"
        )
    else:
        user_id = message.from_user.id if message.from_user else "unknown"
        await message.reply_text(
            f"Your ID: `{user_id}`\nChat ID: `{message.chat.id}`"
        )


if __name__ == "__main__":
    print("Group Manager Bot (MongoDB) is running...")
    app.run()
