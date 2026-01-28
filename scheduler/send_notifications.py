#!/usr/bin/env python3
"""Standalone script to send notifications for the current time."""
import asyncio
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorClient
from pyrogram import Client

from TelegramBot import config
from TelegramBot.database.habits import HabitsDB
from TelegramBot.database.submissions import SubmissionsDB
from TelegramBot.database.streaks import StreaksDB
from TelegramBot.services.notification_service import NotificationService


async def main():
    current_time = datetime.now().strftime("%H:%M")

    # Connect to MongoDB
    mongo = AsyncIOMotorClient(config.MONGO_URI)
    database = mongo.TelegramBot

    # Initialize database wrappers
    habits_db = HabitsDB(database.habits)
    submissions_db = SubmissionsDB(database.submissions)
    streaks_db = StreaksDB(database.streaks)

    # Create Pyrogram client
    async with Client(
        "scheduler",
        api_id=config.API_ID,
        api_hash=config.API_HASH,
        bot_token=config.BOT_TOKEN,
        in_memory=True,
    ) as client:
        service = NotificationService(
            habits_db=habits_db,
            submissions_db=submissions_db,
            streaks_db=streaks_db,
            client=client
        )
        count = await service.send_all_reminders(current_time)
        print(f"[{current_time}] Sent {count} notifications")


if __name__ == "__main__":
    asyncio.run(main())
