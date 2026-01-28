"""
Database operations for submissions collection.
"""

from datetime import datetime, date
from typing import Optional, List, Dict, Any
from bson import ObjectId


class SubmissionsDB:
    """
    Database wrapper class for submissions collection CRUD operations.
    """

    def __init__(self, collection):
        """
        Initialize with a MongoDB collection.

        Args:
            collection: A motor async MongoDB collection instance.
        """
        self.collection = collection

    async def create_submission(
        self,
        habit_id: ObjectId,
        user_id: int,
        photo_file_id: str
    ) -> ObjectId:
        """
        Create a new submission for a habit.

        Args:
            habit_id: The ObjectId of the habit.
            user_id: Telegram user ID.
            photo_file_id: Telegram file ID of the proof photo.

        Returns:
            ObjectId of the created submission document.
        """
        document = {
            "habit_id": habit_id,
            "user_id": user_id,
            "photo_file_id": photo_file_id,
            "submitted_at": datetime.utcnow(),
            "status": "pending",
            "reviewed_by": None,
            "reviewed_at": None,
            "rejection_reason": None,
        }
        result = await self.collection.insert_one(document)
        return result.inserted_id

    async def get_submission(self, submission_id: ObjectId) -> Optional[Dict[str, Any]]:
        """
        Get a submission by its ID.

        Args:
            submission_id: The ObjectId of the submission.

        Returns:
            The submission document or None if not found.
        """
        return await self.collection.find_one({"_id": submission_id})

    async def get_pending(self) -> List[Dict[str, Any]]:
        """
        Get all pending submissions.

        Returns:
            List of submission documents with status "pending".
        """
        cursor = self.collection.find({"status": "pending"})
        return await cursor.to_list(length=None)

    async def approve_submission(
        self,
        submission_id: ObjectId,
        reviewer_id: int
    ) -> bool:
        """
        Approve a submission.

        Args:
            submission_id: The ObjectId of the submission.
            reviewer_id: Telegram user ID of the reviewer/admin.

        Returns:
            True if the submission was approved, False otherwise.
        """
        result = await self.collection.update_one(
            {"_id": submission_id},
            {
                "$set": {
                    "status": "approved",
                    "reviewed_by": reviewer_id,
                    "reviewed_at": datetime.utcnow(),
                }
            }
        )
        return result.modified_count > 0

    async def reject_submission(
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
            True if the submission was rejected, False otherwise.
        """
        result = await self.collection.update_one(
            {"_id": submission_id},
            {
                "$set": {
                    "status": "rejected",
                    "reviewed_by": reviewer_id,
                    "reviewed_at": datetime.utcnow(),
                    "rejection_reason": reason,
                }
            }
        )
        return result.modified_count > 0

    async def get_by_date_range(
        self,
        user_id: int,
        start_date: datetime,
        end_date: datetime,
        habit_id: Optional[ObjectId] = None
    ) -> List[Dict[str, Any]]:
        """
        Get submissions within a date range.

        Args:
            user_id: Telegram user ID.
            start_date: Start of date range.
            end_date: End of date range.
            habit_id: Optional habit ID to filter by.

        Returns:
            List of submission documents.
        """
        query = {
            "user_id": user_id,
            "submitted_at": {
                "$gte": start_date,
                "$lte": end_date,
            }
        }
        if habit_id:
            query["habit_id"] = habit_id

        cursor = self.collection.find(query)
        return await cursor.to_list(length=None)

    async def has_submission_today(
        self,
        user_id: int,
        habit_id: ObjectId
    ) -> bool:
        """
        Check if user has submitted proof for a habit today.

        Only counts pending or approved submissions. Rejected submissions
        are ignored to allow users to resubmit.

        Args:
            user_id: Telegram user ID.
            habit_id: The ObjectId of the habit.

        Returns:
            True if user has a pending or approved submission today, False otherwise.
        """
        today = date.today()
        start_of_day = datetime(today.year, today.month, today.day, 0, 0, 0)
        end_of_day = datetime(today.year, today.month, today.day, 23, 59, 59)

        submission = await self.collection.find_one({
            "user_id": user_id,
            "habit_id": habit_id,
            "status": {"$in": ["pending", "approved"]},
            "submitted_at": {
                "$gte": start_of_day,
                "$lte": end_of_day,
            }
        })
        return submission is not None

    async def get_user_submissions(
        self,
        user_id: int,
        status: Optional[str] = None,
        habit_id: Optional[ObjectId] = None
    ) -> List[Dict[str, Any]]:
        """
        Get all submissions for a user.

        Args:
            user_id: Telegram user ID.
            status: Optional status filter ("pending", "approved", "rejected").
            habit_id: Optional habit ID to filter by.

        Returns:
            List of submission documents.
        """
        query = {"user_id": user_id}
        if status:
            query["status"] = status
        if habit_id:
            query["habit_id"] = habit_id

        cursor = self.collection.find(query)
        return await cursor.to_list(length=None)
