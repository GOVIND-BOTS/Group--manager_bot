import os
import re
import asyncio
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ChatPermissions
from pyrogram.enums import ChatMemberStatus
from pymongo import MongoClient
from pyrogram.errors import (
    UserNotParticipant, ChatAdminRequired, UserAdminInvalid,
    PeerIdInvalid, RPCError
)

API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
MONGO_URI = os.getenv("MONGO_URI", "")
OWNER_ID = int(os.getenv("OWNER_ID", "0"))

OWNER_URL = os.getenv("OWNER_URL", "https://t.me/yourusername")
GROUP_URL = os.getenv("GROUP_URL", "https://t.me/yourgroup")
CHANNEL_URL = os.getenv("CHANNEL_URL", "https://t.me/yourchannel")
BOT_USERNAME = os.getenv("BOT_USERNAME", "").lstrip("@")

if not all([API_ID, API_HASH, BOT_TOKEN, MONGO_URI, OWNER_ID]):
    raise RuntimeError("Set API_ID, API_HASH, BOT_TOKEN, MONGO_URI and OWNER_ID environment variables.")

app = Client("group_manager_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
mongo = MongoClient(MONGO_URI)
db = mongo["telegram_group_manager"]
global_bans = db["global_bans"]
global_mutes = db["global_mutes"]

def buttons():
    username = BOT_USERNAME
    add_url = f"https://t.me/{username}?startgroup=true" if username else "https://t.me/"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("👤 Owner", url=OWNER_URL),
         InlineKeyboardButton("➕ Add Me To Your Group", url=add_url)],
        [InlineKeyboardButton("📢 Group / Channel", url=GROUP_URL),
         InlineKeyboardButton("📡 Updates Channel", url=CHANNEL_URL)]
    ])

async def is_admin(message):
    if not message.from_user:
        return False
    try:
        member = await app.get_chat_member(message.chat.id, message.from_user.id)
        return member.status in (ChatMemberStatus.OWNER, ChatMemberStatus.ADMINISTRATOR)
    except RPCError:
        return False

async def get_target(message, arg_index=1):
    if message.reply_to_message and message.reply_to_message.from_user:
        return message.reply_to_message.from_user
    args = (message.text or "").split()
    if len(args) <= arg_index:
        return None
    value = args[arg_index]
    try:
        if value.startswith("@"):
            return await app.get_users(value)
        if re.fullmatch(r"-?\d+", value):
            return await app.get_users(int(value))
    except RPCError:
        return None
    return None

async def command_allowed(message):
    if message.chat.type.value not in ("group", "supergroup"):
        await message.reply_text("⚠️ Ye command group mein use karein.")
        return False
    if not await is_admin(message):
        await message.reply_text("❌ Sirf group admins ye command use kar sakte hain.")
        return False
    return True

async def get_reason(message, target):
    parts = (message.text or "").split(maxsplit=2)
    if message.reply_to_message:
        return parts[1] if len(parts) > 1 else "No reason provided"
    return parts[2] if len(parts) > 2 else "No reason provided"

@app.on_message(filters.command("start"))
async def start_handler(_, message):
    name = message.from_user.first_name if message.from_user else "there"
    await message.reply_text(
        f"👋 Hello {name}!\n\n"
        "🤖 **Telegram Group Management Bot**\n"
        "Group moderation ke liye mujhe group mein add karein aur admin rights dein.\n\n"
        "Commands: `/ban`, `/unban`, `/mute`, `/unmute`, `/gban`, `/ungban`, `/gmute`, `/ungmute`",
        reply_markup=buttons(),
        disable_web_page_preview=True
    )

@app.on_message(filters.command(["help", "commands"]))
async def help_handler(_, message):
    await message.reply_text(
        "**Moderation commands** (reply to a user or provide @username/user ID):\n\n"
        "`/ban [user] [reason]` — group se ban\n"
        "`/unban [user]` — group ban remove\n"
        "`/mute [user] [reason]` — group mein mute\n"
        "`/unmute [user]` — group mute remove\n"
        "`/gban [user] [reason]` — global ban (bot ke managed groups mein)\n"
        "`/ungban [user]` — global ban list se remove\n"
        "`/gmute [user] [reason]` — global mute (bot ke managed groups mein)\n"
        "`/ungmute [user]` — global mute list se remove\n\n"
        "Commands chalane ke liye bot ko admin banayein, aur Ban Users / Restrict Members permission dein.",
        reply_markup=buttons()
    )

@app.on_message(filters.command(["ban", "unban", "mute", "unmute", "gban", "ungban", "gmute", "ungmute"]))
async def moderation_handler(_, message):
    command = message.command[0].lower()
    if not await command_allowed(message):
        return
    target = await get_target(message)
    if not target:
        await message.reply_text("⚠️ User ko reply karein ya command ke baad @username / user ID dein.\nExample: `/ban @username spam`")
        return
    if target.is_bot:
        await message.reply_text("❌ Bot account ko moderate nahi kar sakte.")
        return
    if message.from_user and target.id == message.from_user.id:
        await message.reply_text("❌ Aap khud par ye action nahi kar sakte.")
        return

    reason = await get_reason(message, target)
    try:
        if command == "ban":
            await app.ban_chat_member(message.chat.id, target.id)
            result = f"🔨 {target.mention} ko group se ban kar diya."
        elif command == "unban":
            await app.unban_chat_member(message.chat.id, target.id, only_if_banned=True)
            result = f"✅ {target.mention} ka group ban remove kar diya."
        elif command == "mute":
            await app.restrict_chat_member(
                message.chat.id, target.id,
                ChatPermissions(can_send_messages=False, can_send_audios=False,
                                can_send_documents=False, can_send_photos=False,
                                can_send_videos=False, can_send_video_notes=False,
                                can_send_voice_notes=False, can_send_polls=False,
                                can_send_other_messages=False, can_add_web_page_previews=False)
            )
            result = f"🔇 {target.mention} ko group mein mute kar diya."
        elif command == "unmute":
            await app.restrict_chat_member(
                message.chat.id, target.id,
                ChatPermissions(can_send_messages=True, can_send_audios=True,
                                can_send_documents=True, can_send_photos=True,
                                can_send_videos=True, can_send_video_notes=True,
                                can_send_voice_notes=True, can_send_polls=True,
                                can_send_other_messages=True, can_add_web_page_previews=True)
            )
            result = f"🔊 {target.mention} ka mute remove kar diya."
        elif command == "gban":
            global_bans.update_one({"_id": target.id}, {"$set": {"name": target.first_name, "reason": reason}}, upsert=True)
            await app.ban_chat_member(message.chat.id, target.id)
            result = f"🌍 {target.mention} ko global ban list mein add kiya aur is group se ban kiya."
        elif command == "ungban":
            global_bans.delete_one({"_id": target.id})
            result = f"✅ {target.mention} ko global ban list se remove kiya. Existing group bans ko `/unban` se remove karein."
        elif command == "gmute":
            global_mutes.update_one({"_id": target.id}, {"$set": {"name": target.first_name, "reason": reason}}, upsert=True)
            await app.restrict_chat_member(
                message.chat.id, target.id,
                ChatPermissions(can_send_messages=False, can_send_audios=False,
                                can_send_documents=False, can_send_photos=False,
                                can_send_videos=False, can_send_video_notes=False,
                                can_send_voice_notes=False, can_send_polls=False,
                                can_send_other_messages=False, can_add_web_page_previews=False)
            )
            result = f"🌍🔇 {target.mention} ko global mute list mein add kiya aur is group mein mute kiya."
        else:
            global_mutes.delete_one({"_id": target.id})
            result = f"🔊 {target.mention} ko global mute list se remove kiya. Current group mein `/unmute` bhi chalayein."
        await message.reply_text(result + f"\n\n📝 Reason: {reason}")
    except (ChatAdminRequired, UserAdminInvalid):
        await message.reply_text("❌ Bot ko admin banayein aur Ban Users / Restrict Members permissions dein.")
    except RPCError as e:
        await message.reply_text(f"❌ Telegram error: {e.__class__.__name__}")

@app.on_message(filters.group & ~filters.service, group=1)
async def enforce_global_lists(_, message):
    if not message.from_user:
        return
    user_id = message.from_user.id
    try:
        if global_bans.find_one({"_id": user_id}):
            await app.ban_chat_member(message.chat.id, user_id)
            return
        if global_mutes.find_one({"_id": user_id}):
            await message.delete()
    except (ChatAdminRequired, UserAdminInvalid, RPCError):
        pass

@app.on_message(filters.new_chat_members, group=2)
async def check_new_members(_, message):
    for user in message.new_chat_members:
        try:
            if global_bans.find_one({"_id": user.id}):
                await app.ban_chat_member(message.chat.id, user.id)
        except RPCError:
            pass

@app.on_message(filters.command("id"))
async def id_handler(_, message):
    if message.reply_to_message and message.reply_to_message.from_user:
        await message.reply_text(f"User ID: `{message.reply_to_message.from_user.id}`\nChat ID: `{message.chat.id}`")
    else:
        user_id = message.from_user.id if message.from_user else "unknown"
        await message.reply_text(f"Your ID: `{user_id}`\nChat ID: `{message.chat.id}`")

if __name__ == "__main__":
    print("Group Manager Bot is running...")
    app.run()
