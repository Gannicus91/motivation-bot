"""
Photo submission handler for habit proofs.

Handles incoming photos from users and creates submissions for admin review.
"""

from typing import List
from bson import ObjectId
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton

from TelegramBot.helpers.filters import is_ratelimited
from TelegramBot.database.habits import HabitsDB
from TelegramBot.database.submissions import SubmissionsDB
from TelegramBot.database.streaks import StreaksDB
from TelegramBot.services.streak_service import StreakService
from TelegramBot.services.submission_service import SubmissionService


def get_admin_ids() -> List[int]:
    """Get list of admin user IDs."""
    from TelegramBot.config import OWNER_USERID
    return OWNER_USERID


async def handle_photo_submission(
    client: Client,
    message: Message,
    habits_db: HabitsDB,
    submission_service: SubmissionService
) -> None:
    """
    Handle photo submission from user.

    Args:
        client: Pyrogram client.
        message: The photo message.
        habits_db: Habits database instance.
        submission_service: Submission service instance.
    """
    user_id = message.from_user.id
    photo_file_id = message.photo.file_id

    # Get user's active habits
    habits = await habits_db.get_user_habits(user_id)

    if not habits:
        await message.reply_text(
            "You have no active habits.\n\n"
            "Use /add_habit <name> to create a habit first!"
        )
        return

    # If user has multiple habits, ask which one
    if len(habits) > 1:
        # For now, show options
        keyboard = []
        for habit in habits:
            keyboard.append([
                InlineKeyboardButton(
                    habit["name"],
                    callback_data=f"submit:{habit['_id']}"
                )
            ])

        await message.reply_text(
            "Which habit is this submission for?\n\n"
            "Select from the options below:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

        # Store the photo file ID temporarily
        # In a real implementation, we'd use a state machine or cache
        # For now, we'll handle the single-habit case
        return

    # Single habit - auto submit
    habit = habits[0]
    habit_id = habit["_id"]

    try:
        submission_id = await submission_service.submit(
            user_id=user_id,
            habit_id=habit_id,
            photo_file_id=photo_file_id
        )

        await message.reply_text(
            f"Your proof for '{habit['name']}' has been submitted!\n\n"
            "Status: Pending review\n\n"
            "You'll be notified once it's reviewed."
        )

        # Forward to admins
        await forward_to_admins(client, message, habit, submission_id)

    except ValueError as e:
        error_msg = str(e).lower()
        if "already submitted" in error_msg:
            await message.reply_text(
                f"You've already submitted proof for '{habit['name']}' today.\n\n"
                "Try again tomorrow!"
            )
        else:
            await message.reply_text(f"Error: {e}")


async def forward_to_admins(
    client: Client,
    message: Message,
    habit: dict,
    submission_id: ObjectId
) -> None:
    """
    Forward submission to admins for review.

    Args:
        client: Pyrogram client.
        message: The original photo message.
        habit: The habit document.
        submission_id: The submission ObjectId.
    """
    if client is None:
        return

    admin_ids = get_admin_ids()

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "Approve",
                callback_data=f"approve:{submission_id}"
            ),
            InlineKeyboardButton(
                "Reject",
                callback_data=f"reject:{submission_id}"
            )
        ]
    ])

    user = message.from_user
    caption = (
        f"New submission for review\n\n"
        f"User: {user.first_name} (ID: {user.id})\n"
        f"Habit: {habit['name']}\n"
        f"Submission ID: {submission_id}"
    )

    for admin_id in admin_ids:
        try:
            # Forward the photo to admin with review buttons
            await client.send_photo(
                chat_id=admin_id,
                photo=message.photo.file_id,
                caption=caption,
                reply_markup=keyboard
            )
        except Exception:
            # Admin might have blocked the bot
            pass


# Register handlers with Pyrogram

@Client.on_message(filters.photo & filters.private & is_ratelimited)
async def photo_handler(client: Client, message: Message):
    """Pyrogram handler for photo messages."""
    from TelegramBot.database.MongoDb import database

    habits_db = HabitsDB(database.habits)
    submissions_db = SubmissionsDB(database.submissions)
    streaks_db = StreaksDB(database.streaks)
    streak_service = StreakService(streaks_db)
    submission_service = SubmissionService(
        submissions_db=submissions_db,
        habits_db=habits_db,
        streak_service=streak_service,
        client=client
    )

    await handle_photo_submission(client, message, habits_db, submission_service)
