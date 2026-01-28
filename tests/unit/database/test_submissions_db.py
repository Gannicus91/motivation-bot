"""
Tests for the submissions database module.
Following TDD: These tests are written BEFORE the implementation.
"""

import pytest
from datetime import datetime, date, timedelta
from bson import ObjectId
from freezegun import freeze_time

from TelegramBot.database.submissions import SubmissionsDB


class TestSubmissionsDatabase:
    """Test suite for submissions database operations."""

    async def test_create_submission_returns_object_id(
        self, submissions_collection, sample_habit_id, sample_user_id
    ):
        """Creating a submission should return an ObjectId."""
        db = SubmissionsDB(submissions_collection)
        submission_id = await db.create_submission(
            habit_id=sample_habit_id,
            user_id=sample_user_id,
            photo_file_id="AgACAgIAAxkBAAI_test"
        )

        assert isinstance(submission_id, ObjectId)

    async def test_create_submission_stores_correct_data(
        self, submissions_collection, sample_habit_id, sample_user_id
    ):
        """Created submission should contain all provided fields with pending status."""
        db = SubmissionsDB(submissions_collection)
        submission_id = await db.create_submission(
            habit_id=sample_habit_id,
            user_id=sample_user_id,
            photo_file_id="AgACAgIAAxkBAAI_test"
        )

        submission = await submissions_collection.find_one({"_id": submission_id})

        assert submission["habit_id"] == sample_habit_id
        assert submission["user_id"] == sample_user_id
        assert submission["photo_file_id"] == "AgACAgIAAxkBAAI_test"
        assert submission["status"] == "pending"
        assert isinstance(submission["submitted_at"], datetime)
        assert submission["reviewed_by"] is None
        assert submission["reviewed_at"] is None
        assert submission["rejection_reason"] is None

    async def test_get_submission_by_id(
        self, submissions_collection, sample_habit_id, sample_user_id
    ):
        """get_submission should return the submission document by ID."""
        db = SubmissionsDB(submissions_collection)
        submission_id = await db.create_submission(
            habit_id=sample_habit_id,
            user_id=sample_user_id,
            photo_file_id="AgACAgIAAxkBAAI_test"
        )

        submission = await db.get_submission(submission_id)

        assert submission is not None
        assert submission["_id"] == submission_id

    async def test_get_pending_returns_only_pending_submissions(
        self, submissions_collection, sample_habit_id, sample_user_id, sample_admin_id
    ):
        """get_pending should return only submissions with pending status."""
        db = SubmissionsDB(submissions_collection)
        await db.create_submission(sample_habit_id, sample_user_id, "photo1")
        await db.create_submission(sample_habit_id, sample_user_id, "photo2")
        sub_id = await db.create_submission(sample_habit_id, sample_user_id, "photo3")
        await db.approve_submission(sub_id, sample_admin_id)

        pending = await db.get_pending()

        assert len(pending) == 2
        for sub in pending:
            assert sub["status"] == "pending"

    async def test_get_pending_returns_empty_when_none_pending(
        self, submissions_collection, sample_habit_id, sample_user_id, sample_admin_id
    ):
        """get_pending should return empty list when no pending submissions."""
        db = SubmissionsDB(submissions_collection)
        sub_id = await db.create_submission(sample_habit_id, sample_user_id, "photo1")
        await db.approve_submission(sub_id, sample_admin_id)

        pending = await db.get_pending()

        assert pending == []

    async def test_approve_submission_sets_status_approved(
        self, submissions_collection, sample_habit_id, sample_user_id, sample_admin_id
    ):
        """approve_submission should set status to approved."""
        db = SubmissionsDB(submissions_collection)
        sub_id = await db.create_submission(sample_habit_id, sample_user_id, "photo1")

        result = await db.approve_submission(sub_id, sample_admin_id)

        submission = await db.get_submission(sub_id)
        assert result is True
        assert submission["status"] == "approved"
        assert submission["reviewed_by"] == sample_admin_id
        assert isinstance(submission["reviewed_at"], datetime)

    async def test_approve_submission_returns_false_for_nonexistent(
        self, submissions_collection, sample_admin_id
    ):
        """approve_submission should return False for non-existent submission."""
        db = SubmissionsDB(submissions_collection)
        result = await db.approve_submission(ObjectId(), sample_admin_id)

        assert result is False

    async def test_reject_submission_sets_status_rejected(
        self, submissions_collection, sample_habit_id, sample_user_id, sample_admin_id
    ):
        """reject_submission should set status to rejected with reason."""
        db = SubmissionsDB(submissions_collection)
        sub_id = await db.create_submission(sample_habit_id, sample_user_id, "photo1")

        result = await db.reject_submission(sub_id, sample_admin_id, "Photo not clear")

        submission = await db.get_submission(sub_id)
        assert result is True
        assert submission["status"] == "rejected"
        assert submission["reviewed_by"] == sample_admin_id
        assert submission["rejection_reason"] == "Photo not clear"
        assert isinstance(submission["reviewed_at"], datetime)

    async def test_reject_submission_without_reason(
        self, submissions_collection, sample_habit_id, sample_user_id, sample_admin_id
    ):
        """reject_submission should work without providing a reason."""
        db = SubmissionsDB(submissions_collection)
        sub_id = await db.create_submission(sample_habit_id, sample_user_id, "photo1")

        result = await db.reject_submission(sub_id, sample_admin_id)

        submission = await db.get_submission(sub_id)
        assert result is True
        assert submission["status"] == "rejected"
        assert submission["rejection_reason"] is None

    async def test_get_by_date_range(
        self, submissions_collection, sample_habit_id, sample_user_id
    ):
        """get_by_date_range should return submissions within the date range."""
        db = SubmissionsDB(submissions_collection)

        # Insert submissions at different times
        with freeze_time("2024-01-15 10:00:00"):
            await db.create_submission(sample_habit_id, sample_user_id, "photo1")

        with freeze_time("2024-01-16 10:00:00"):
            await db.create_submission(sample_habit_id, sample_user_id, "photo2")

        with freeze_time("2024-01-17 10:00:00"):
            await db.create_submission(sample_habit_id, sample_user_id, "photo3")

        start_date = datetime(2024, 1, 15, 0, 0, 0)
        end_date = datetime(2024, 1, 16, 23, 59, 59)

        submissions = await db.get_by_date_range(sample_user_id, start_date, end_date)

        assert len(submissions) == 2

    async def test_get_by_date_range_for_specific_habit(
        self, submissions_collection, sample_user_id
    ):
        """get_by_date_range should filter by habit_id when provided."""
        db = SubmissionsDB(submissions_collection)
        habit1 = ObjectId()
        habit2 = ObjectId()

        with freeze_time("2024-01-15 10:00:00"):
            await db.create_submission(habit1, sample_user_id, "photo1")
            await db.create_submission(habit2, sample_user_id, "photo2")

        start_date = datetime(2024, 1, 15, 0, 0, 0)
        end_date = datetime(2024, 1, 15, 23, 59, 59)

        submissions = await db.get_by_date_range(
            sample_user_id, start_date, end_date, habit_id=habit1
        )

        assert len(submissions) == 1
        assert submissions[0]["habit_id"] == habit1

    @freeze_time("2024-01-15 14:30:00")
    async def test_has_submission_today_returns_true_when_submitted(
        self, submissions_collection, sample_habit_id, sample_user_id
    ):
        """has_submission_today should return True when user submitted today."""
        db = SubmissionsDB(submissions_collection)
        await db.create_submission(sample_habit_id, sample_user_id, "photo1")

        result = await db.has_submission_today(sample_user_id, sample_habit_id)

        assert result is True

    @freeze_time("2024-01-15 14:30:00")
    async def test_has_submission_today_returns_false_when_not_submitted(
        self, submissions_collection, sample_habit_id, sample_user_id
    ):
        """has_submission_today should return False when no submission today."""
        db = SubmissionsDB(submissions_collection)

        result = await db.has_submission_today(sample_user_id, sample_habit_id)

        assert result is False

    async def test_has_submission_today_ignores_yesterdays_submissions(
        self, submissions_collection, sample_habit_id, sample_user_id
    ):
        """has_submission_today should not count yesterday's submissions."""
        db = SubmissionsDB(submissions_collection)

        with freeze_time("2024-01-14 10:00:00"):
            await db.create_submission(sample_habit_id, sample_user_id, "photo1")

        with freeze_time("2024-01-15 10:00:00"):
            result = await db.has_submission_today(sample_user_id, sample_habit_id)

        assert result is False

    async def test_get_user_submissions(
        self, submissions_collection, sample_habit_id, sample_user_id
    ):
        """get_user_submissions should return all submissions for a user."""
        db = SubmissionsDB(submissions_collection)
        await db.create_submission(sample_habit_id, sample_user_id, "photo1")
        await db.create_submission(sample_habit_id, sample_user_id, "photo2")

        submissions = await db.get_user_submissions(sample_user_id)

        assert len(submissions) == 2

    async def test_get_user_submissions_filters_by_status(
        self, submissions_collection, sample_habit_id, sample_user_id, sample_admin_id
    ):
        """get_user_submissions should filter by status when provided."""
        db = SubmissionsDB(submissions_collection)
        await db.create_submission(sample_habit_id, sample_user_id, "photo1")
        sub_id = await db.create_submission(sample_habit_id, sample_user_id, "photo2")
        await db.approve_submission(sub_id, sample_admin_id)

        pending = await db.get_user_submissions(sample_user_id, status="pending")
        approved = await db.get_user_submissions(sample_user_id, status="approved")

        assert len(pending) == 1
        assert len(approved) == 1

    @freeze_time("2024-01-15 14:30:00")
    async def test_has_submission_today_ignores_rejected_submissions(
        self, submissions_collection, sample_habit_id, sample_user_id, sample_admin_id
    ):
        """
        BUG FIX TEST: has_submission_today should ignore rejected submissions.

        This allows users to resubmit after their proof photo was rejected.
        Only pending or approved submissions should count as "already submitted".
        """
        db = SubmissionsDB(submissions_collection)

        # Create and reject a submission
        sub_id = await db.create_submission(sample_habit_id, sample_user_id, "photo1")
        await db.reject_submission(sub_id, sample_admin_id, "Photo unclear")

        # User should be able to submit again - rejected submission doesn't count
        result = await db.has_submission_today(sample_user_id, sample_habit_id)

        assert result is False

    @freeze_time("2024-01-15 14:30:00")
    async def test_has_submission_today_counts_pending_submissions(
        self, submissions_collection, sample_habit_id, sample_user_id
    ):
        """has_submission_today should count pending submissions."""
        db = SubmissionsDB(submissions_collection)

        # Create a pending submission
        await db.create_submission(sample_habit_id, sample_user_id, "photo1")

        # Should return True - pending submission counts
        result = await db.has_submission_today(sample_user_id, sample_habit_id)

        assert result is True

    @freeze_time("2024-01-15 14:30:00")
    async def test_has_submission_today_counts_approved_submissions(
        self, submissions_collection, sample_habit_id, sample_user_id, sample_admin_id
    ):
        """has_submission_today should count approved submissions."""
        db = SubmissionsDB(submissions_collection)

        # Create and approve a submission
        sub_id = await db.create_submission(sample_habit_id, sample_user_id, "photo1")
        await db.approve_submission(sub_id, sample_admin_id)

        # Should return True - approved submission counts
        result = await db.has_submission_today(sample_user_id, sample_habit_id)

        assert result is True
