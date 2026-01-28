"""
Tests for photo handler plugin.
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


class TestPhotoHandler:
    """Test suite for photo submission handler."""

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
        client.forward_messages = AsyncMock()
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
    def mock_photo_message(self, sample_user_id):
        """Create a mock message with a photo."""
        message = MagicMock()
        message.from_user = MagicMock()
        message.from_user.id = sample_user_id
        message.from_user.first_name = "Test"
        message.chat = MagicMock()
        message.chat.id = sample_user_id
        message.reply_text = AsyncMock()
        message.photo = MagicMock()
        message.photo.file_id = "AgACAgIAAxkBAAI_test_photo"
        message.forward = AsyncMock()
        return message

    @freeze_time("2024-01-15 10:00:00")
    async def test_photo_creates_submission(
        self, habits_db, submissions_db, submission_service,
        mock_photo_message, sample_user_id
    ):
        """Receiving a photo should create a pending submission."""
        from TelegramBot.plugins.users.photo_handler import handle_photo_submission

        habit_id = await habits_db.create_habit(
            sample_user_id, "Exercise", "09:00", "UTC"
        )

        await handle_photo_submission(
            None, mock_photo_message, habits_db, submission_service
        )

        # Check submission was created
        submissions = await submissions_db.get_user_submissions(sample_user_id)
        assert len(submissions) == 1
        assert submissions[0]["status"] == "pending"

    async def test_photo_requires_active_habit(
        self, habits_db, submission_service, mock_photo_message, sample_user_id
    ):
        """Should notify user if they have no active habits."""
        from TelegramBot.plugins.users.photo_handler import handle_photo_submission

        await handle_photo_submission(
            None, mock_photo_message, habits_db, submission_service
        )

        mock_photo_message.reply_text.assert_called()
        text = mock_photo_message.reply_text.call_args[0][0].lower()
        assert "no habit" in text or "no active" in text

    @freeze_time("2024-01-15 10:00:00")
    async def test_photo_asks_which_habit_when_multiple(
        self, habits_db, submission_service, mock_photo_message, sample_user_id
    ):
        """Should ask which habit if user has multiple."""
        from TelegramBot.plugins.users.photo_handler import handle_photo_submission

        await habits_db.create_habit(sample_user_id, "Exercise", "09:00", "UTC")
        await habits_db.create_habit(sample_user_id, "Reading", "20:00", "UTC")

        await handle_photo_submission(
            None, mock_photo_message, habits_db, submission_service
        )

        mock_photo_message.reply_text.assert_called()
        text = mock_photo_message.reply_text.call_args[0][0]
        # Should present options or ask which habit
        assert "Exercise" in text or "which" in text.lower()

    @freeze_time("2024-01-15 10:00:00")
    async def test_photo_auto_submits_for_single_habit(
        self, habits_db, submissions_db, submission_service,
        mock_photo_message, sample_user_id
    ):
        """Should auto-submit if user has only one habit."""
        from TelegramBot.plugins.users.photo_handler import handle_photo_submission

        habit_id = await habits_db.create_habit(
            sample_user_id, "Exercise", "09:00", "UTC"
        )

        await handle_photo_submission(
            None, mock_photo_message, habits_db, submission_service
        )

        submissions = await submissions_db.get_user_submissions(sample_user_id)
        assert len(submissions) == 1

    @freeze_time("2024-01-15 10:00:00")
    async def test_photo_confirms_submission(
        self, habits_db, submission_service, mock_photo_message, sample_user_id
    ):
        """Should confirm successful submission to user."""
        from TelegramBot.plugins.users.photo_handler import handle_photo_submission

        await habits_db.create_habit(sample_user_id, "Exercise", "09:00", "UTC")

        await handle_photo_submission(
            None, mock_photo_message, habits_db, submission_service
        )

        mock_photo_message.reply_text.assert_called()
        text = mock_photo_message.reply_text.call_args[0][0].lower()
        assert "submitted" in text or "received" in text or "pending" in text

    @freeze_time("2024-01-15 10:00:00")
    async def test_photo_rejects_duplicate_submission(
        self, habits_db, submissions_db, submission_service,
        mock_photo_message, sample_user_id
    ):
        """Should reject second photo submission on same day."""
        from TelegramBot.plugins.users.photo_handler import handle_photo_submission

        habit_id = await habits_db.create_habit(
            sample_user_id, "Exercise", "09:00", "UTC"
        )
        # First submission
        await submissions_db.create_submission(
            habit_id, sample_user_id, "first_photo"
        )

        # Try second
        await handle_photo_submission(
            None, mock_photo_message, habits_db, submission_service
        )

        mock_photo_message.reply_text.assert_called()
        text = mock_photo_message.reply_text.call_args[0][0].lower()
        assert "already" in text

    async def test_forwards_to_admin(
        self, habits_db, submission_service, mock_photo_message,
        mock_client, sample_user_id, sample_admin_id
    ):
        """Should forward submission to admin for review."""
        from TelegramBot.plugins.users.photo_handler import handle_photo_submission

        await habits_db.create_habit(sample_user_id, "Exercise", "09:00", "UTC")

        with freeze_time("2024-01-15 10:00:00"):
            # Mock admin IDs
            with patch(
                'TelegramBot.plugins.users.photo_handler.get_admin_ids',
                return_value=[sample_admin_id]
            ):
                await handle_photo_submission(
                    mock_client, mock_photo_message, habits_db, submission_service
                )

        # Check that forward or send_photo was called
        assert (
            mock_client.send_message.called or
            mock_client.send_photo.called or
            mock_photo_message.forward.called
        )
