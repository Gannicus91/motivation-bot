"""
Tests for user commands plugin.
Following TDD: These tests are written BEFORE the implementation.
"""

import pytest
from datetime import datetime
from bson import ObjectId
from freezegun import freeze_time
from unittest.mock import AsyncMock, MagicMock, patch

from TelegramBot.database.habits import HabitsDB
from TelegramBot.database.submissions import SubmissionsDB
from TelegramBot.database.streaks import StreaksDB
from TelegramBot.services.streak_service import StreakService


class TestUserHabitCommands:
    """Test suite for user habit commands."""

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
    def mock_message(self, sample_user_id):
        """Create a mock Pyrogram Message."""
        message = MagicMock()
        message.from_user = MagicMock()
        message.from_user.id = sample_user_id
        message.from_user.first_name = "Test"
        message.chat = MagicMock()
        message.chat.id = sample_user_id
        message.reply_text = AsyncMock()
        message.reply_photo = AsyncMock()
        message.command = []
        message.text = ""
        return message

    async def test_add_habit_creates_habit(
        self, habits_db, mock_message, sample_user_id
    ):
        """add_habit command should create a new habit."""
        from TelegramBot.plugins.users.habits import add_habit_handler

        mock_message.command = ["add_habit", "Morning", "Exercise"]
        mock_message.text = "/add_habit Morning Exercise"

        await add_habit_handler(None, mock_message, habits_db)

        habits = await habits_db.get_user_habits(sample_user_id)
        assert len(habits) == 1
        assert habits[0]["name"] == "Morning Exercise"

    async def test_add_habit_requires_name(
        self, habits_db, mock_message, sample_user_id
    ):
        """add_habit should require a habit name."""
        from TelegramBot.plugins.users.habits import add_habit_handler

        mock_message.command = ["add_habit"]
        mock_message.text = "/add_habit"

        await add_habit_handler(None, mock_message, habits_db)

        mock_message.reply_text.assert_called()
        call_args = mock_message.reply_text.call_args
        assert "usage" in call_args[0][0].lower() or "name" in call_args[0][0].lower()

    async def test_add_habit_with_notification_time(
        self, habits_db, mock_message, sample_user_id
    ):
        """add_habit should accept optional notification time."""
        from TelegramBot.plugins.users.habits import add_habit_handler

        mock_message.command = ["add_habit", "Exercise", "09:00"]
        mock_message.text = "/add_habit Exercise 09:00"

        await add_habit_handler(None, mock_message, habits_db)

        habits = await habits_db.get_user_habits(sample_user_id)
        assert habits[0]["notification_time"] == "09:00"

    async def test_my_habits_shows_user_habits(
        self, habits_db, mock_message, sample_user_id
    ):
        """my_habits command should list user's active habits."""
        from TelegramBot.plugins.users.habits import my_habits_handler

        await habits_db.create_habit(sample_user_id, "Exercise", "09:00", "UTC")
        await habits_db.create_habit(sample_user_id, "Reading", "20:00", "UTC")

        await my_habits_handler(None, mock_message, habits_db)

        mock_message.reply_text.assert_called()
        text = mock_message.reply_text.call_args[0][0]
        assert "Exercise" in text
        assert "Reading" in text

    async def test_my_habits_shows_empty_message(
        self, habits_db, mock_message, sample_user_id
    ):
        """my_habits should show message when no habits exist."""
        from TelegramBot.plugins.users.habits import my_habits_handler

        await my_habits_handler(None, mock_message, habits_db)

        mock_message.reply_text.assert_called()
        text = mock_message.reply_text.call_args[0][0].lower()
        assert "no habits" in text or "no active" in text

    async def test_progress_shows_streak_info(
        self, habits_db, streaks_db, streak_service, mock_message, sample_user_id
    ):
        """progress command should show streak statistics."""
        from TelegramBot.plugins.users.habits import progress_handler

        habit_id = await habits_db.create_habit(
            sample_user_id, "Exercise", "09:00", "UTC"
        )
        await streaks_db.get_or_create(sample_user_id, habit_id)

        with freeze_time("2024-01-15"):
            await streak_service.on_approval(sample_user_id, habit_id)
        with freeze_time("2024-01-16"):
            await streak_service.on_approval(sample_user_id, habit_id)

        with freeze_time("2024-01-16"):
            await progress_handler(None, mock_message, habits_db, streaks_db)

        mock_message.reply_text.assert_called()
        text = mock_message.reply_text.call_args[0][0]
        assert "Exercise" in text
        assert "2" in text  # Current streak

    async def test_progress_shows_longest_streak(
        self, habits_db, streaks_db, streak_service, mock_message, sample_user_id
    ):
        """progress should show longest streak."""
        from TelegramBot.plugins.users.habits import progress_handler

        habit_id = await habits_db.create_habit(
            sample_user_id, "Exercise", "09:00", "UTC"
        )
        await streaks_db.get_or_create(sample_user_id, habit_id)

        # Build a streak
        for i in range(5):
            with freeze_time(f"2024-01-{10+i}"):
                await streak_service.on_approval(sample_user_id, habit_id)

        # Reset and build smaller streak
        await streaks_db.reset_streak(sample_user_id, habit_id)
        with freeze_time("2024-01-20"):
            await streak_service.on_approval(sample_user_id, habit_id)

        with freeze_time("2024-01-20"):
            await progress_handler(None, mock_message, habits_db, streaks_db)

        text = mock_message.reply_text.call_args[0][0]
        assert "5" in text  # Longest streak should still be 5

    async def test_delete_habit_deactivates(
        self, habits_db, mock_message, sample_user_id
    ):
        """delete_habit command should deactivate the habit."""
        from TelegramBot.plugins.users.habits import delete_habit_handler

        habit_id = await habits_db.create_habit(
            sample_user_id, "Exercise", "09:00", "UTC"
        )

        mock_message.command = ["delete_habit", str(habit_id)]

        await delete_habit_handler(None, mock_message, habits_db)

        habits = await habits_db.get_user_habits(sample_user_id)
        assert len(habits) == 0  # Should not show in active habits
