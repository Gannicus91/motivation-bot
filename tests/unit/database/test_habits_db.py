"""
Tests for the habits database module.
Following TDD: These tests are written BEFORE the implementation.
"""

import pytest
from datetime import datetime
from bson import ObjectId

from TelegramBot.database.habits import HabitsDB


class TestHabitsDatabase:
    """Test suite for habits database operations."""

    async def test_create_habit_returns_object_id(self, habits_collection, sample_user_id):
        """Creating a habit should return an ObjectId."""
        db = HabitsDB(habits_collection)
        habit_id = await db.create_habit(
            user_id=sample_user_id,
            name="Morning Exercise",
            notification_time="09:00",
            timezone="UTC"
        )

        assert isinstance(habit_id, ObjectId)

    async def test_create_habit_stores_correct_data(self, habits_collection, sample_user_id):
        """Created habit should contain all provided fields."""
        db = HabitsDB(habits_collection)
        habit_id = await db.create_habit(
            user_id=sample_user_id,
            name="Reading",
            notification_time="20:00",
            timezone="America/New_York"
        )

        habit = await habits_collection.find_one({"_id": habit_id})

        assert habit["user_id"] == sample_user_id
        assert habit["name"] == "Reading"
        assert habit["notification_time"] == "20:00"
        assert habit["timezone"] == "America/New_York"
        assert habit["is_active"] is True
        assert isinstance(habit["created_at"], datetime)

    async def test_get_habit_returns_habit_by_id(self, habits_collection, sample_user_id):
        """get_habit should return the habit document by ID."""
        db = HabitsDB(habits_collection)
        habit_id = await db.create_habit(
            user_id=sample_user_id,
            name="Meditation",
            notification_time="07:00",
            timezone="UTC"
        )

        habit = await db.get_habit(habit_id)

        assert habit is not None
        assert habit["_id"] == habit_id
        assert habit["name"] == "Meditation"

    async def test_get_habit_returns_none_for_nonexistent(self, habits_collection):
        """get_habit should return None for non-existent habit ID."""
        db = HabitsDB(habits_collection)
        habit = await db.get_habit(ObjectId())

        assert habit is None

    async def test_get_user_habits_returns_all_user_habits(self, habits_collection, sample_user_id):
        """get_user_habits should return all habits for a user."""
        db = HabitsDB(habits_collection)
        await db.create_habit(sample_user_id, "Exercise", "09:00", "UTC")
        await db.create_habit(sample_user_id, "Reading", "20:00", "UTC")
        await db.create_habit(sample_user_id, "Meditation", "07:00", "UTC")

        habits = await db.get_user_habits(sample_user_id)

        assert len(habits) == 3
        names = [h["name"] for h in habits]
        assert "Exercise" in names
        assert "Reading" in names
        assert "Meditation" in names

    async def test_get_user_habits_returns_only_active_by_default(self, habits_collection, sample_user_id):
        """get_user_habits should return only active habits by default."""
        db = HabitsDB(habits_collection)
        await db.create_habit(sample_user_id, "Active Habit", "09:00", "UTC")
        habit_id = await db.create_habit(sample_user_id, "Inactive Habit", "10:00", "UTC")
        await db.deactivate_habit(habit_id)

        habits = await db.get_user_habits(sample_user_id)

        assert len(habits) == 1
        assert habits[0]["name"] == "Active Habit"

    async def test_get_user_habits_can_include_inactive(self, habits_collection, sample_user_id):
        """get_user_habits with include_inactive=True should return all habits."""
        db = HabitsDB(habits_collection)
        await db.create_habit(sample_user_id, "Active Habit", "09:00", "UTC")
        habit_id = await db.create_habit(sample_user_id, "Inactive Habit", "10:00", "UTC")
        await db.deactivate_habit(habit_id)

        habits = await db.get_user_habits(sample_user_id, include_inactive=True)

        assert len(habits) == 2

    async def test_get_user_habits_empty_for_nonexistent_user(self, habits_collection):
        """get_user_habits should return empty list for user with no habits."""
        db = HabitsDB(habits_collection)
        habits = await db.get_user_habits(999999999)

        assert habits == []

    async def test_update_habit_updates_fields(self, habits_collection, sample_user_id):
        """update_habit should update the specified fields."""
        db = HabitsDB(habits_collection)
        habit_id = await db.create_habit(sample_user_id, "Exercise", "09:00", "UTC")

        await db.update_habit(habit_id, name="Morning Jog", notification_time="06:30")

        habit = await db.get_habit(habit_id)
        assert habit["name"] == "Morning Jog"
        assert habit["notification_time"] == "06:30"

    async def test_update_habit_preserves_unchanged_fields(self, habits_collection, sample_user_id):
        """update_habit should not modify fields not specified in update."""
        db = HabitsDB(habits_collection)
        habit_id = await db.create_habit(sample_user_id, "Exercise", "09:00", "America/New_York")

        await db.update_habit(habit_id, name="Morning Jog")

        habit = await db.get_habit(habit_id)
        assert habit["notification_time"] == "09:00"
        assert habit["timezone"] == "America/New_York"

    async def test_deactivate_habit_sets_is_active_false(self, habits_collection, sample_user_id):
        """deactivate_habit should set is_active to False."""
        db = HabitsDB(habits_collection)
        habit_id = await db.create_habit(sample_user_id, "Exercise", "09:00", "UTC")

        result = await db.deactivate_habit(habit_id)

        habit = await db.get_habit(habit_id)
        assert habit["is_active"] is False
        assert result is True

    async def test_deactivate_habit_returns_false_for_nonexistent(self, habits_collection):
        """deactivate_habit should return False for non-existent habit."""
        db = HabitsDB(habits_collection)
        result = await db.deactivate_habit(ObjectId())

        assert result is False

    async def test_delete_habit_removes_document(self, habits_collection, sample_user_id):
        """delete_habit should remove the habit document."""
        db = HabitsDB(habits_collection)
        habit_id = await db.create_habit(sample_user_id, "Exercise", "09:00", "UTC")

        result = await db.delete_habit(habit_id)

        assert result is True
        habit = await db.get_habit(habit_id)
        assert habit is None

    async def test_delete_habit_returns_false_for_nonexistent(self, habits_collection):
        """delete_habit should return False for non-existent habit."""
        db = HabitsDB(habits_collection)
        result = await db.delete_habit(ObjectId())

        assert result is False

    async def test_get_habits_by_notification_time(self, habits_collection, sample_user_id):
        """get_habits_by_notification_time should return habits scheduled at given time."""
        db = HabitsDB(habits_collection)
        await db.create_habit(sample_user_id, "Morning", "09:00", "UTC")
        await db.create_habit(sample_user_id, "Also Morning", "09:00", "UTC")
        await db.create_habit(sample_user_id, "Evening", "18:00", "UTC")

        habits = await db.get_habits_by_notification_time("09:00")

        assert len(habits) == 2
        for h in habits:
            assert h["notification_time"] == "09:00"
