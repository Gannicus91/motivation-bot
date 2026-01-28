"""
Business logic for submission management.
"""

from typing import Dict, Any, List, Optional
from bson import ObjectId

from TelegramBot.database.submissions import SubmissionsDB
from TelegramBot.database.habits import HabitsDB
from TelegramBot.services.streak_service import StreakService


class SubmissionService:
    """
    Service class for submission-related business logic.
    Handles submission creation, approval, rejection, and notifications.
    """

    def __init__(
        self,
        submissions_db: SubmissionsDB,
        habits_db: HabitsDB,
        streak_service: StreakService,
        client=None
    ):
        """
        Initialize with database instances and optional client.

        Args:
            submissions_db: The database layer for submissions.
            habits_db: The database layer for habits.
            streak_service: The service for streak management.
            client: Optional Pyrogram client for notifications.
        """
        self.submissions_db = submissions_db
        self.habits_db = habits_db
        self.streak_service = streak_service
        self.client = client

    async def submit(
        self,
        user_id: int,
        habit_id: ObjectId,
        photo_file_id: Optional[str]
    ) -> ObjectId:
        """
        Submit proof for a habit.

        Args:
            user_id: Telegram user ID.
            habit_id: The ObjectId of the habit.
            photo_file_id: Telegram file ID of the proof photo.

        Returns:
            ObjectId of the created submission.

        Raises:
            ValueError: If photo is missing, habit doesn't exist,
                       or already submitted today.
        """
        # Validate photo is provided
        if not photo_file_id:
            raise ValueError("Photo is required")

        # Validate habit exists
        habit = await self.habits_db.get_habit(habit_id)
        if habit is None:
            raise ValueError("Habit not found")

        # Check if already submitted today
        has_submitted = await self.submissions_db.has_submission_today(
            user_id, habit_id
        )
        if has_submitted:
            raise ValueError("Already submitted today")

        # Create the submission
        return await self.submissions_db.create_submission(
            habit_id=habit_id,
            user_id=user_id,
            photo_file_id=photo_file_id
        )

    async def approve(
        self,
        submission_id: ObjectId,
        reviewer_id: int
    ) -> bool:
        """
        Approve a submission and update streak.

        Args:
            submission_id: The ObjectId of the submission.
            reviewer_id: Telegram user ID of the reviewer/admin.

        Returns:
            True if approved successfully, False otherwise.
        """
        # Get submission details first
        submission = await self.submissions_db.get_submission(submission_id)
        if submission is None:
            return False

        # Approve the submission
        result = await self.submissions_db.approve_submission(
            submission_id, reviewer_id
        )

        if result:
            # Update streak
            await self.streak_service.on_approval(
                submission["user_id"],
                submission["habit_id"]
            )

            # Get updated streak for notification
            streak_stats = await self.streak_service.get_streak_stats(
                submission["user_id"],
                submission["habit_id"]
            )

            # Notify user
            await self._notify_user_approved(
                submission["user_id"],
                submission["habit_id"],
                streak_stats
            )

        return result

    async def reject(
        self,
        submission_id: ObjectId,
        reviewer_id: int,
        reason: Optional[str] = None
    ) -> bool:
        """
        Reject a submission.

        Args:
            submission_id: The ObjectId of the submission.
            reviewer_id: Telegram user ID of the reviewer/admin.
            reason: Optional rejection reason.

        Returns:
            True if rejected successfully, False otherwise.
        """
        # Get submission details first
        submission = await self.submissions_db.get_submission(submission_id)
        if submission is None:
            return False

        # Reject the submission
        result = await self.submissions_db.reject_submission(
            submission_id, reviewer_id, reason
        )

        if result:
            # Notify user
            await self._notify_user_rejected(
                submission["user_id"],
                submission["habit_id"],
                reason
            )

        return result

    async def get_pending(self) -> List[Dict[str, Any]]:
        """
        Get all pending submissions.

        Returns:
            List of pending submission documents.
        """
        return await self.submissions_db.get_pending()

    async def get_submission_details(
        self,
        submission_id: ObjectId
    ) -> Optional[Dict[str, Any]]:
        """
        Get submission details including habit information.

        Args:
            submission_id: The ObjectId of the submission.

        Returns:
            Dictionary with submission and habit details, or None.
        """
        submission = await self.submissions_db.get_submission(submission_id)
        if submission is None:
            return None

        # Get habit information
        habit = await self.habits_db.get_habit(submission["habit_id"])

        return {
            **submission,
            "habit_name": habit["name"] if habit else "Unknown",
        }

    async def _notify_user_approved(
        self,
        user_id: int,
        habit_id: ObjectId,
        streak_stats: Dict[str, Any]
    ) -> None:
        """Send approval notification to user."""
        if self.client is None:
            return

        habit = await self.habits_db.get_habit(habit_id)
        habit_name = habit["name"] if habit else "your habit"

        current = streak_stats["current_streak"]
        longest = streak_stats["longest_streak"]

        message = (
            f"Your submission for '{habit_name}' has been approved!\n\n"
            f"Current streak: {current} day(s)\n"
            f"Longest streak: {longest} day(s)\n\n"
            f"Keep up the great work!"
        )

        await self.client.send_message(chat_id=user_id, text=message)

    async def _notify_user_rejected(
        self,
        user_id: int,
        habit_id: ObjectId,
        reason: Optional[str]
    ) -> None:
        """Send rejection notification to user."""
        if self.client is None:
            return

        habit = await self.habits_db.get_habit(habit_id)
        habit_name = habit["name"] if habit else "your habit"

        message = f"Your submission for '{habit_name}' has been rejected."
        if reason:
            message += f"\n\nReason: {reason}"
        message += "\n\nPlease submit a new proof photo."

        await self.client.send_message(chat_id=user_id, text=message)
