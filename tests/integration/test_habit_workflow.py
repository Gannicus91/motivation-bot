"""
Integration tests for the complete habit tracking workflow.
Tests the full flow from habit creation through submission and review.
"""

import pytest
from datetime import datetime, date, timedelta
from bson import ObjectId
from freezegun import freeze_time
from unittest.mock import AsyncMock, MagicMock, patch

from TelegramBot.database.habits import HabitsDB
from TelegramBot.database.submissions import SubmissionsDB
from TelegramBot.database.streaks import StreaksDB
from TelegramBot.services.streak_service import StreakService
from TelegramBot.services.submission_service import SubmissionService
from TelegramBot.services.notification_service import NotificationService


class TestHabitWorkflow:
    """Integration tests for the complete habit workflow."""

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
    def notification_service(
        self, habits_db, submissions_db, streaks_db, mock_client
    ):
        return NotificationService(
            habits_db=habits_db,
            submissions_db=submissions_db,
            streaks_db=streaks_db,
            client=mock_client
        )

    # Test 1: Full workflow: add_habit -> submit_proof -> approve -> streak_updated
    async def test_full_workflow_add_submit_approve(
        self, habits_db, submissions_db, streaks_db,
        submission_service, sample_user_id, sample_admin_id
    ):
        """
        Complete workflow test:
        1. User creates a habit
        2. User submits proof photo
        3. Admin approves submission
        4. User's streak is updated
        """
        with freeze_time("2024-01-15 10:00:00"):
            # Step 1: Create habit
            habit_id = await habits_db.create_habit(
                user_id=sample_user_id,
                name="Morning Exercise",
                notification_time="09:00",
                timezone="UTC"
            )
            
            # Verify habit created
            habit = await habits_db.get_habit(habit_id)
            assert habit is not None
            assert habit["name"] == "Morning Exercise"
            assert habit["is_active"] is True

            # Step 2: Submit proof
            submission_id = await submission_service.submit(
                user_id=sample_user_id,
                habit_id=habit_id,
                photo_file_id="AgACAgIAAxkBAAI_workout_photo"
            )
            
            # Verify submission created
            submission = await submissions_db.get_submission(submission_id)
            assert submission is not None
            assert submission["status"] == "pending"

            # Step 3: Admin approves
            success = await submission_service.approve(
                submission_id=submission_id,
                reviewer_id=sample_admin_id
            )
            assert success is True

            # Step 4: Verify streak updated
            streak = await streaks_db.get_streak(sample_user_id, habit_id)
            assert streak is not None
            assert streak["current_streak"] == 1
            assert streak["total_approved"] == 1
            assert streak["longest_streak"] == 1

    # Test 2: Multi-day streak maintenance
    async def test_multi_day_streak_maintenance(
        self, habits_db, submissions_db, streaks_db,
        submission_service, streak_service, sample_user_id, sample_admin_id
    ):
        """
        Test streak maintenance over multiple consecutive days.
        """
        # Day 1: Create habit and first submission
        with freeze_time("2024-01-15 10:00:00"):
            habit_id = await habits_db.create_habit(
                user_id=sample_user_id,
                name="Reading",
                notification_time="20:00",
                timezone="UTC"
            )
            
            sub_id_1 = await submission_service.submit(
                user_id=sample_user_id,
                habit_id=habit_id,
                photo_file_id="photo_day1"
            )
            await submission_service.approve(sub_id_1, sample_admin_id)
            
            streak = await streaks_db.get_streak(sample_user_id, habit_id)
            assert streak["current_streak"] == 1

        # Day 2: Second consecutive day
        with freeze_time("2024-01-16 10:00:00"):
            sub_id_2 = await submission_service.submit(
                user_id=sample_user_id,
                habit_id=habit_id,
                photo_file_id="photo_day2"
            )
            await submission_service.approve(sub_id_2, sample_admin_id)
            
            streak = await streaks_db.get_streak(sample_user_id, habit_id)
            assert streak["current_streak"] == 2
            assert streak["longest_streak"] == 2

        # Day 3: Third consecutive day
        with freeze_time("2024-01-17 10:00:00"):
            sub_id_3 = await submission_service.submit(
                user_id=sample_user_id,
                habit_id=habit_id,
                photo_file_id="photo_day3"
            )
            await submission_service.approve(sub_id_3, sample_admin_id)
            
            streak = await streaks_db.get_streak(sample_user_id, habit_id)
            assert streak["current_streak"] == 3
            assert streak["longest_streak"] == 3
            assert streak["total_approved"] == 3

    # Test 3: Streak breaks on missed day
    async def test_streak_breaks_on_missed_day(
        self, habits_db, submissions_db, streaks_db,
        submission_service, streak_service, sample_user_id, sample_admin_id
    ):
        """
        Test that streak resets when user misses a day.
        """
        # Day 1 and 2: Build a streak
        with freeze_time("2024-01-15 10:00:00"):
            habit_id = await habits_db.create_habit(
                user_id=sample_user_id,
                name="Meditation",
                notification_time="07:00",
                timezone="UTC"
            )
            
            sub_id_1 = await submission_service.submit(
                user_id=sample_user_id,
                habit_id=habit_id,
                photo_file_id="photo_day1"
            )
            await submission_service.approve(sub_id_1, sample_admin_id)

        with freeze_time("2024-01-16 10:00:00"):
            sub_id_2 = await submission_service.submit(
                user_id=sample_user_id,
                habit_id=habit_id,
                photo_file_id="photo_day2"
            )
            await submission_service.approve(sub_id_2, sample_admin_id)
            
            streak = await streaks_db.get_streak(sample_user_id, habit_id)
            assert streak["current_streak"] == 2
            assert streak["longest_streak"] == 2

        # Skip Day 3 (January 17)

        # Day 4: Submit after missing a day
        with freeze_time("2024-01-18 10:00:00"):
            # Check if missed and reset
            await streak_service.check_and_reset_if_missed(sample_user_id, habit_id)
            
            streak = await streaks_db.get_streak(sample_user_id, habit_id)
            # Streak should be reset to 0 due to missed day
            assert streak["current_streak"] == 0
            # But longest streak should be preserved
            assert streak["longest_streak"] == 2

            # Now submit again
            sub_id_4 = await submission_service.submit(
                user_id=sample_user_id,
                habit_id=habit_id,
                photo_file_id="photo_day4"
            )
            await submission_service.approve(sub_id_4, sample_admin_id)
            
            streak = await streaks_db.get_streak(sample_user_id, habit_id)
            # New streak starts at 1
            assert streak["current_streak"] == 1
            # Longest still preserved
            assert streak["longest_streak"] == 2

    # Test 4: Rejection flow with user notification
    async def test_rejection_flow_with_notification(
        self, habits_db, submissions_db, streaks_db,
        submission_service, mock_client, sample_user_id, sample_admin_id
    ):
        """
        Test the complete rejection flow:
        1. User submits proof
        2. Admin rejects with reason
        3. User is notified
        4. Streak is NOT updated
        """
        with freeze_time("2024-01-15 10:00:00"):
            habit_id = await habits_db.create_habit(
                user_id=sample_user_id,
                name="Exercise",
                notification_time="09:00",
                timezone="UTC"
            )
            
            submission_id = await submission_service.submit(
                user_id=sample_user_id,
                habit_id=habit_id,
                photo_file_id="unclear_photo"
            )
            
            # Admin rejects with reason
            success = await submission_service.reject(
                submission_id=submission_id,
                reviewer_id=sample_admin_id,
                reason="Photo is unclear, please resubmit"
            )
            assert success is True

            # Verify submission is rejected
            submission = await submissions_db.get_submission(submission_id)
            assert submission["status"] == "rejected"
            assert submission["rejection_reason"] == "Photo is unclear, please resubmit"

            # Verify user was notified
            mock_client.send_message.assert_called()

            # Verify streak was NOT updated
            streak = await streaks_db.get_streak(sample_user_id, habit_id)
            assert streak is None or streak["current_streak"] == 0

    # Test 5: Daily notification delivery
    async def test_daily_notification_delivery(
        self, habits_db, submissions_db, notification_service,
        mock_client, sample_user_id
    ):
        """
        Test that daily notifications are sent correctly:
        1. Create habits with notification times
        2. Check which users are due
        3. Send reminders
        """
        # Create habits for different notification times
        with freeze_time("2024-01-15 08:00:00"):
            await habits_db.create_habit(
                user_id=sample_user_id,
                name="Morning Run",
                notification_time="09:00",
                timezone="UTC"
            )
            
            await habits_db.create_habit(
                user_id=sample_user_id,
                name="Evening Read",
                notification_time="20:00",
                timezone="UTC"
            )

        # Check at 09:00 - should find Morning Run habit
        with freeze_time("2024-01-15 09:00:00"):
            users_due = await notification_service.get_users_due("09:00")
            
            assert len(users_due) >= 1
            # Should contain our user's morning habit
            user_ids = [u["user_id"] for u in users_due]
            assert sample_user_id in user_ids

        # Check at 20:00 - should find Evening Read habit
        with freeze_time("2024-01-15 20:00:00"):
            users_due = await notification_service.get_users_due("20:00")
            
            assert len(users_due) >= 1
            user_ids = [u["user_id"] for u in users_due]
            assert sample_user_id in user_ids

    # Test 6: No notification if already submitted today
    async def test_no_notification_if_already_submitted(
        self, habits_db, submissions_db, notification_service,
        submission_service, sample_user_id, sample_admin_id
    ):
        """
        Users who have already submitted today should not receive notifications.
        """
        with freeze_time("2024-01-15 08:00:00"):
            habit_id = await habits_db.create_habit(
                user_id=sample_user_id,
                name="Morning Exercise",
                notification_time="09:00",
                timezone="UTC"
            )
            
            # Submit proof before notification time
            await submission_service.submit(
                user_id=sample_user_id,
                habit_id=habit_id,
                photo_file_id="early_photo"
            )

        # Check at notification time
        with freeze_time("2024-01-15 09:00:00"):
            users_due = await notification_service.get_users_due("09:00")
            
            # User should NOT be in the list since they already submitted
            matching_users = [
                u for u in users_due 
                if u["user_id"] == sample_user_id and u["habit_id"] == habit_id
            ]
            assert len(matching_users) == 0

    # Test 7: Multiple habits workflow
    async def test_multiple_habits_workflow(
        self, habits_db, submissions_db, streaks_db,
        submission_service, sample_user_id, sample_admin_id
    ):
        """
        Test workflow with multiple habits.
        Each habit should have independent streaks.
        """
        with freeze_time("2024-01-15 10:00:00"):
            habit_1 = await habits_db.create_habit(
                user_id=sample_user_id,
                name="Exercise",
                notification_time="09:00",
                timezone="UTC"
            )
            
            habit_2 = await habits_db.create_habit(
                user_id=sample_user_id,
                name="Reading",
                notification_time="20:00",
                timezone="UTC"
            )
            
            # Submit for habit 1 only
            sub_1 = await submission_service.submit(
                user_id=sample_user_id,
                habit_id=habit_1,
                photo_file_id="exercise_photo"
            )
            await submission_service.approve(sub_1, sample_admin_id)
            
            # Verify habit 1 has streak
            streak_1 = await streaks_db.get_streak(sample_user_id, habit_1)
            assert streak_1["current_streak"] == 1
            
            # Verify habit 2 has no streak
            streak_2 = await streaks_db.get_streak(sample_user_id, habit_2)
            assert streak_2 is None or streak_2["current_streak"] == 0

    # Test 8: Pending submission does not count for streak
    async def test_pending_submission_does_not_count(
        self, habits_db, submissions_db, streaks_db,
        submission_service, sample_user_id
    ):
        """
        Pending submissions should not count towards streak.
        Only approved submissions update the streak.
        """
        with freeze_time("2024-01-15 10:00:00"):
            habit_id = await habits_db.create_habit(
                user_id=sample_user_id,
                name="Exercise",
                notification_time="09:00",
                timezone="UTC"
            )
            
            # Submit but don't approve
            await submission_service.submit(
                user_id=sample_user_id,
                habit_id=habit_id,
                photo_file_id="pending_photo"
            )
            
            # Streak should not exist or be 0
            streak = await streaks_db.get_streak(sample_user_id, habit_id)
            assert streak is None or streak["current_streak"] == 0

    # Test 9: Deactivated habit stops receiving notifications
    async def test_deactivated_habit_no_notifications(
        self, habits_db, submissions_db, notification_service,
        sample_user_id
    ):
        """
        Deactivated habits should not trigger notifications.
        """
        with freeze_time("2024-01-15 08:00:00"):
            habit_id = await habits_db.create_habit(
                user_id=sample_user_id,
                name="Old Habit",
                notification_time="09:00",
                timezone="UTC"
            )
            
            # Deactivate the habit
            await habits_db.deactivate_habit(habit_id)

        # Check at notification time
        with freeze_time("2024-01-15 09:00:00"):
            users_due = await notification_service.get_users_due("09:00")
            
            # Should not include deactivated habit
            matching_users = [
                u for u in users_due 
                if u["user_id"] == sample_user_id
            ]
            assert len(matching_users) == 0

    # Test 10: Full notification send cycle
    async def test_full_notification_send_cycle(
        self, habits_db, submissions_db, notification_service,
        mock_client, sample_user_id
    ):
        """
        Test complete notification sending cycle.
        """
        with freeze_time("2024-01-15 08:00:00"):
            await habits_db.create_habit(
                user_id=sample_user_id,
                name="Morning Run",
                notification_time="09:00",
                timezone="UTC"
            )

        with freeze_time("2024-01-15 09:00:00"):
            # Send all reminders for 09:00
            count = await notification_service.send_all_reminders("09:00")
            
            # Should have sent at least one reminder
            assert count >= 1
            
            # Verify message was sent
            mock_client.send_message.assert_called()
