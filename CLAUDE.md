# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A Telegram bot for habit tracking built on the Pyrogram framework (MTProto API). Users receive daily reminders to submit proof photos of their habit progress, which are reviewed by an admin.

## Commands

```bash
# Run the bot
python3 -m TelegramBot

# Run all tests
pytest

# Run a single test file
pytest tests/unit/services/test_streak_service.py

# Run a specific test
pytest tests/unit/services/test_streak_service.py::TestStreakService::test_missed_day_resets_streak

# Install dependencies
pip3 install -r requirements.txt
```

## Architecture

### Three-Layer Architecture
The habit tracking features follow a clean separation:
1. **Database Layer** (`database/`) - Raw MongoDB operations via wrapper classes (e.g., `HabitsDB`, `StreaksDB`)
2. **Service Layer** (`services/`) - Business logic that orchestrates database calls (e.g., `StreakService.on_approval()` handles reset checks + increment)
3. **Plugin Layer** (`plugins/`) - Telegram handlers that call services

### Plugin System
Plugins are auto-discovered from `TelegramBot/plugins/` via Pyrogram's smart plugins. Organized by permission level:
- `plugins/users/` - Public commands and handlers (habits, photo submissions)
- `plugins/sudo/` - Elevated commands for SUDO_USERID users (reviews, dbstats)
- `plugins/developer/` - Owner-only commands for OWNER_USERID (broadcast, updater)

### Database Collections
- `users`, `chats` - User/chat data persistence
- `habits` - Habit definitions with notification schedules
- `submissions` - Photo submissions with review status (pending/approved/rejected)
- `streaks` - Streak tracking per user per habit

### Key Database Classes
Each collection has a dedicated wrapper in `database/`:
- `HabitsDB` - CRUD for habits, query by notification time
- `SubmissionsDB` - Create submissions, update status, query pending
- `StreaksDB` - Increment/reset streaks, track longest streak

### Helpers
- `helpers/filters.py` - Custom Pyrogram filters: `dev_cmd`, `sudo_cmd`, `is_ratelimited`
- `helpers/decorators.py` - `@admin_commands`, `@catch_errors`, `@run_sync_in_thread`

## Plugin Template

```python
from TelegramBot.helpers.filters import is_ratelimited
from pyrogram import Client, filters
from pyrogram.types import Message

@Client.on_message(filters.command(["mycommand"]) & is_ratelimited)
async def my_handler(client: Client, message: Message):
    await message.reply_text("Response")
```

## Testing

Tests use `pytest` with `pytest-asyncio` (auto mode). Key fixtures in `tests/conftest.py`:
- `mongo_client`, `mongo_database` - mongomock-motor for in-memory MongoDB
- `habits_collection`, `submissions_collection`, `streaks_collection` - Collection fixtures
- `mock_pyrogram_client`, `mock_message`, `mock_callback_query` - Pyrogram mocks
- Use `freezegun.freeze_time` for date-dependent tests (especially streak logic)

## Environment Variables

Required in `config.env`:
- `API_ID`, `API_HASH` - From my.telegram.org
- `BOT_TOKEN` - From @BotFather
- `OWNER_USERID` - JSON array of owner user IDs
- `MONGO_URI` - MongoDB connection string
- `SUDO_USERID` (optional) - JSON array of sudo user IDs