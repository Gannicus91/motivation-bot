"""
Database operations for streaks collection.
"""

from datetime import date, datetime
from typing import Optional, List, Dict, Any
from bson import ObjectId


class StreaksDB:
    """
    Database wrapper class for streaks collection CRUD operations.
    Tracks user streak data for habits (Duolingo-style).
    """

    def __init__(self, collection):
        """
        Initialize with a MongoDB collection.

        Args:
            collection: A motor async MongoDB collection instance.
        """
        self.collection = collection

    async def get_or_create(
        self,
        user_id: int,
        habit_id: ObjectId
    ) -> Dict[str, Any]:
        """
        Get existing streak or create a new one if it doesn't exist.

        Args:
            user_id: Telegram user ID.
            habit_id: The ObjectId of the habit.

        Returns:
            The streak document.
        """
        streak = await self.collection.find_one({
            "user_id": user_id,
            "habit_id": habit_id
        })

        if streak is None:
            document = {
                "user_id": user_id,
                "habit_id": habit_id,
                "current_streak": 0,
                "longest_streak": 0,
                "last_approved_date": None,
                "total_approved": 0,
            }
            result = await self.collection.insert_one(document)
            document["_id"] = result.inserted_id
            return document

        return streak

    async def get_streak(
        self,
        user_id: int,
        habit_id: ObjectId
    ) -> Optional[Dict[str, Any]]:
        """
        Get a streak for a specific habit (without creating).

        Args:
            user_id: Telegram user ID.
            habit_id: The ObjectId of the habit.

        Returns:
            The streak document or None if not found.
        """
        return await self.collection.find_one({
            "user_id": user_id,
            "habit_id": habit_id
        })

    async def increment_streak(
        self,
        user_id: int,
        habit_id: ObjectId
    ) -> bool:
        """
        Increment the current streak by 1 and update related fields.

        Args:
            user_id: Telegram user ID.
            habit_id: The ObjectId of the habit.

        Returns:
            True if streak was incremented, False otherwise.
        """
        # Ensure streak exists
        await self.get_or_create(user_id, habit_id)

        # Get current streak to check if we need to update longest
        current = await self.get_streak(user_id, habit_id)
        new_streak = current["current_streak"] + 1
        new_longest = max(current["longest_streak"], new_streak)

        # Store date as datetime for MongoDB compatibility
        today = date.today()
        today_datetime = datetime(today.year, today.month, today.day)

        result = await self.collection.update_one(
            {"user_id": user_id, "habit_id": habit_id},
            {
                "$inc": {"current_streak": 1, "total_approved": 1},
                "$set": {
                    "last_approved_date": today_datetime,
                    "longest_streak": new_longest,
                }
            }
        )
        return result.modified_count > 0

    async def reset_streak(
        self,
        user_id: int,
        habit_id: ObjectId
    ) -> bool:
        """
        Reset the current streak to 0 (preserves longest_streak and total_approved).

        Args:
            user_id: Telegram user ID.
            habit_id: The ObjectId of the habit.

        Returns:
            True if streak was reset, False otherwise.
        """
        result = await self.collection.update_one(
            {"user_id": user_id, "habit_id": habit_id},
            {"$set": {"current_streak": 0}}
        )
        return result.modified_count > 0

    async def update_longest(
        self,
        user_id: int,
        habit_id: ObjectId,
        new_value: int
    ) -> bool:
        """
        Update longest_streak if new value is greater.

        Args:
            user_id: Telegram user ID.
            habit_id: The ObjectId of the habit.
            new_value: The new longest streak value.

        Returns:
            True if longest was updated, False otherwise.
        """
        result = await self.collection.update_one(
            {
                "user_id": user_id,
                "habit_id": habit_id,
                "longest_streak": {"$lt": new_value}
            },
            {"$set": {"longest_streak": new_value}}
        )
        return result.modified_count > 0

    async def get_user_streaks(
        self,
        user_id: int
    ) -> List[Dict[str, Any]]:
        """
        Get all streaks for a user.

        Args:
            user_id: Telegram user ID.

        Returns:
            List of streak documents.
        """
        cursor = self.collection.find({"user_id": user_id})
        return await cursor.to_list(length=None)

    async def delete_streak(
        self,
        user_id: int,
        habit_id: ObjectId
    ) -> bool:
        """
        Delete a streak document.

        Args:
            user_id: Telegram user ID.
            habit_id: The ObjectId of the habit.

        Returns:
            True if streak was deleted, False otherwise.
        """
        result = await self.collection.delete_one({
            "user_id": user_id,
            "habit_id": habit_id
        })
        return result.deleted_count > 0
