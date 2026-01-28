"""
Tests for the streaks database module.
Following TDD: These tests are written BEFORE the implementation.
"""

import pytest
from datetime import date, timedelta
from bson import ObjectId
from freezegun import freeze_time

from TelegramBot.database.streaks import StreaksDB


class TestStreaksDatabase:
    """Test suite for streaks database operations."""

    async def test_get_or_create_creates_new_streak(
        self, streaks_collection, sample_user_id, sample_habit_id
    ):
        """get_or_create should create a new streak if none exists."""
        db = StreaksDB(streaks_collection)

        streak = await db.get_or_create(sample_user_id, sample_habit_id)

        assert streak is not None
        assert streak["user_id"] == sample_user_id
        assert streak["habit_id"] == sample_habit_id
        assert streak["current_streak"] == 0
        assert streak["longest_streak"] == 0
        assert streak["total_approved"] == 0
        assert streak["last_approved_date"] is None

    async def test_get_or_create_returns_existing_streak(
        self, streaks_collection, sample_user_id, sample_habit_id
    ):
        """get_or_create should return existing streak if one exists."""
        db = StreaksDB(streaks_collection)

        # Create initial streak
        await db.get_or_create(sample_user_id, sample_habit_id)
        # Increment to modify it
        await db.increment_streak(sample_user_id, sample_habit_id)

        # Get again
        streak = await db.get_or_create(sample_user_id, sample_habit_id)

        assert streak["current_streak"] == 1

    @freeze_time("2024-01-15")
    async def test_increment_streak_increments_current(
        self, streaks_collection, sample_user_id, sample_habit_id
    ):
        """increment_streak should increase current_streak by 1."""
        db = StreaksDB(streaks_collection)
        await db.get_or_create(sample_user_id, sample_habit_id)

        result = await db.increment_streak(sample_user_id, sample_habit_id)

        streak = await db.get_or_create(sample_user_id, sample_habit_id)
        assert result is True
        assert streak["current_streak"] == 1
        assert streak["total_approved"] == 1
        # Stored as datetime for MongoDB compatibility, check the date portion
        assert streak["last_approved_date"].date() == date(2024, 1, 15)

    async def test_increment_streak_updates_longest_when_exceeded(
        self, streaks_collection, sample_user_id, sample_habit_id
    ):
        """increment_streak should update longest_streak when current exceeds it."""
        db = StreaksDB(streaks_collection)
        await db.get_or_create(sample_user_id, sample_habit_id)

        # Increment multiple times
        for i in range(5):
            with freeze_time(f"2024-01-{15+i}"):
                await db.increment_streak(sample_user_id, sample_habit_id)

        streak = await db.get_or_create(sample_user_id, sample_habit_id)
        assert streak["current_streak"] == 5
        assert streak["longest_streak"] == 5

    async def test_reset_streak_sets_current_to_zero(
        self, streaks_collection, sample_user_id, sample_habit_id
    ):
        """reset_streak should set current_streak to 0."""
        db = StreaksDB(streaks_collection)
        await db.get_or_create(sample_user_id, sample_habit_id)

        # Build up a streak
        with freeze_time("2024-01-15"):
            await db.increment_streak(sample_user_id, sample_habit_id)
        with freeze_time("2024-01-16"):
            await db.increment_streak(sample_user_id, sample_habit_id)

        # Reset it
        result = await db.reset_streak(sample_user_id, sample_habit_id)

        streak = await db.get_or_create(sample_user_id, sample_habit_id)
        assert result is True
        assert streak["current_streak"] == 0

    async def test_reset_streak_preserves_longest(
        self, streaks_collection, sample_user_id, sample_habit_id
    ):
        """reset_streak should not modify longest_streak."""
        db = StreaksDB(streaks_collection)
        await db.get_or_create(sample_user_id, sample_habit_id)

        # Build up a streak
        for i in range(3):
            with freeze_time(f"2024-01-{15+i}"):
                await db.increment_streak(sample_user_id, sample_habit_id)

        # Reset it
        await db.reset_streak(sample_user_id, sample_habit_id)

        streak = await db.get_or_create(sample_user_id, sample_habit_id)
        assert streak["current_streak"] == 0
        assert streak["longest_streak"] == 3

    async def test_reset_streak_preserves_total_approved(
        self, streaks_collection, sample_user_id, sample_habit_id
    ):
        """reset_streak should not modify total_approved."""
        db = StreaksDB(streaks_collection)
        await db.get_or_create(sample_user_id, sample_habit_id)

        # Build up a streak
        for i in range(3):
            with freeze_time(f"2024-01-{15+i}"):
                await db.increment_streak(sample_user_id, sample_habit_id)

        # Reset it
        await db.reset_streak(sample_user_id, sample_habit_id)

        streak = await db.get_or_create(sample_user_id, sample_habit_id)
        assert streak["total_approved"] == 3

    async def test_update_longest_updates_when_greater(
        self, streaks_collection, sample_user_id, sample_habit_id
    ):
        """update_longest should update longest_streak when new value is greater."""
        db = StreaksDB(streaks_collection)
        await db.get_or_create(sample_user_id, sample_habit_id)

        result = await db.update_longest(sample_user_id, sample_habit_id, 10)

        streak = await db.get_or_create(sample_user_id, sample_habit_id)
        assert result is True
        assert streak["longest_streak"] == 10

    async def test_update_longest_does_not_update_when_smaller(
        self, streaks_collection, sample_user_id, sample_habit_id
    ):
        """update_longest should not update if new value is smaller."""
        db = StreaksDB(streaks_collection)
        await db.get_or_create(sample_user_id, sample_habit_id)
        await db.update_longest(sample_user_id, sample_habit_id, 10)

        result = await db.update_longest(sample_user_id, sample_habit_id, 5)

        streak = await db.get_or_create(sample_user_id, sample_habit_id)
        assert result is False
        assert streak["longest_streak"] == 10

    async def test_get_user_streaks_returns_all_streaks(
        self, streaks_collection, sample_user_id
    ):
        """get_user_streaks should return all streaks for a user."""
        db = StreaksDB(streaks_collection)
        habit1 = ObjectId()
        habit2 = ObjectId()
        habit3 = ObjectId()

        await db.get_or_create(sample_user_id, habit1)
        await db.get_or_create(sample_user_id, habit2)
        await db.get_or_create(sample_user_id, habit3)

        streaks = await db.get_user_streaks(sample_user_id)

        assert len(streaks) == 3

    async def test_get_user_streaks_empty_for_nonexistent_user(
        self, streaks_collection
    ):
        """get_user_streaks should return empty list for user with no streaks."""
        db = StreaksDB(streaks_collection)
        streaks = await db.get_user_streaks(999999999)

        assert streaks == []

    async def test_get_streak_returns_specific_habit_streak(
        self, streaks_collection, sample_user_id, sample_habit_id
    ):
        """get_streak should return streak for specific habit."""
        db = StreaksDB(streaks_collection)
        await db.get_or_create(sample_user_id, sample_habit_id)
        await db.increment_streak(sample_user_id, sample_habit_id)

        streak = await db.get_streak(sample_user_id, sample_habit_id)

        assert streak is not None
        assert streak["current_streak"] == 1

    async def test_get_streak_returns_none_for_nonexistent(
        self, streaks_collection, sample_user_id
    ):
        """get_streak should return None if no streak exists."""
        db = StreaksDB(streaks_collection)
        streak = await db.get_streak(sample_user_id, ObjectId())

        assert streak is None

    async def test_delete_streak(
        self, streaks_collection, sample_user_id, sample_habit_id
    ):
        """delete_streak should remove the streak document."""
        db = StreaksDB(streaks_collection)
        await db.get_or_create(sample_user_id, sample_habit_id)

        result = await db.delete_streak(sample_user_id, sample_habit_id)

        assert result is True
        streak = await db.get_streak(sample_user_id, sample_habit_id)
        assert streak is None
