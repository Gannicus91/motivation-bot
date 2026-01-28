"""
User habit management commands.

Commands:
- /add_habit <name> [time] - Create a new habit
- /my_habits - List active habits
- /progress - Show streak statistics
- /delete_habit <id> - Deactivate a habit
"""

import re
from bson import ObjectId
from pyrogram import Client, filters
from pyrogram.types import Message

from TelegramBot.helpers.filters import is_ratelimited
from TelegramBot.database.habits import HabitsDB
from TelegramBot.database.streaks import StreaksDB


# Default notification time if not specified
DEFAULT_NOTIFICATION_TIME = "09:00"
DEFAULT_TIMEZONE = "UTC"


async def add_habit_handler(
    client: Client,
    message: Message,
    habits_db: HabitsDB
) -> None:
    """
    Handle /add_habit command.
    Usage: /add_habit <name> [notification_time]

    Examples:
        /add_habit Morning Exercise
        /add_habit Reading 20:00
    """
    command_parts = message.command[1:] if len(message.command) > 1 else []

    if not command_parts:
        await message.reply_text(
            "Usage: /add_habit <habit name> [notification time]\n\n"
            "Examples:\n"
            "  /add_habit Morning Exercise\n"
            "  /add_habit Reading 20:00"
        )
        return

    # Check if last part is a time (HH:MM format)
    time_pattern = re.compile(r"^\d{2}:\d{2}$")
    notification_time = DEFAULT_NOTIFICATION_TIME

    if time_pattern.match(command_parts[-1]):
        notification_time = command_parts[-1]
        name_parts = command_parts[:-1]
    else:
        name_parts = command_parts

    if not name_parts:
        await message.reply_text(
            "Please provide a habit name.\n"
            "Usage: /add_habit <habit name> [notification time]"
        )
        return

    habit_name = " ".join(name_parts)
    user_id = message.from_user.id

    habit_id = await habits_db.create_habit(
        user_id=user_id,
        name=habit_name,
        notification_time=notification_time,
        timezone=DEFAULT_TIMEZONE
    )

    await message.reply_text(
        f"Habit '{habit_name}' created!\n\n"
        f"Daily reminder at: {notification_time}\n\n"
        f"Use /my_habits to see all your habits."
    )


async def my_habits_handler(
    client: Client,
    message: Message,
    habits_db: HabitsDB
) -> None:
    """
    Handle /my_habits command.
    Lists all active habits for the user.
    """
    user_id = message.from_user.id
    habits = await habits_db.get_user_habits(user_id)

    if not habits:
        await message.reply_text(
            "You have no active habits.\n\n"
            "Use /add_habit <name> to create your first habit!"
        )
        return

    lines = ["Your active habits:\n"]

    for i, habit in enumerate(habits, 1):
        lines.append(
            f"{i}. {habit['name']}\n"
            f"   Reminder: {habit['notification_time']}\n"
            f"   ID: {habit['_id']}"
        )

    lines.append("\nUse /progress to see your streaks.")

    await message.reply_text("\n".join(lines))


async def progress_handler(
    client: Client,
    message: Message,
    habits_db: HabitsDB,
    streaks_db: StreaksDB
) -> None:
    """
    Handle /progress command.
    Shows streak statistics for all habits.
    """
    user_id = message.from_user.id
    habits = await habits_db.get_user_habits(user_id)

    if not habits:
        await message.reply_text(
            "You have no active habits.\n\n"
            "Use /add_habit <name> to create your first habit!"
        )
        return

    lines = ["Your progress:\n"]

    for habit in habits:
        streak = await streaks_db.get_streak(user_id, habit["_id"])

        current = streak["current_streak"] if streak else 0
        longest = streak["longest_streak"] if streak else 0
        total = streak["total_approved"] if streak else 0

        lines.append(f"{habit['name']}:")
        lines.append(f"  Current streak: {current} day(s)")
        lines.append(f"  Longest streak: {longest} day(s)")
        lines.append(f"  Total approved: {total}")
        lines.append("")

    await message.reply_text("\n".join(lines))


async def delete_habit_handler(
    client: Client,
    message: Message,
    habits_db: HabitsDB
) -> None:
    """
    Handle /delete_habit command.
    Deactivates a habit (soft delete).
    Usage: /delete_habit <habit_id>
    """
    if len(message.command) < 2:
        await message.reply_text(
            "Usage: /delete_habit <habit_id>\n\n"
            "Use /my_habits to see your habit IDs."
        )
        return

    habit_id_str = message.command[1]

    try:
        habit_id = ObjectId(habit_id_str)
    except Exception:
        await message.reply_text("Invalid habit ID.")
        return

    # Verify the habit belongs to this user
    habit = await habits_db.get_habit(habit_id)
    if habit is None or habit["user_id"] != message.from_user.id:
        await message.reply_text("Habit not found.")
        return

    success = await habits_db.deactivate_habit(habit_id)

    if success:
        await message.reply_text(
            f"Habit '{habit['name']}' has been deleted.\n\n"
            "Your streak history is preserved."
        )
    else:
        await message.reply_text("Failed to delete habit.")


# Register handlers with Pyrogram
# These will be auto-discovered by Pyrogram's plugin system

@Client.on_message(filters.command(["add_habit"]) & filters.private & is_ratelimited)
async def add_habit_command(client: Client, message: Message):
    """Pyrogram handler for /add_habit."""
    # Import here to avoid circular imports during bot startup
    from TelegramBot.database.MongoDb import database
    habits_db = HabitsDB(database.habits)
    await add_habit_handler(client, message, habits_db)


@Client.on_message(filters.command(["my_habits", "habits"]) & filters.private & is_ratelimited)
async def my_habits_command(client: Client, message: Message):
    """Pyrogram handler for /my_habits."""
    from TelegramBot.database.MongoDb import database
    habits_db = HabitsDB(database.habits)
    await my_habits_handler(client, message, habits_db)


@Client.on_message(filters.command(["progress", "stats", "streak"]) & filters.private & is_ratelimited)
async def progress_command(client: Client, message: Message):
    """Pyrogram handler for /progress."""
    from TelegramBot.database.MongoDb import database
    habits_db = HabitsDB(database.habits)
    streaks_db = StreaksDB(database.streaks)
    await progress_handler(client, message, habits_db, streaks_db)


@Client.on_message(filters.command(["delete_habit"]) & filters.private & is_ratelimited)
async def delete_habit_command(client: Client, message: Message):
    """Pyrogram handler for /delete_habit."""
    from TelegramBot.database.MongoDb import database
    habits_db = HabitsDB(database.habits)
    await delete_habit_handler(client, message, habits_db)
