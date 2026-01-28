"""
Admin review commands for managing habit submissions.

Commands:
- /pending_reviews - Show pending submissions
- Callback handlers for approve/reject buttons
"""

from bson import ObjectId
from pyrogram import Client, filters
from pyrogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from TelegramBot.helpers.filters import sudo_cmd, is_ratelimited
from TelegramBot.database.habits import HabitsDB
from TelegramBot.database.submissions import SubmissionsDB
from TelegramBot.database.streaks import StreaksDB
from TelegramBot.services.streak_service import StreakService
from TelegramBot.services.submission_service import SubmissionService


async def pending_reviews_handler(
    client: Client,
    message: Message,
    submissions_db: SubmissionsDB,
    habits_db: HabitsDB
) -> None:
    """
    Handle /pending_reviews command.
    Shows all pending submissions for review.
    """
    pending = await submissions_db.get_pending()

    if not pending:
        await message.reply_text(
            "No pending submissions to review."
        )
        return

    lines = [f"Pending submissions: {len(pending)}\n"]

    for i, sub in enumerate(pending, 1):
        habit = await habits_db.get_habit(sub["habit_id"])
        habit_name = habit["name"] if habit else "Unknown"

        lines.append(
            f"{i}. User {sub['user_id']} - {habit_name}\n"
            f"   Submitted: {sub['submitted_at'].strftime('%Y-%m-%d %H:%M')}\n"
            f"   ID: {sub['_id']}"
        )

    lines.append("\nClick on a submission photo to review it.")

    await message.reply_text("\n".join(lines))


async def approve_callback_handler(
    client: Client,
    callback_query: CallbackQuery,
    submission_service: SubmissionService
) -> None:
    """
    Handle approve button callback.
    Approves the submission and updates streak.
    """
    # Parse submission ID from callback data
    data = callback_query.data
    if not data.startswith("approve:"):
        return

    submission_id_str = data.replace("approve:", "")

    try:
        submission_id = ObjectId(submission_id_str)
    except Exception:
        await callback_query.answer("Invalid submission ID", show_alert=True)
        return

    reviewer_id = callback_query.from_user.id

    # Approve the submission
    success = await submission_service.approve(submission_id, reviewer_id)

    if success:
        await callback_query.answer("Submission approved!")

        # Update the message to show it's been reviewed
        try:
            await callback_query.message.edit_caption(
                callback_query.message.caption + "\n\n✅ APPROVED"
            )
        except Exception:
            pass
    else:
        await callback_query.answer("Failed to approve submission", show_alert=True)


async def reject_callback_handler(
    client: Client,
    callback_query: CallbackQuery,
    submission_service: SubmissionService,
    reason: str = None
) -> None:
    """
    Handle reject button callback.
    Rejects the submission.
    """
    # Parse submission ID from callback data
    data = callback_query.data
    if not data.startswith("reject:"):
        return

    submission_id_str = data.replace("reject:", "")

    try:
        submission_id = ObjectId(submission_id_str)
    except Exception:
        await callback_query.answer("Invalid submission ID", show_alert=True)
        return

    reviewer_id = callback_query.from_user.id

    # Reject the submission
    success = await submission_service.reject(submission_id, reviewer_id, reason)

    if success:
        await callback_query.answer("Submission rejected")

        # Update the message to show it's been reviewed
        try:
            await callback_query.message.edit_caption(
                callback_query.message.caption + "\n\n❌ REJECTED"
            )
        except Exception:
            pass
    else:
        await callback_query.answer("Failed to reject submission", show_alert=True)


def get_submission_service(client: Client) -> SubmissionService:
    """Create a SubmissionService instance."""
    from TelegramBot.database.MongoDb import database

    habits_db = HabitsDB(database.habits)
    submissions_db = SubmissionsDB(database.submissions)
    streaks_db = StreaksDB(database.streaks)
    streak_service = StreakService(streaks_db)

    return SubmissionService(
        submissions_db=submissions_db,
        habits_db=habits_db,
        streak_service=streak_service,
        client=client
    )


# Register handlers with Pyrogram

@Client.on_message(
    filters.command(["pending_reviews", "pending"]) & sudo_cmd & is_ratelimited
)
async def pending_reviews_command(client: Client, message: Message):
    """Pyrogram handler for /pending_reviews."""
    from TelegramBot.database.MongoDb import database

    submissions_db = SubmissionsDB(database.submissions)
    habits_db = HabitsDB(database.habits)

    await pending_reviews_handler(client, message, submissions_db, habits_db)


@Client.on_callback_query(filters.regex(r"^approve:"))
async def approve_callback(client: Client, callback_query: CallbackQuery):
    """Pyrogram handler for approve callback."""
    # Verify user is admin
    from TelegramBot.config import SUDO_USERID
    if callback_query.from_user.id not in SUDO_USERID:
        await callback_query.answer("Unauthorized", show_alert=True)
        return

    submission_service = get_submission_service(client)
    await approve_callback_handler(client, callback_query, submission_service)


@Client.on_callback_query(filters.regex(r"^reject:"))
async def reject_callback(client: Client, callback_query: CallbackQuery):
    """Pyrogram handler for reject callback."""
    # Verify user is admin
    from TelegramBot.config import SUDO_USERID
    if callback_query.from_user.id not in SUDO_USERID:
        await callback_query.answer("Unauthorized", show_alert=True)
        return

    submission_service = get_submission_service(client)
    await reject_callback_handler(client, callback_query, submission_service)
