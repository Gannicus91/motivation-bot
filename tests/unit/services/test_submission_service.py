"""
Tests for the submission service.
Following TDD: These tests are written BEFORE the implementation.
"""

import pytest
from datetime import datetime
from bson import ObjectId
from freezegun import freeze_time
from unittest.mock import AsyncMock, MagicMock

from TelegramBot.database.submissions import SubmissionsDB
from TelegramBot.database.habits import HabitsDB
from TelegramBot.database.streaks import StreaksDB
from TelegramBot.services.submission_service import SubmissionService
from TelegramBot.services.streak_service import StreakService


class TestSubmissionService:
    """Test suite for submission service business logic."""

    @pytest.fixture
    def submissions_db(self, submissions_collection):
        """Create a SubmissionsDB instance."""
        return SubmissionsDB(submissions_collection)

    @pytest.fixture
    def habits_db(self, habits_collection):
        """Create a HabitsDB instance."""
        return HabitsDB(habits_collection)

    @pytest.fixture
    def streaks_db(self, streaks_collection):
        """Create a StreaksDB instance."""
        return StreaksDB(streaks_collection)

    @pytest.fixture
    def streak_service(self, streaks_db):
        """Create a StreakService instance."""
        return StreakService(streaks_db)

    @pytest.fixture
    def mock_client(self):
        """Create a mock Pyrogram client."""
        client = MagicMock()
        client.send_message = AsyncMock()
        return client

    @pytest.fixture
    def submission_service(
        self, submissions_db, habits_db, streak_service, mock_client
    ):
        """Create a SubmissionService instance."""
        return SubmissionService(
            submissions_db=submissions_db,
            habits_db=habits_db,
            streak_service=streak_service,
            client=mock_client
        )

    async def test_submit_requires_photo(
        self, submission_service, sample_user_id, sample_habit_id
    ):
        """submit should raise error if no photo provided."""
        with pytest.raises(ValueError, match="Photo is required"):
            await submission_service.submit(
                user_id=sample_user_id,
                habit_id=sample_habit_id,
                photo_file_id=None
            )

    async def test_submit_requires_existing_habit(
        self, submission_service, sample_user_id
    ):
        """submit should raise error if habit doesn't exist."""
        with pytest.raises(ValueError, match="Habit not found"):
            await submission_service.submit(
                user_id=sample_user_id,
                habit_id=ObjectId(),
                photo_file_id="photo123"
            )

    @freeze_time("2024-01-15 10:00:00")
    async def test_submit_allows_one_per_day(
        self, submission_service, habits_db, sample_user_id
    ):
        """submit should reject second submission on same day."""
        habit_id = await habits_db.create_habit(
            sample_user_id, "Exercise", "09:00", "UTC"
        )

        # First submission should succeed
        await submission_service.submit(sample_user_id, habit_id, "photo1")

        # Second submission same day should fail
        with pytest.raises(ValueError, match="Already submitted today"):
            await submission_service.submit(sample_user_id, habit_id, "photo2")

    @freeze_time("2024-01-15 10:00:00")
    async def test_submit_creates_pending_submission(
        self, submission_service, habits_db, submissions_db, sample_user_id
    ):
        """submit should create a pending submission."""
        habit_id = await habits_db.create_habit(
            sample_user_id, "Exercise", "09:00", "UTC"
        )

        submission_id = await submission_service.submit(
            sample_user_id, habit_id, "photo123"
        )

        submission = await submissions_db.get_submission(submission_id)
        assert submission is not None
        assert submission["status"] == "pending"
        assert submission["photo_file_id"] == "photo123"

    async def test_approve_updates_streak(
        self, submission_service, habits_db, submissions_db, streaks_db,
        sample_user_id, sample_admin_id
    ):
        """approve should update the user's streak."""
        habit_id = await habits_db.create_habit(
            sample_user_id, "Exercise", "09:00", "UTC"
        )

        with freeze_time("2024-01-15"):
            submission_id = await submission_service.submit(
                sample_user_id, habit_id, "photo123"
            )
            await submission_service.approve(submission_id, sample_admin_id)

        streak = await streaks_db.get_streak(sample_user_id, habit_id)
        assert streak["current_streak"] == 1
        assert streak["total_approved"] == 1

    async def test_approve_notifies_user(
        self, submission_service, habits_db, mock_client,
        sample_user_id, sample_admin_id
    ):
        """approve should send notification to user."""
        habit_id = await habits_db.create_habit(
            sample_user_id, "Exercise", "09:00", "UTC"
        )

        with freeze_time("2024-01-15"):
            submission_id = await submission_service.submit(
                sample_user_id, habit_id, "photo123"
            )
            await submission_service.approve(submission_id, sample_admin_id)

        mock_client.send_message.assert_called()
        call_args = mock_client.send_message.call_args
        assert call_args[1]["chat_id"] == sample_user_id
        assert "approved" in call_args[1]["text"].lower()

    async def test_reject_notifies_user_with_reason(
        self, submission_service, habits_db, mock_client,
        sample_user_id, sample_admin_id
    ):
        """reject should notify user with rejection reason."""
        habit_id = await habits_db.create_habit(
            sample_user_id, "Exercise", "09:00", "UTC"
        )

        with freeze_time("2024-01-15"):
            submission_id = await submission_service.submit(
                sample_user_id, habit_id, "photo123"
            )
            await submission_service.reject(
                submission_id, sample_admin_id, "Photo not clear"
            )

        mock_client.send_message.assert_called()
        call_args = mock_client.send_message.call_args
        assert call_args[1]["chat_id"] == sample_user_id
        assert "rejected" in call_args[1]["text"].lower()
        assert "Photo not clear" in call_args[1]["text"]

    async def test_reject_does_not_update_streak(
        self, submission_service, habits_db, streaks_db,
        sample_user_id, sample_admin_id
    ):
        """reject should not update the user's streak."""
        habit_id = await habits_db.create_habit(
            sample_user_id, "Exercise", "09:00", "UTC"
        )

        with freeze_time("2024-01-15"):
            submission_id = await submission_service.submit(
                sample_user_id, habit_id, "photo123"
            )
            await submission_service.reject(
                submission_id, sample_admin_id, "Not valid"
            )

        streak = await streaks_db.get_streak(sample_user_id, habit_id)
        # Streak should not exist or be 0
        assert streak is None or streak["current_streak"] == 0

    async def test_get_pending_returns_pending_submissions(
        self, submission_service, habits_db, sample_user_id, sample_admin_id
    ):
        """get_pending should return all pending submissions."""
        habit_id = await habits_db.create_habit(
            sample_user_id, "Exercise", "09:00", "UTC"
        )

        with freeze_time("2024-01-15"):
            await submission_service.submit(sample_user_id, habit_id, "photo1")

        with freeze_time("2024-01-16"):
            submission_id = await submission_service.submit(
                sample_user_id, habit_id, "photo2"
            )
            await submission_service.approve(submission_id, sample_admin_id)

        with freeze_time("2024-01-17"):
            await submission_service.submit(sample_user_id, habit_id, "photo3")

        pending = await submission_service.get_pending()
        assert len(pending) == 2

    async def test_get_submission_details_includes_habit_info(
        self, submission_service, habits_db, sample_user_id
    ):
        """get_submission_details should include habit information."""
        habit_id = await habits_db.create_habit(
            sample_user_id, "Morning Exercise", "09:00", "UTC"
        )

        with freeze_time("2024-01-15"):
            submission_id = await submission_service.submit(
                sample_user_id, habit_id, "photo123"
            )

        details = await submission_service.get_submission_details(submission_id)

        assert details is not None
        assert details["habit_name"] == "Morning Exercise"
        assert details["user_id"] == sample_user_id
