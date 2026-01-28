"""
Business logic for notification management.
"""

from datetime import date, datetime, timedelta
from typing import Dict, Any, List
from bson import ObjectId

from TelegramBot.database.habits import HabitsDB
from TelegramBot.database.submissions import SubmissionsDB
from TelegramBot.database.streaks import StreaksDB


class NotificationService:
    """
    Service class for notification-related business logic.
    Handles sending daily reminders and determining who needs notifications.
    """

    def __init__(
        self,
        habits_db: HabitsDB,
        submissions_db: SubmissionsDB,
        streaks_db: StreaksDB,
        client=None
    ):
        """
        Initialize with database instances and optional client.

        Args:
            habits_db: The database layer for habits.
            submissions_db: The database layer for submissions.
            streaks_db: The database layer for streaks.
            client: Optional Pyrogram client for sending messages.
        """
        self.habits_db = habits_db
        self.submissions_db = submissions_db
        self.streaks_db = streaks_db
        self.client = client

    async def get_users_due(
        self,
        notification_time: str
    ) -> List[Dict[str, Any]]:
        """
        Get all habits due for notification at the given time.

        Excludes habits where the user has already submitted today.

        Args:
            notification_time: Time in HH:MM format.

        Returns:
            List of habit documents that need reminders.
        """
        # Get all habits scheduled for this time
        habits = await self.habits_db.get_habits_by_notification_time(
            notification_time
        )

        # Filter out those who already submitted today
        due_habits = []
        for habit in habits:
            has_submitted = await self.submissions_db.has_submission_today(
                habit["user_id"],
                habit["_id"]
            )
            if not has_submitted:
                due_habits.append(habit)

        return due_habits

    async def send_reminder(
        self,
        user_id: int,
        habit_id: ObjectId
    ) -> bool:
        """
        Send a reminder notification to a user for a habit.

        Args:
            user_id: Telegram user ID.
            habit_id: The ObjectId of the habit.

        Returns:
            True if message was sent, False otherwise.
        """
        if self.client is None:
            return False

        # Get habit info
        habit = await self.habits_db.get_habit(habit_id)
        if habit is None:
            return False

        # Get streak info
        streak = await self.streaks_db.get_streak(user_id, habit_id)
        current_streak = streak["current_streak"] if streak else 0
        last_approved = streak.get("last_approved_date") if streak else None

        # Check if streak is at risk
        streak_at_risk = False
        if last_approved:
            if isinstance(last_approved, datetime):
                last_approved = last_approved.date()
            yesterday = date.today() - timedelta(days=1)
            streak_at_risk = last_approved == yesterday and current_streak > 0

        # Build message
        message = self._build_reminder_message(
            habit["name"],
            current_streak,
            streak_at_risk
        )

        await self.client.send_message(chat_id=user_id, text=message)
        return True

    async def send_all_reminders(
        self,
        notification_time: str
    ) -> int:
        """
        Send reminders to all users due at the given time.

        Args:
            notification_time: Time in HH:MM format.

        Returns:
            Number of reminders sent.
        """
        due_habits = await self.get_users_due(notification_time)

        count = 0
        for habit in due_habits:
            try:
                success = await self.send_reminder(
                    habit["user_id"],
                    habit["_id"]
                )
                if success:
                    count += 1
            except Exception:
                # Log error but continue sending to others
                pass

        return count

    def _build_reminder_message(
        self,
        habit_name: str,
        current_streak: int,
        streak_at_risk: bool
    ) -> str:
        """
        Build the reminder message text.

        Args:
            habit_name: Name of the habit.
            current_streak: Current streak count.
            streak_at_risk: Whether the streak is at risk of being lost.

        Returns:
            Formatted reminder message.
        """
        lines = [
            f"Time for your daily habit: {habit_name}!",
            "",
        ]

        if current_streak > 0:
            lines.append(f"Current streak: {current_streak} day(s)")

            if streak_at_risk:
                lines.append(
                    "Don't lose your streak! Submit your proof today."
                )
        else:
            lines.append("Start building your streak today!")

        lines.extend([
            "",
            "Reply with a photo to submit your proof.",
        ])

        return "\n".join(lines)
