"""
Tests for the streak service.
Following TDD: These tests are written BEFORE the implementation.
"""

import pytest
from datetime import date, datetime, timedelta
from bson import ObjectId
from freezegun import freeze_time

from TelegramBot.database.streaks import StreaksDB
from TelegramBot.services.streak_service import StreakService


class TestStreakService:
    """Test suite for streak service business logic."""

    @pytest.fixture
    def streak_db(self, streaks_collection):
        """Create a StreaksDB instance."""
        return StreaksDB(streaks_collection)

    @pytest.fixture
    def streak_service(self, streak_db):
        """Create a StreakService instance."""
        return StreakService(streak_db)

    async def test_calculate_streak_returns_zero_for_new_user(
        self, streak_service, sample_user_id, sample_habit_id
    ):
        """calculate_streak should return 0 for user with no approvals."""
        streak = await streak_service.calculate_streak(sample_user_id, sample_habit_id)

        assert streak == 0

    async def test_calculate_streak_returns_current_streak(
        self, streak_service, streak_db, sample_user_id, sample_habit_id
    ):
        """calculate_streak should return current streak value."""
        await streak_db.get_or_create(sample_user_id, sample_habit_id)
        with freeze_time("2024-01-15"):
            await streak_db.increment_streak(sample_user_id, sample_habit_id)
        with freeze_time("2024-01-16"):
            await streak_db.increment_streak(sample_user_id, sample_habit_id)

        with freeze_time("2024-01-16"):
            streak = await streak_service.calculate_streak(sample_user_id, sample_habit_id)

        assert streak == 2

    @freeze_time("2024-01-17")
    async def test_on_approval_increments_streak(
        self, streak_service, streak_db, sample_user_id, sample_habit_id
    ):
        """on_approval should increment the streak."""
        await streak_db.get_or_create(sample_user_id, sample_habit_id)

        await streak_service.on_approval(sample_user_id, sample_habit_id)

        streak_data = await streak_db.get_streak(sample_user_id, sample_habit_id)
        assert streak_data["current_streak"] == 1
        assert streak_data["total_approved"] == 1

    async def test_on_approval_updates_longest_when_exceeded(
        self, streak_service, streak_db, sample_user_id, sample_habit_id
    ):
        """on_approval should update longest_streak when current exceeds it."""
        await streak_db.get_or_create(sample_user_id, sample_habit_id)

        for i in range(5):
            with freeze_time(f"2024-01-{15+i}"):
                await streak_service.on_approval(sample_user_id, sample_habit_id)

        streak_data = await streak_db.get_streak(sample_user_id, sample_habit_id)
        assert streak_data["current_streak"] == 5
        assert streak_data["longest_streak"] == 5

    async def test_missed_day_resets_streak(
        self, streak_service, streak_db, sample_user_id, sample_habit_id
    ):
        """check_and_reset_if_missed should reset streak if a day was missed."""
        await streak_db.get_or_create(sample_user_id, sample_habit_id)

        # Build up a streak
        with freeze_time("2024-01-15"):
            await streak_service.on_approval(sample_user_id, sample_habit_id)
        with freeze_time("2024-01-16"):
            await streak_service.on_approval(sample_user_id, sample_habit_id)

        # Check two days later (missed Jan 17)
        with freeze_time("2024-01-18"):
            was_reset = await streak_service.check_and_reset_if_missed(
                sample_user_id, sample_habit_id
            )

        assert was_reset is True
        streak_data = await streak_db.get_streak(sample_user_id, sample_habit_id)
        assert streak_data["current_streak"] == 0

    async def test_no_reset_if_submitted_yesterday(
        self, streak_service, streak_db, sample_user_id, sample_habit_id
    ):
        """check_and_reset_if_missed should not reset if submitted yesterday."""
        await streak_db.get_or_create(sample_user_id, sample_habit_id)

        with freeze_time("2024-01-15"):
            await streak_service.on_approval(sample_user_id, sample_habit_id)

        with freeze_time("2024-01-16"):
            was_reset = await streak_service.check_and_reset_if_missed(
                sample_user_id, sample_habit_id
            )

        assert was_reset is False
        streak_data = await streak_db.get_streak(sample_user_id, sample_habit_id)
        assert streak_data["current_streak"] == 1

    async def test_no_reset_if_submitted_today(
        self, streak_service, streak_db, sample_user_id, sample_habit_id
    ):
        """check_and_reset_if_missed should not reset if submitted today."""
        await streak_db.get_or_create(sample_user_id, sample_habit_id)

        with freeze_time("2024-01-15"):
            await streak_service.on_approval(sample_user_id, sample_habit_id)
            was_reset = await streak_service.check_and_reset_if_missed(
                sample_user_id, sample_habit_id
            )

        assert was_reset is False

    async def test_pending_submission_does_not_count(
        self, streak_service, streak_db, sample_user_id, sample_habit_id
    ):
        """Pending submissions should not affect streak calculation."""
        await streak_db.get_or_create(sample_user_id, sample_habit_id)

        # Only one approval
        with freeze_time("2024-01-15"):
            await streak_service.on_approval(sample_user_id, sample_habit_id)

        with freeze_time("2024-01-15"):
            streak = await streak_service.calculate_streak(sample_user_id, sample_habit_id)

        # Should only count the one approval
        assert streak == 1

    async def test_get_streak_stats_returns_full_data(
        self, streak_service, streak_db, sample_user_id, sample_habit_id
    ):
        """get_streak_stats should return comprehensive streak statistics."""
        await streak_db.get_or_create(sample_user_id, sample_habit_id)

        # Build some history
        for i in range(3):
            with freeze_time(f"2024-01-{15+i}"):
                await streak_service.on_approval(sample_user_id, sample_habit_id)

        with freeze_time("2024-01-17"):
            stats = await streak_service.get_streak_stats(sample_user_id, sample_habit_id)

        assert stats["current_streak"] == 3
        assert stats["longest_streak"] == 3
        assert stats["total_approved"] == 3
        assert stats["last_approved_date"] is not None

    async def test_get_all_user_streaks(
        self, streak_service, streak_db, sample_user_id
    ):
        """get_all_user_streaks should return streaks for all user's habits."""
        habit1 = ObjectId()
        habit2 = ObjectId()

        await streak_db.get_or_create(sample_user_id, habit1)
        await streak_db.get_or_create(sample_user_id, habit2)

        with freeze_time("2024-01-15"):
            await streak_service.on_approval(sample_user_id, habit1)
            await streak_service.on_approval(sample_user_id, habit2)
            await streak_service.on_approval(sample_user_id, habit2)

        streaks = await streak_service.get_all_user_streaks(sample_user_id)

        assert len(streaks) == 2
