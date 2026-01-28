"""
Test fixtures for the Telegram Habit Tracking Bot.
"""

import pytest
from datetime import datetime, date
from unittest.mock import AsyncMock, MagicMock, patch
from bson import ObjectId

import mongomock_motor


@pytest.fixture
def mongo_client():
    """Create a mock MongoDB client using mongomock-motor."""
    return mongomock_motor.AsyncMongoMockClient()


@pytest.fixture
def mongo_database(mongo_client):
    """Get the test database from the mock client."""
    return mongo_client.TelegramBot


@pytest.fixture
def habits_collection(mongo_database):
    """Get the habits collection from the test database."""
    return mongo_database.habits


@pytest.fixture
def submissions_collection(mongo_database):
    """Get the submissions collection from the test database."""
    return mongo_database.submissions


@pytest.fixture
def streaks_collection(mongo_database):
    """Get the streaks collection from the test database."""
    return mongo_database.streaks


@pytest.fixture
def sample_user_id():
    """Sample user ID for tests."""
    return 123456789


@pytest.fixture
def sample_admin_id():
    """Sample admin user ID for tests."""
    return 987654321


@pytest.fixture
def sample_habit_id():
    """Sample habit ObjectId for tests."""
    return ObjectId()


@pytest.fixture
def sample_habit_data(sample_user_id):
    """Sample habit document data."""
    return {
        "user_id": sample_user_id,
        "name": "Morning Exercise",
        "is_active": True,
        "notification_time": "09:00",
        "timezone": "UTC",
        "created_at": datetime.utcnow(),
    }


@pytest.fixture
def sample_submission_data(sample_habit_id, sample_user_id):
    """Sample submission document data."""
    return {
        "habit_id": sample_habit_id,
        "user_id": sample_user_id,
        "photo_file_id": "AgACAgIAAxkBAAI",
        "submitted_at": datetime.utcnow(),
        "status": "pending",
        "reviewed_by": None,
        "reviewed_at": None,
        "rejection_reason": None,
    }


@pytest.fixture
def sample_streak_data(sample_user_id, sample_habit_id):
    """Sample streak document data."""
    return {
        "user_id": sample_user_id,
        "habit_id": sample_habit_id,
        "current_streak": 5,
        "longest_streak": 10,
        "last_approved_date": date.today(),
        "total_approved": 25,
    }


@pytest.fixture
def mock_pyrogram_client():
    """Create a mock Pyrogram Client."""
    client = MagicMock()
    client.send_message = AsyncMock()
    client.send_photo = AsyncMock()
    client.get_users = AsyncMock()
    return client


@pytest.fixture
def mock_message(sample_user_id):
    """Create a mock Pyrogram Message."""
    message = MagicMock()
    message.from_user = MagicMock()
    message.from_user.id = sample_user_id
    message.from_user.first_name = "Test"
    message.from_user.last_name = "User"
    message.chat = MagicMock()
    message.chat.id = sample_user_id
    message.reply_text = AsyncMock()
    message.reply_photo = AsyncMock()
    message.command = []
    message.text = ""
    message.photo = None
    return message


@pytest.fixture
def mock_callback_query(sample_user_id):
    """Create a mock Pyrogram CallbackQuery."""
    callback = MagicMock()
    callback.from_user = MagicMock()
    callback.from_user.id = sample_user_id
    callback.message = MagicMock()
    callback.message.chat = MagicMock()
    callback.message.chat.id = sample_user_id
    callback.data = ""
    callback.answer = AsyncMock()
    callback.edit_message_text = AsyncMock()
    return callback


def create_message(user_id: int, text: str = "", command: list = None, photo=None):
    """Factory function to create mock messages with specific attributes."""
    message = MagicMock()
    message.from_user = MagicMock()
    message.from_user.id = user_id
    message.from_user.first_name = "Test"
    message.chat = MagicMock()
    message.chat.id = user_id
    message.reply_text = AsyncMock()
    message.reply_photo = AsyncMock()
    message.command = command or []
    message.text = text
    message.photo = photo
    return message


def create_photo():
    """Factory function to create a mock Photo object."""
    photo = MagicMock()
    photo.file_id = "AgACAgIAAxkBAAI_test_file_id"
    photo.file_unique_id = "AQADAgAT_unique"
    return photo
