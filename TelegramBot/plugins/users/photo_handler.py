"""
Photo submission handler for habit proofs.

Handles incoming photos from users and creates submissions for admin review.
"""

from typing import List
from bson import ObjectId
from pyrogram import Client, filters
from pyrogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from TelegramBot.helpers.filters import is_ratelimited
from TelegramBot.database.habits import HabitsDB
from TelegramBot.database.submissions import SubmissionsDB
from TelegramBot.database.streaks import StreaksDB
from TelegramBot.services.streak_service import StreakService
from TelegramBot.services.submission_service import SubmissionService


# In-memory cache for pending photos when user has multiple habits
# Format: {user_id: {"photo_file_id": str, "message": Message}}
pending_photos: dict = {}


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
        # Store photo in pending cache for later retrieval
        pending_photos[user_id] = {
            "photo_file_id": photo_file_id,
            "message": message
        }

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


async def forward_photo_to_admins(
    client: Client,
    photo_file_id: str,
    user_first_name: str,
    user_id: int,
    habit: dict,
    submission_id: ObjectId
) -> None:
    """
    Forward photo submission to admins for review.

    Args:
        client: Pyrogram client.
        photo_file_id: The photo file ID.
        user_first_name: The user's first name.
        user_id: The user's ID.
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

    caption = (
        f"New submission for review\n\n"
        f"User: {user_first_name} (ID: {user_id})\n"
        f"Habit: {habit['name']}\n"
        f"Submission ID: {submission_id}"
    )

    for admin_id in admin_ids:
        try:
            await client.send_photo(
                chat_id=admin_id,
                photo=photo_file_id,
                caption=caption,
                reply_markup=keyboard
            )
        except Exception:
            pass


async def handle_submit_callback(
    client: Client,
    callback_query: CallbackQuery,
    habits_db: HabitsDB,
    submission_service: SubmissionService
) -> None:
    """
    Handle habit selection callback for multi-habit photo submission.

    Args:
        client: Pyrogram client.
        callback_query: The callback query from habit selection.
        habits_db: Habits database instance.
        submission_service: Submission service instance.
    """
    user_id = callback_query.from_user.id
    habit_id_str = callback_query.data.split(":")[1]
    habit_id = ObjectId(habit_id_str)

    # Get cached photo
    pending = pending_photos.pop(user_id, None)
    if not pending:
        await callback_query.answer(
            "Session expired. Please send photo again.",
            show_alert=True
        )
        return

    photo_file_id = pending["photo_file_id"]

    # Get habit details
    habit = await habits_db.get_habit(habit_id)
    if not habit:
        await callback_query.answer("Habit not found.", show_alert=True)
        return

    try:
        submission_id = await submission_service.submit(
            user_id=user_id,
            habit_id=habit_id,
            photo_file_id=photo_file_id
        )

        await callback_query.edit_message_text(
            f"Your proof for '{habit['name']}' has been submitted!\n\n"
            "Status: Pending review\n\n"
            "You'll be notified once it's reviewed."
        )

        # Forward to admins
        await forward_photo_to_admins(
            client=client,
            photo_file_id=photo_file_id,
            user_first_name=callback_query.from_user.first_name,
            user_id=user_id,
            habit=habit,
            submission_id=submission_id
        )

        await callback_query.answer()

    except ValueError as e:
        error_msg = str(e).lower()
        if "already submitted" in error_msg:
            await callback_query.edit_message_text(
                f"You've already submitted proof for '{habit['name']}' today.\n\n"
                "Try again tomorrow!"
            )
        else:
            await callback_query.answer(f"Error: {e}", show_alert=True)


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


@Client.on_callback_query(filters.regex(r"^submit:"))
async def submit_callback_handler(client: Client, callback_query: CallbackQuery):
    """Pyrogram handler for submit callback queries."""
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

    await handle_submit_callback(client, callback_query, habits_db, submission_service)
