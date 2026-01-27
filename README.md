# Habit Tracking Bot

A Telegram bot for habit tracking built on the Pyrogram framework (MTProto API). Users receive daily reminders to submit proof photos of their habit progress, which are reviewed by an admin.

## Features

- Fully asynchronous code using Pyrogram, httpx, aiofiles, and MongoDB motor
- Pluggable plugin architecture for easy extension
- Rate limiting using the leaky bucket algorithm
- MongoDB support for user and chat data persistence

## Setup

### Prerequisites

- Python 3.9+
- MongoDB instance
- Telegram API credentials from [my.telegram.org](https://my.telegram.org)
- Bot token from [@BotFather](https://t.me/botfather)

### Installation

```bash
git clone <repository-url>
cd motivation-bot
pip3 install -r requirements.txt
```

### Configuration

Create a `config.env` file with the following variables:

```env
API_ID=your_api_id
API_HASH=your_api_hash
BOT_TOKEN=your_bot_token
OWNER_USERID=[123456789]
MONGO_URI=mongodb://localhost:27017
SUDO_USERID=[123456789]  # optional
```

### Running

```bash
python3 -m TelegramBot
# or
bash start
```

### Docker

```bash
docker-compose up --build
```

## Commands

### User Commands
- `/start` - Start the bot

### Sudo Commands
- `/dbstats` - Get database statistics
- `/log` - Get the bot log file

### Developer Commands
- `/update` - Update bot from repository
- `/broadcast` - Broadcast message to users and chats

## Project Structure

```
├── Dockerfile
├── README.md
├── config.env
├── requirements.txt
├── TelegramBot
│   ├── __init__.py          # Bot initialization
│   ├── __main__.py          # Entry point
│   ├── config.py            # Environment variables
│   ├── logging.py           # Logging configuration
│   ├── version.py           # Version info
│   │
│   ├── database
│   │   ├── database.py      # High-level database functions
│   │   └── MongoDb.py       # MongoDB CRUD operations
│   │
│   ├── helpers
│   │   ├── filters.py       # Custom Pyrogram filters
│   │   ├── decorators.py    # Python decorators
│   │   ├── ratelimiter.py   # Rate limiting
│   │   └── functions.py     # Utility functions
│   │
│   └── plugins
│       ├── developer
│       │   ├── broadcast.py
│       │   └── updater.py
│       ├── sudo
│       │   ├── dbstats.py
│       │   └── log.py
│       └── users
│           └── start.py
│
└── start                     # Bash script to start the bot
```

## Plugin Template

```python
from TelegramBot.helpers.filters import is_ratelimited
from pyrogram import Client, filters
from pyrogram.types import Message

@Client.on_message(filters.command(["mycommand"]) & is_ratelimited)
async def my_handler(client: Client, message: Message):
    await message.reply_text("Response")
```

## Based On

This project is built on the [Telegram-Bot-Boilerplate](https://github.com/sanjit-sinha/Telegram-Bot-Boilerplate) by Sanjit Sinha.
