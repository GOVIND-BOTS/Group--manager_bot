import re
import json
from pathlib import Path
from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.enums import ChatMemberStatus
from pyrogram.errors import RPCError, ChatAdminRequired, UserAdminInvalid, FloodWait
import asyncio

# Data files
WARN_DATA_FILE = Path("bio_warns.json")
NOTIFIED_FILE = Path("bio_notified.json")   # jis user ko 1 baar already bata diya
WARN_LIMIT = 6

# Telegram group/channel invite / public links
LINK_PATTERN = re.compile(
    r"(?:https?://)?(?:t\.me|telegram\.me|telegram\.dog)/(?:joinchat/|\+|[\w\d_]+)",
    re.IGNORECASE
)

def load_json(file: Path):
    try:
        return json.loads(file.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}

def save_json(file: Path, data):
    file.write_text(json.dumps(data, indent=2), encoding="utf-8")

WARNS = load_json(WARN_DATA_FILE)          # {chat_id: {user_id: count}}
NOTIFIED = load_json(NOTIFIED_FILE)        # {chat_id: [user_id, ...]}

def get_warn_count(chat_id: int, user_id: int) -> int:
    return WARNS.get(str(chat_id), {}).get(str(user_id), 0)

def add_warn(chat_id: int, user_id: int) -> int:
    chat_key = str(chat_id)
    user_key = str(user_id)
    if chat_key not in WARNS:
        WARNS[chat_key] = {}
    WARNS[chat_key][user_key] = WARNS[chat_key].get(user_key, 0) + 1
    save_json(WARN_DATA_FILE, WARNS)
    return WARNS[chat_key][user_key]

def reset_warn(chat_id: int, user_id: int):
    chat_key = str(chat_id)
    user_key = str(user_id)
    if chat_key in WARNS and user_key in WARNS[chat_key]:
        del WARNS[chat_key][user_key]
        if not WARNS[chat_key]:
            del WARNS[chat_key]
        save_json(WARN_DATA_FILE, WARNS)

def is_already_notified(chat_id: int, user_id: int) -> bool:
    return str(user_id) in NOTIFIED.get(str(chat_id), [])

def mark_notified(chat_id: int, user_id: int):
    chat_key = str(chat_id)
    user_key = str(user_id)
    if chat_key not in NOTIFIED:
        NOTIFIED[chat_key] = []
    if user_key not in NOTIFIED[chat_key]:
        NOTIFIED[chat_key].append(user_key)
        save_json(NOTIFIED_FILE, NOTIFIED)

async def is_user_admin(client: Client, chat_id: int, user_id: int) -> bool:
    try:
        member = await client.get_chat_member(chat_id, user_id)
        return member.status in (ChatMemberStatus.OWNER, ChatMemberStatus.ADMINISTRATOR)
    except RPCError:
        return False

async def has_group_or_channel_link_in_bio(client: Client, user_id: int) -> bool:
    """User ke bio mein Telegram group/channel link hai ya nahi"""
    try:
        user = await client.get_users(user_id)
        bio = getattr(user, "bio", None) or ""
        if not bio:
            try:
                chat = await client.get_chat(user_id)
                bio = getattr(chat, "bio", None) or getattr(chat, "description", None) or ""
            except Exception:
                pass
        if bio and LINK_PATTERN.search(str(bio)):
            return True
    except RPCError:
        pass
    return False

def register_bio_link_handlers(app: Client):
    """
    bot.py mein yeh call karo:
        from bio_link_warn import register_bio_link_handlers
        register_bio_link_handlers(app)
    """

    # ========== 1. Message aate hi check (pehle wala feature) ==========
    @app.on_message(filters.group & ~filters.service & ~filters.bot, group=5)
    async def check_bio_link_and_warn(client: Client, message: Message):
        if not message.from_user:
            return

        user = message.from_user
        chat_id = message.chat.id
        user_id = user.id

        # Admins skip
        if await is_user_admin(client, chat_id, user_id):
            return

        # Bio mein link hai?
        if not await has_group_or_channel_link_in_bio(client, user_id):
            return

        # Warn increment
        current_warns = add_warn(chat_id, user_id)

        try:
            if current_warns >= WARN_LIMIT:
                await client.ban_chat_member(chat_id, user_id)
                reset_warn(chat_id, user_id)
                await message.reply_text(
                    f"🚫 {user.mention} ko **ban** kar diya gaya.\n"
                    f"Kyunki unke bio mein group/channel link tha aur warn limit ({WARN_LIMIT}) cross ho gayi."
                )
            else:
                remaining = WARN_LIMIT - current_warns
                await message.reply_text(
                    f"⚠️ {user.mention} **Warning** [{current_warns}/{WARN_LIMIT}]\n\n"
                    f"Aapke bio mein Telegram group/channel ka link hai.\n"
                    f"Please bio se link hata do, warna {remaining} warning ke baad ban ho jaoge."
                )
        except (ChatAdminRequired, UserAdminInvalid):
            await message.reply_text(
                "❌ Bot ko admin banao aur **Ban Users** permission do."
            )
        except RPCError:
            pass

    # ========== 2. Admin command: Group ke members scan karke 1 baar tag karo ==========
    @app.on_message(filters.command("scanbio") & filters.group)
    async def scan_bio_command(client: Client, message: Message):
        if not await is_user_admin(client, message.chat.id, message.from_user.id):
            await message.reply_text("❌ Sirf admins use kar sakte hain.")
            return

        status_msg = await message.reply_text("🔍 Members scan kar raha hoon... thoda time lagega.")

        chat_id = message.chat.id
        notified_count = 0
        checked = 0

        try:
            async for member in client.get_chat_members(chat_id):
                user = member.user
                if not user or user.is_bot:
                    continue

                # Admins skip
                if member.status in (ChatMemberStatus.OWNER, ChatMemberStatus.ADMINISTRATOR):
                    continue

                checked += 1

                # Pehle se notify kiya hua hai toh skip
                if is_already_notified(chat_id, user.id):
                    continue

                # Bio check
                if await has_group_or_channel_link_in_bio(client, user.id):
                    try:
                        await client.send_message(
                            chat_id,
                            f"⚠️ {user.mention}\n\n"
                            f"Aapke **bio** mein Telegram group/channel ka link hai.\n"
                            f"Kripya bio se link hata den, warna aage warning / ban ho sakta hai."
                        )
                        mark_notified(chat_id, user.id)
                        notified_count += 1
                        await asyncio.sleep(1.5)  # flood wait se bachne ke liye
                    except FloodWait as e:
                        await asyncio.sleep(e.value + 1)
                    except RPCError:
                        pass

                # Bahut bade groups mein thoda break
                if checked % 50 == 0:
                    await asyncio.sleep(1)

        except Exception as e:
            await status_msg.edit_text(f"❌ Scan mein error aaya: {e}")
            return

        await status_msg.edit_text(
            f"✅ Scan complete!\n\n"
            f"• Checked: {checked} members\n"
            f"• Bio mein link wale (1st time notify): {notified_count}"
        )

    # ========== 3. Warns reset command ==========
    @app.on_message(filters.command("resetbiowarn") & filters.group)
    async def reset_bio_warn_cmd(client: Client, message: Message):
        if not await is_user_admin(client, message.chat.id, message.from_user.id):
            await message.reply_text("❌ Sirf admins use kar sakte hain.")
            return

        if not message.reply_to_message or not message.reply_to_message.from_user:
            await message.reply_text("⚠️ Kisi user ke message pe reply karke `/resetbiowarn` bhejo.")
            return

        target = message.reply_to_message.from_user
        reset_warn(message.chat.id, target.id)
        await message.reply_text(f"✅ {target.mention} ke bio-link warns reset kar diye.")
