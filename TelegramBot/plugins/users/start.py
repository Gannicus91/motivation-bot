from pyrogram import Client, filters
from pyrogram.types import Message


@Client.on_message(filters.command(["start"]))
async def start_command(client: Client, message: Message):
    await message.reply_text("Bot is being developed...")
