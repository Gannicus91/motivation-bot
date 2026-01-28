"""
Database operations for habits collection.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from bson import ObjectId


class HabitsDB:
    """
    Database wrapper class for habits collection CRUD operations.
    """

    def __init__(self, collection):
        """
        Initialize with a MongoDB collection.

        Args:
            collection: A motor async MongoDB collection instance.
        """
        self.collection = collection

    async def create_habit(
        self,
        user_id: int,
        name: str,
        notification_time: str,
        timezone: str
    ) -> ObjectId:
        """
        Create a new habit for a user.

        Args:
            user_id: Telegram user ID.
            name: Name of the habit.
            notification_time: Time for daily notification (HH:MM format).
            timezone: User's timezone string.

        Returns:
            ObjectId of the created habit document.
        """
        document = {
            "user_id": user_id,
            "name": name,
            "notification_time": notification_time,
            "timezone": timezone,
            "is_active": True,
            "created_at": datetime.utcnow(),
        }
        result = await self.collection.insert_one(document)
        return result.inserted_id

    async def get_habit(self, habit_id: ObjectId) -> Optional[Dict[str, Any]]:
        """
        Get a habit by its ID.

        Args:
            habit_id: The ObjectId of the habit.

        Returns:
            The habit document or None if not found.
        """
        return await self.collection.find_one({"_id": habit_id})

    async def get_user_habits(
        self,
        user_id: int,
        include_inactive: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Get all habits for a user.

        Args:
            user_id: Telegram user ID.
            include_inactive: Whether to include deactivated habits.

        Returns:
            List of habit documents.
        """
        query = {"user_id": user_id}
        if not include_inactive:
            query["is_active"] = True

        cursor = self.collection.find(query)
        return await cursor.to_list(length=None)

    async def update_habit(self, habit_id: ObjectId, **fields) -> bool:
        """
        Update a habit's fields.

        Args:
            habit_id: The ObjectId of the habit.
            **fields: Fields to update (name, notification_time, timezone).

        Returns:
            True if the habit was updated, False otherwise.
        """
        if not fields:
            return False

        result = await self.collection.update_one(
            {"_id": habit_id},
            {"$set": fields}
        )
        return result.modified_count > 0

    async def deactivate_habit(self, habit_id: ObjectId) -> bool:
        """
        Deactivate a habit (soft delete).

        Args:
            habit_id: The ObjectId of the habit.

        Returns:
            True if the habit was deactivated, False otherwise.
        """
        result = await self.collection.update_one(
            {"_id": habit_id},
            {"$set": {"is_active": False}}
        )
        return result.modified_count > 0

    async def delete_habit(self, habit_id: ObjectId) -> bool:
        """
        Permanently delete a habit.

        Args:
            habit_id: The ObjectId of the habit.

        Returns:
            True if the habit was deleted, False otherwise.
        """
        result = await self.collection.delete_one({"_id": habit_id})
        return result.deleted_count > 0

    async def get_habits_by_notification_time(
        self,
        notification_time: str
    ) -> List[Dict[str, Any]]:
        """
        Get all active habits scheduled for a specific notification time.

        Args:
            notification_time: Time in HH:MM format.

        Returns:
            List of habit documents.
        """
        cursor = self.collection.find({
            "notification_time": notification_time,
            "is_active": True
        })
        return await cursor.to_list(length=None)
