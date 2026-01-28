"""
Tests for admin review commands plugin.
Following TDD: These tests are written BEFORE the implementation.
"""

import pytest
from bson import ObjectId
from freezegun import freeze_time
from unittest.mock import AsyncMock, MagicMock, patch

from TelegramBot.database.habits import HabitsDB
from TelegramBot.database.submissions import SubmissionsDB
from TelegramBot.database.streaks import StreaksDB
from TelegramBot.services.streak_service import StreakService
from TelegramBot.services.submission_service import SubmissionService


class TestAdminCommands:
    """Test suite for admin review commands."""

    @pytest.fixture
    def habits_db(self, habits_collection):
        return HabitsDB(habits_collection)

    @pytest.fixture
    def submissions_db(self, submissions_collection):
        return SubmissionsDB(submissions_collection)

    @pytest.fixture
    def streaks_db(self, streaks_collection):
        return StreaksDB(streaks_collection)

    @pytest.fixture
    def streak_service(self, streaks_db):
        return StreakService(streaks_db)

    @pytest.fixture
    def mock_client(self):
        client = MagicMock()
        client.send_message = AsyncMock()
        client.send_photo = AsyncMock()
        return client

    @pytest.fixture
    def submission_service(
        self, submissions_db, habits_db, streak_service, mock_client
    ):
        return SubmissionService(
            submissions_db=submissions_db,
            habits_db=habits_db,
            streak_service=streak_service,
            client=mock_client
        )

    @pytest.fixture
    def mock_admin_message(self, sample_admin_id):
        """Create a mock message from admin."""
        message = MagicMock()
        message.from_user = MagicMock()
        message.from_user.id = sample_admin_id
        message.chat = MagicMock()
        message.chat.id = sample_admin_id
        message.reply_text = AsyncMock()
        message.reply_photo = AsyncMock()
        message.command = []
        return message

    @pytest.fixture
    def mock_callback_query(self, sample_admin_id):
        """Create a mock callback query."""
        callback = MagicMock()
        callback.from_user = MagicMock()
        callback.from_user.id = sample_admin_id
        callback.message = MagicMock()
        callback.message.chat = MagicMock()
        callback.message.chat.id = sample_admin_id
        callback.message.reply_text = AsyncMock()
        callback.message.edit_caption = AsyncMock()
        callback.message.edit_text = AsyncMock()
        callback.answer = AsyncMock()
        callback.data = ""
        return callback

    async def test_pending_reviews_shows_all_pending(
        self, habits_db, submissions_db, mock_admin_message,
        mock_client, sample_user_id
    ):
        """pending_reviews should show all pending submissions."""
        from TelegramBot.plugins.sudo.reviews import pending_reviews_handler

        habit_id = await habits_db.create_habit(
            sample_user_id, "Exercise", "09:00", "UTC"
        )

        with freeze_time("2024-01-15"):
            await submissions_db.create_submission(habit_id, sample_user_id, "photo1")
        with freeze_time("2024-01-16"):
            await submissions_db.create_submission(habit_id, sample_user_id, "photo2")

        await pending_reviews_handler(
            mock_client, mock_admin_message, submissions_db, habits_db
        )

        mock_admin_message.reply_text.assert_called()
        text = mock_admin_message.reply_text.call_args[0][0]
        assert "2" in text or "pending" in text.lower()

    async def test_pending_reviews_shows_empty_message(
        self, submissions_db, habits_db, mock_admin_message, mock_client
    ):
        """pending_reviews should show message when no pending."""
        from TelegramBot.plugins.sudo.reviews import pending_reviews_handler

        await pending_reviews_handler(
            mock_client, mock_admin_message, submissions_db, habits_db
        )

        mock_admin_message.reply_text.assert_called()
        text = mock_admin_message.reply_text.call_args[0][0].lower()
        assert "no pending" in text or "empty" in text or "none" in text

    async def test_approve_callback_approves_submission(
        self, habits_db, submissions_db, streaks_db, submission_service,
        mock_callback_query, mock_client, sample_user_id, sample_admin_id
    ):
        """Approve callback should approve the submission."""
        from TelegramBot.plugins.sudo.reviews import approve_callback_handler

        habit_id = await habits_db.create_habit(
            sample_user_id, "Exercise", "09:00", "UTC"
        )

        with freeze_time("2024-01-15"):
            submission_id = await submissions_db.create_submission(
                habit_id, sample_user_id, "photo1"
            )

        mock_callback_query.data = f"approve:{submission_id}"

        await approve_callback_handler(
            mock_client, mock_callback_query, submission_service
        )

        submission = await submissions_db.get_submission(submission_id)
        assert submission["status"] == "approved"
        mock_callback_query.answer.assert_called()

    async def test_approve_callback_updates_streak(
        self, habits_db, submissions_db, streaks_db, submission_service,
        mock_callback_query, mock_client, sample_user_id, sample_admin_id
    ):
        """Approve callback should update user's streak."""
        from TelegramBot.plugins.sudo.reviews import approve_callback_handler

        habit_id = await habits_db.create_habit(
            sample_user_id, "Exercise", "09:00", "UTC"
        )

        with freeze_time("2024-01-15"):
            submission_id = await submissions_db.create_submission(
                habit_id, sample_user_id, "photo1"
            )
            mock_callback_query.data = f"approve:{submission_id}"

            await approve_callback_handler(
                mock_client, mock_callback_query, submission_service
            )

        streak = await streaks_db.get_streak(sample_user_id, habit_id)
        assert streak is not None
        assert streak["current_streak"] == 1

    async def test_reject_callback_rejects_submission(
        self, habits_db, submissions_db, submission_service,
        mock_callback_query, mock_client, sample_user_id, sample_admin_id
    ):
        """Reject callback should reject the submission."""
        from TelegramBot.plugins.sudo.reviews import reject_callback_handler

        habit_id = await habits_db.create_habit(
            sample_user_id, "Exercise", "09:00", "UTC"
        )

        with freeze_time("2024-01-15"):
            submission_id = await submissions_db.create_submission(
                habit_id, sample_user_id, "photo1"
            )

        mock_callback_query.data = f"reject:{submission_id}"

        await reject_callback_handler(
            mock_client, mock_callback_query, submission_service
        )

        submission = await submissions_db.get_submission(submission_id)
        assert submission["status"] == "rejected"
        mock_callback_query.answer.assert_called()

    async def test_reject_callback_does_not_update_streak(
        self, habits_db, submissions_db, streaks_db, submission_service,
        mock_callback_query, mock_client, sample_user_id, sample_admin_id
    ):
        """Reject callback should not update user's streak."""
        from TelegramBot.plugins.sudo.reviews import reject_callback_handler

        habit_id = await habits_db.create_habit(
            sample_user_id, "Exercise", "09:00", "UTC"
        )

        with freeze_time("2024-01-15"):
            submission_id = await submissions_db.create_submission(
                habit_id, sample_user_id, "photo1"
            )
            mock_callback_query.data = f"reject:{submission_id}"

            await reject_callback_handler(
                mock_client, mock_callback_query, submission_service
            )

        streak = await streaks_db.get_streak(sample_user_id, habit_id)
        # Streak should not exist or be 0
        assert streak is None or streak["current_streak"] == 0

    async def test_approve_notifies_user(
        self, habits_db, submissions_db, submission_service,
        mock_callback_query, mock_client, sample_user_id
    ):
        """Approve should notify the user."""
        from TelegramBot.plugins.sudo.reviews import approve_callback_handler

        habit_id = await habits_db.create_habit(
            sample_user_id, "Exercise", "09:00", "UTC"
        )

        with freeze_time("2024-01-15"):
            submission_id = await submissions_db.create_submission(
                habit_id, sample_user_id, "photo1"
            )
            mock_callback_query.data = f"approve:{submission_id}"

            await approve_callback_handler(
                mock_client, mock_callback_query, submission_service
            )

        # Check that user was notified
        mock_client.send_message.assert_called()

    async def test_reject_notifies_user(
        self, habits_db, submissions_db, submission_service,
        mock_callback_query, mock_client, sample_user_id
    ):
        """Reject should notify the user."""
        from TelegramBot.plugins.sudo.reviews import reject_callback_handler

        habit_id = await habits_db.create_habit(
            sample_user_id, "Exercise", "09:00", "UTC"
        )

        with freeze_time("2024-01-15"):
            submission_id = await submissions_db.create_submission(
                habit_id, sample_user_id, "photo1"
            )
            mock_callback_query.data = f"reject:{submission_id}"

            await reject_callback_handler(
                mock_client, mock_callback_query, submission_service
            )

        mock_client.send_message.assert_called()
