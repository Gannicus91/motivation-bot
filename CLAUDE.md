# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A Telegram bot for habit tracking built on the Pyrogram framework (MTProto API). Users receive daily reminders to submit proof photos of their habit progress, which are reviewed by an admin.

## Commands

```bash
# Run the bot
python3 -m TelegramBot
# or
bash start

# Install dependencies
pip3 install -r requirements.txt

# Docker
docker-compose up --build
```

## Architecture

### Entry Point & Initialization
- `TelegramBot/__init__.py` - Bot initialization: sets up uvloop, validates MongoDB connection, creates Pyrogram client with plugin autoloading
- `TelegramBot/__main__.py` - Entry point that starts the bot
- `TelegramBot/config.py` - Environment variables loaded from `config.env`

### Plugin System
Plugins are auto-discovered from `TelegramBot/plugins/` via Pyrogram's smart plugins. Organized by permission level:
- `plugins/users/` - Public commands (start, ping, paste)
- `plugins/sudo/` - Elevated commands for SUDO_USERID users (speedtest, serverstats, dbstats)
- `plugins/developer/` - Owner-only commands for OWNER_USERID (shell, broadcast, updater)

### Database Layer
- `database/MongoDb.py` - MongoDB wrapper class with CRUD operations using motor (async driver)
- `database/database.py` - High-level functions for saving users/chats
- Collections: `users`, `chats` in database `TelegramBot`

### Helpers
- `helpers/filters.py` - Custom Pyrogram filters: `dev_cmd`, `sudo_cmd`, `is_ratelimited`
- `helpers/decorators.py` - `@admin_commands`, `@catch_errors`, `@run_sync_in_thread`
- `helpers/ratelimiter.py` - Rate limiting using pyrate_limiter (leaky bucket algorithm)
- `helpers/functions.py` - Utility functions (`isAdmin`, `get_readable_time`, `get_readable_bytes`)

## Plugin Template

```python
from TelegramBot.helpers.filters import is_ratelimited
from pyrogram import Client, filters
from pyrogram.types import Message

@Client.on_message(filters.command(["mycommand"]) & is_ratelimited)
async def my_handler(client: Client, message: Message):
    await message.reply_text("Response")
```

## Environment Variables

Required in `config.env`:
- `API_ID`, `API_HASH` - From my.telegram.org
- `BOT_TOKEN` - From @BotFather
- `OWNER_USERID` - JSON array of owner user IDs
- `MONGO_URI` - MongoDB connection string
- `SUDO_USERID` (optional) - JSON array of sudo user IDs