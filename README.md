# Telegram Group Management Bot

## Features
- `/start` works in private chat and groups, with Owner, Add Me To Your Group, Group/Channel and Updates buttons.
- Group moderation: `/ban`, `/unban`, `/mute`, `/unmute`
- Global moderation list: `/gban`, `/ungban`, `/gmute`, `/ungmute`
- `/help`, `/commands`, `/id`
- MongoDB stores global ban/mute lists persistently.

## Environment variables
Set the variables from `.env.example` in your hosting provider. Do not commit real tokens or MongoDB credentials.

## Setup
1. Create a bot with @BotFather and copy its token.
2. Get `API_ID` and `API_HASH` from https://my.telegram.org.
3. Create a MongoDB Atlas database and copy its connection URI.
4. Set all environment variables from `.env.example`.
5. Install dependencies with `pip install -r requirements.txt`.
6. Run `python bot.py`.

## Deploy
- Render: create a Background Worker, connect this project/repository, build command `pip install -r requirements.txt`, start command `python bot.py`, and add environment variables.
- VPS: `pip install -r requirements.txt`, set environment variables, then run `python bot.py` (recommended: use systemd or tmux).
- Heroku: deploy with the included `Procfile` and set the same config vars. Heroku dynos use ephemeral local storage, so MongoDB is used for persistent global lists.

## Telegram permissions
Add the bot to your group and promote it to admin. Enable **Ban Users** and **Restrict Members**. For best results, disable privacy mode in @BotFather if you want the bot to inspect ordinary group messages for global mute enforcement.

## Command usage
Reply to a user's message with `/ban`, `/mute`, etc., or use `/ban @username reason`.
For numeric user IDs, the target user must be known to the bot (for example, they interacted with it) or Telegram may return `PeerIdInvalid`.

## Important notes
- Global actions apply only to groups where the bot is present and has the required admin permissions; Telegram bots cannot globally ban a user from every Telegram group.
- `/ungban` and `/ungmute` remove the user from the global list. Existing bans/mutes in each group may still need `/unban` or `/unmute`.
- Replace the default owner/group/channel URLs with your actual links.
