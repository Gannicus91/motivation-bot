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


class TestMultiHabitPhotoSubmission:
    """Tests for multi-habit photo submission with callback handling."""

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

    @pytest.fixture
    def mock_callback_query(self, sample_user_id):
        """Create a mock callback query for habit selection."""
        callback = MagicMock()
        callback.from_user = MagicMock()
        callback.from_user.id = sample_user_id
        callback.from_user.first_name = "Test"
        callback.message = MagicMock()
        callback.message.chat = MagicMock()
        callback.message.chat.id = sample_user_id
        callback.data = ""
        callback.answer = AsyncMock()
        callback.edit_message_text = AsyncMock()
        return callback

    @freeze_time("2024-01-15 10:00:00")
    async def test_multi_habit_photo_stores_pending(
        self, habits_db, submission_service, mock_photo_message, sample_user_id
    ):
        """Photo is cached when user has multiple habits."""
        from TelegramBot.plugins.users.photo_handler import (
            handle_photo_submission,
            pending_photos
        )

        # Clear any previous pending photos
        pending_photos.clear()

        # Create two habits
        await habits_db.create_habit(sample_user_id, "Exercise", "09:00", "UTC")
        await habits_db.create_habit(sample_user_id, "Reading", "20:00", "UTC")

        await handle_photo_submission(
            None, mock_photo_message, habits_db, submission_service
        )

        # Photo should be stored in pending_photos cache
        assert sample_user_id in pending_photos
        assert pending_photos[sample_user_id]["photo_file_id"] == "AgACAgIAAxkBAAI_test_photo"

    @freeze_time("2024-01-15 10:00:00")
    async def test_submit_callback_creates_submission(
        self, habits_db, submissions_db, submission_service,
        mock_photo_message, mock_callback_query, mock_client,
        sample_user_id, sample_admin_id
    ):
        """Callback handler processes selection and creates submission."""
        from TelegramBot.plugins.users.photo_handler import (
            handle_photo_submission,
            handle_submit_callback,
            pending_photos
        )

        # Clear any previous pending photos
        pending_photos.clear()

        # Create two habits
        habit1_id = await habits_db.create_habit(sample_user_id, "Exercise", "09:00", "UTC")
        await habits_db.create_habit(sample_user_id, "Reading", "20:00", "UTC")

        # User sends photo - should store in pending
        await handle_photo_submission(
            mock_client, mock_photo_message, habits_db, submission_service
        )

        # Set callback data to select first habit
        mock_callback_query.data = f"submit:{habit1_id}"

        # Mock admin IDs for forwarding
        with patch(
            'TelegramBot.plugins.users.photo_handler.get_admin_ids',
            return_value=[sample_admin_id]
        ):
            await handle_submit_callback(
                mock_client, mock_callback_query, habits_db, submission_service
            )

        # Check submission was created
        submissions = await submissions_db.get_user_submissions(sample_user_id)
        assert len(submissions) == 1
        assert submissions[0]["habit_id"] == habit1_id
        assert submissions[0]["status"] == "pending"

    @freeze_time("2024-01-15 10:00:00")
    async def test_submit_callback_clears_cache(
        self, habits_db, submissions_db, submission_service,
        mock_photo_message, mock_callback_query, mock_client,
        sample_user_id, sample_admin_id
    ):
        """Photo is removed from cache after submission."""
        from TelegramBot.plugins.users.photo_handler import (
            handle_photo_submission,
            handle_submit_callback,
            pending_photos
        )

        # Clear any previous pending photos
        pending_photos.clear()

        # Create two habits
        habit1_id = await habits_db.create_habit(sample_user_id, "Exercise", "09:00", "UTC")
        await habits_db.create_habit(sample_user_id, "Reading", "20:00", "UTC")

        # User sends photo
        await handle_photo_submission(
            mock_client, mock_photo_message, habits_db, submission_service
        )

        # Verify it's cached
        assert sample_user_id in pending_photos

        # User clicks habit button
        mock_callback_query.data = f"submit:{habit1_id}"

        with patch(
            'TelegramBot.plugins.users.photo_handler.get_admin_ids',
            return_value=[sample_admin_id]
        ):
            await handle_submit_callback(
                mock_client, mock_callback_query, habits_db, submission_service
            )

        # Cache should be cleared
        assert sample_user_id not in pending_photos

    @freeze_time("2024-01-15 10:00:00")
    async def test_submit_callback_forwards_to_admin(
        self, habits_db, submission_service, mock_photo_message,
        mock_callback_query, mock_client, sample_user_id, sample_admin_id
    ):
        """Admin receives the photo after callback selection."""
        from TelegramBot.plugins.users.photo_handler import (
            handle_photo_submission,
            handle_submit_callback,
            pending_photos
        )

        # Clear any previous pending photos
        pending_photos.clear()

        # Create two habits
        habit1_id = await habits_db.create_habit(sample_user_id, "Exercise", "09:00", "UTC")
        await habits_db.create_habit(sample_user_id, "Reading", "20:00", "UTC")

        # User sends photo
        await handle_photo_submission(
            mock_client, mock_photo_message, habits_db, submission_service
        )

        # User clicks habit button
        mock_callback_query.data = f"submit:{habit1_id}"

        with patch(
            'TelegramBot.plugins.users.photo_handler.get_admin_ids',
            return_value=[sample_admin_id]
        ):
            await handle_submit_callback(
                mock_client, mock_callback_query, habits_db, submission_service
            )

        # Admin should receive the photo
        mock_client.send_photo.assert_called()
        call_kwargs = mock_client.send_photo.call_args
        assert call_kwargs[1]["chat_id"] == sample_admin_id
        assert "Exercise" in call_kwargs[1]["caption"]

    @freeze_time("2024-01-15 10:00:00")
    async def test_submit_callback_expired_session(
        self, habits_db, submission_service, mock_callback_query,
        mock_client, sample_user_id
    ):
        """Expired session (no cached photo) shows error."""
        from TelegramBot.plugins.users.photo_handler import (
            handle_submit_callback,
            pending_photos
        )

        # Clear cache - no pending photos
        pending_photos.clear()

        habit_id = await habits_db.create_habit(sample_user_id, "Exercise", "09:00", "UTC")

        # User clicks button without having sent a photo first
        mock_callback_query.data = f"submit:{habit_id}"

        await handle_submit_callback(
            mock_client, mock_callback_query, habits_db, submission_service
        )

        # Should answer with error
        mock_callback_query.answer.assert_called()
        answer_text = mock_callback_query.answer.call_args[0][0].lower()
        assert "expired" in answer_text or "again" in answer_text

    @freeze_time("2024-01-15 10:00:00")
    async def test_submit_callback_answers_to_stop_loading(
        self, habits_db, submission_service, mock_photo_message,
        mock_callback_query, mock_client, sample_user_id, sample_admin_id
    ):
        """Callback query is answered to stop the loading spinner."""
        from TelegramBot.plugins.users.photo_handler import (
            handle_photo_submission,
            handle_submit_callback,
            pending_photos
        )

        pending_photos.clear()

        habit_id = await habits_db.create_habit(sample_user_id, "Exercise", "09:00", "UTC")
        await habits_db.create_habit(sample_user_id, "Reading", "20:00", "UTC")

        await handle_photo_submission(
            mock_client, mock_photo_message, habits_db, submission_service
        )

        mock_callback_query.data = f"submit:{habit_id}"

        with patch(
            'TelegramBot.plugins.users.photo_handler.get_admin_ids',
            return_value=[sample_admin_id]
        ):
            await handle_submit_callback(
                mock_client, mock_callback_query, habits_db, submission_service
            )

        # Callback should be answered (stops loading indicator)
        mock_callback_query.answer.assert_called()

    @freeze_time("2024-01-15 10:00:00")
    async def test_user_can_resubmit_after_rejection(
        self, habits_db, submissions_db, submission_service,
        mock_photo_message, sample_user_id, sample_admin_id
    ):
        """
        BUG FIX TEST: User should be able to resubmit photo after rejection.

        This test demonstrates the bug where users cannot resubmit after
        their proof photo was rejected by admin.
        """
        from TelegramBot.plugins.users.photo_handler import handle_photo_submission

        # Create habit
        habit_id = await habits_db.create_habit(
            sample_user_id, "Morning Exercise", "09:00", "UTC"
        )

        # User submits first photo
        first_submission_id = await submissions_db.create_submission(
            habit_id, sample_user_id, "first_photo_file_id"
        )

        # Admin rejects it
        await submissions_db.reject_submission(
            first_submission_id, sample_admin_id, "Photo unclear"
        )

        # User tries to submit again (THIS SHOULD WORK)
        await handle_photo_submission(
            None, mock_photo_message, habits_db, submission_service
        )

        # Should succeed - check confirmation message
        mock_photo_message.reply_text.assert_called()
        text = mock_photo_message.reply_text.call_args[0][0].lower()

        # Should show success message, not error
        assert "submitted" in text or "pending" in text
        assert "already" not in text

        # Verify new submission was created
        submissions = await submissions_db.get_user_submissions(sample_user_id)
        assert len(submissions) == 2  # Old rejected + new pending

        # Check the new submission is pending
        pending_submissions = [s for s in submissions if s["status"] == "pending"]
        assert len(pending_submissions) == 1
        assert pending_submissions[0]["photo_file_id"] == "AgACAgIAAxkBAAI_test_photo"
