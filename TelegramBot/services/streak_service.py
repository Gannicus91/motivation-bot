"""
Business logic for streak management.
"""

from datetime import date, datetime, timedelta
from typing import Dict, Any, List, Optional
from bson import ObjectId

from TelegramBot.database.streaks import StreaksDB


class StreakService:
    """
    Service class for streak-related business logic.
    Handles streak calculations, updates, and reset logic.
    """

    def __init__(self, streaks_db: StreaksDB):
        """
        Initialize with a StreaksDB instance.

        Args:
            streaks_db: The database layer for streak operations.
        """
        self.streaks_db = streaks_db

    async def calculate_streak(
        self,
        user_id: int,
        habit_id: ObjectId
    ) -> int:
        """
        Calculate the current streak for a user's habit.

        Args:
            user_id: Telegram user ID.
            habit_id: The ObjectId of the habit.

        Returns:
            Current streak count.
        """
        streak = await self.streaks_db.get_streak(user_id, habit_id)
        if streak is None:
            return 0
        return streak["current_streak"]

    async def on_approval(
        self,
        user_id: int,
        habit_id: ObjectId
    ) -> Dict[str, Any]:
        """
        Handle streak update when a submission is approved.

        Args:
            user_id: Telegram user ID.
            habit_id: The ObjectId of the habit.

        Returns:
            Updated streak data.
        """
        # First check if we need to reset due to missed day
        await self.check_and_reset_if_missed(user_id, habit_id)

        # Increment the streak
        await self.streaks_db.increment_streak(user_id, habit_id)

        # Return updated streak data
        return await self.streaks_db.get_or_create(user_id, habit_id)

    async def check_and_reset_if_missed(
        self,
        user_id: int,
        habit_id: ObjectId
    ) -> bool:
        """
        Check if the user missed a day and reset streak if so.

        A day is considered missed if the last approved date was more than
        1 day ago (not yesterday or today).

        Args:
            user_id: Telegram user ID.
            habit_id: The ObjectId of the habit.

        Returns:
            True if streak was reset, False otherwise.
        """
        streak = await self.streaks_db.get_streak(user_id, habit_id)

        if streak is None:
            return False

        last_approved = streak.get("last_approved_date")
        if last_approved is None:
            return False

        # Convert to date if datetime
        if isinstance(last_approved, datetime):
            last_approved = last_approved.date()

        today = date.today()
        yesterday = today - timedelta(days=1)

        # If last approval was before yesterday, we missed a day
        if last_approved < yesterday:
            await self.streaks_db.reset_streak(user_id, habit_id)
            return True

        return False

    async def get_streak_stats(
        self,
        user_id: int,
        habit_id: ObjectId
    ) -> Dict[str, Any]:
        """
        Get comprehensive streak statistics for a user's habit.

        Args:
            user_id: Telegram user ID.
            habit_id: The ObjectId of the habit.

        Returns:
            Dictionary with streak statistics.
        """
        streak = await self.streaks_db.get_or_create(user_id, habit_id)

        return {
            "current_streak": streak["current_streak"],
            "longest_streak": streak["longest_streak"],
            "total_approved": streak["total_approved"],
            "last_approved_date": streak.get("last_approved_date"),
        }

    async def get_all_user_streaks(
        self,
        user_id: int
    ) -> List[Dict[str, Any]]:
        """
        Get all streak data for a user across all habits.

        Args:
            user_id: Telegram user ID.

        Returns:
            List of streak documents.
        """
        return await self.streaks_db.get_user_streaks(user_id)
