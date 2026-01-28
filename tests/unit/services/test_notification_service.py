"""
Tests for the notification service.
Following TDD: These tests are written BEFORE the implementation.
"""

import pytest
from datetime import datetime, timedelta
from bson import ObjectId
from freezegun import freeze_time
from unittest.mock import AsyncMock, MagicMock

from TelegramBot.database.habits import HabitsDB
from TelegramBot.database.submissions import SubmissionsDB
from TelegramBot.database.streaks import StreaksDB
from TelegramBot.services.notification_service import NotificationService


class TestNotificationService:
    """Test suite for notification service business logic."""

    @pytest.fixture
    def habits_db(self, habits_collection):
        """Create a HabitsDB instance."""
        return HabitsDB(habits_collection)

    @pytest.fixture
    def submissions_db(self, submissions_collection):
        """Create a SubmissionsDB instance."""
        return SubmissionsDB(submissions_collection)

    @pytest.fixture
    def streaks_db(self, streaks_collection):
        """Create a StreaksDB instance."""
        return StreaksDB(streaks_collection)

    @pytest.fixture
    def mock_client(self):
        """Create a mock Pyrogram client."""
        client = MagicMock()
        client.send_message = AsyncMock()
        return client

    @pytest.fixture
    def notification_service(
        self, habits_db, submissions_db, streaks_db, mock_client
    ):
        """Create a NotificationService instance."""
        return NotificationService(
            habits_db=habits_db,
            submissions_db=submissions_db,
            streaks_db=streaks_db,
            client=mock_client
        )

    @freeze_time("2024-01-15 09:00:00")
    async def test_get_users_due_returns_habits_at_current_time(
        self, notification_service, habits_db, sample_user_id
    ):
        """get_users_due should return habits scheduled for current time."""
        await habits_db.create_habit(sample_user_id, "Morning", "09:00", "UTC")
        await habits_db.create_habit(sample_user_id, "Evening", "18:00", "UTC")

        due = await notification_service.get_users_due("09:00")

        assert len(due) == 1
        assert due[0]["name"] == "Morning"

    @freeze_time("2024-01-15 09:00:00")
    async def test_get_users_due_excludes_already_submitted_today(
        self, notification_service, habits_db, submissions_db, sample_user_id
    ):
        """get_users_due should exclude users who already submitted today."""
        habit_id = await habits_db.create_habit(
            sample_user_id, "Morning", "09:00", "UTC"
        )
        await submissions_db.create_submission(habit_id, sample_user_id, "photo1")

        due = await notification_service.get_users_due("09:00")

        assert len(due) == 0

    @freeze_time("2024-01-15 09:00:00")
    async def test_get_users_due_includes_if_submitted_yesterday(
        self, notification_service, habits_db, submissions_db, sample_user_id
    ):
        """get_users_due should include users who submitted yesterday but not today."""
        habit_id = await habits_db.create_habit(
            sample_user_id, "Morning", "09:00", "UTC"
        )

        # Submit yesterday
        with freeze_time("2024-01-14 09:00:00"):
            await submissions_db.create_submission(habit_id, sample_user_id, "photo1")

        # Check today
        with freeze_time("2024-01-15 09:00:00"):
            due = await notification_service.get_users_due("09:00")

        assert len(due) == 1

    async def test_get_users_due_excludes_inactive_habits(
        self, notification_service, habits_db, sample_user_id
    ):
        """get_users_due should exclude deactivated habits."""
        habit_id = await habits_db.create_habit(
            sample_user_id, "Morning", "09:00", "UTC"
        )
        await habits_db.deactivate_habit(habit_id)

        with freeze_time("2024-01-15 09:00:00"):
            due = await notification_service.get_users_due("09:00")

        assert len(due) == 0

    @freeze_time("2024-01-15 09:00:00")
    async def test_send_reminder_sends_message(
        self, notification_service, habits_db, mock_client, sample_user_id
    ):
        """send_reminder should send a message to the user."""
        habit_id = await habits_db.create_habit(
            sample_user_id, "Morning Exercise", "09:00", "UTC"
        )

        await notification_service.send_reminder(sample_user_id, habit_id)

        mock_client.send_message.assert_called_once()
        call_args = mock_client.send_message.call_args
        assert call_args[1]["chat_id"] == sample_user_id

    @freeze_time("2024-01-15 09:00:00")
    async def test_reminder_content_includes_habit_name(
        self, notification_service, habits_db, mock_client, sample_user_id
    ):
        """Reminder message should include the habit name."""
        habit_id = await habits_db.create_habit(
            sample_user_id, "Morning Exercise", "09:00", "UTC"
        )

        await notification_service.send_reminder(sample_user_id, habit_id)

        call_args = mock_client.send_message.call_args
        assert "Morning Exercise" in call_args[1]["text"]

    @freeze_time("2024-01-15 09:00:00")
    async def test_reminder_content_includes_streak_info(
        self, notification_service, habits_db, streaks_db, mock_client, sample_user_id
    ):
        """Reminder message should include current streak info."""
        habit_id = await habits_db.create_habit(
            sample_user_id, "Exercise", "09:00", "UTC"
        )
        await streaks_db.get_or_create(sample_user_id, habit_id)

        # Build up a streak
        with freeze_time("2024-01-13"):
            await streaks_db.increment_streak(sample_user_id, habit_id)
        with freeze_time("2024-01-14"):
            await streaks_db.increment_streak(sample_user_id, habit_id)

        with freeze_time("2024-01-15 09:00:00"):
            await notification_service.send_reminder(sample_user_id, habit_id)

        call_args = mock_client.send_message.call_args
        text = call_args[1]["text"]
        assert "streak" in text.lower()
        assert "2" in text  # Current streak of 2

    async def test_send_all_reminders_sends_to_all_due_users(
        self, notification_service, habits_db, mock_client
    ):
        """send_all_reminders should send to all users due for reminders."""
        user1 = 111111
        user2 = 222222

        await habits_db.create_habit(user1, "Exercise", "09:00", "UTC")
        await habits_db.create_habit(user2, "Reading", "09:00", "UTC")

        with freeze_time("2024-01-15 09:00:00"):
            count = await notification_service.send_all_reminders("09:00")

        assert count == 2
        assert mock_client.send_message.call_count == 2

    async def test_send_all_reminders_returns_zero_when_none_due(
        self, notification_service, habits_db, mock_client
    ):
        """send_all_reminders should return 0 when no users are due."""
        await habits_db.create_habit(123, "Exercise", "18:00", "UTC")

        with freeze_time("2024-01-15 09:00:00"):
            count = await notification_service.send_all_reminders("09:00")

        assert count == 0
        mock_client.send_message.assert_not_called()

    @freeze_time("2024-01-15 09:00:00")
    async def test_streak_at_risk_warning(
        self, notification_service, habits_db, streaks_db, mock_client, sample_user_id
    ):
        """Reminder should warn if streak is at risk (submitted yesterday)."""
        habit_id = await habits_db.create_habit(
            sample_user_id, "Exercise", "09:00", "UTC"
        )

        # Build a streak with yesterday as last submission
        with freeze_time("2024-01-14"):
            await streaks_db.get_or_create(sample_user_id, habit_id)
            await streaks_db.increment_streak(sample_user_id, habit_id)

        with freeze_time("2024-01-15 09:00:00"):
            await notification_service.send_reminder(sample_user_id, habit_id)

        call_args = mock_client.send_message.call_args
        text = call_args[1]["text"].lower()
        # Should mention the streak is at risk or needs to submit today
        assert "don't lose" in text or "at risk" in text or "today" in text
