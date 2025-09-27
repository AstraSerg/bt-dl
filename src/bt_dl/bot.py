# src/bt_dl/bot.py
import os
import asyncio
from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram.types import Message
from dotenv import load_dotenv
from urllib.parse import quote


load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
SEARCH_URL_TEMPLATE = os.getenv(
    "SEARCH_URL",
    "https://rutracker.org/forum/tracker.php?nm={}"
)

if not BOT_TOKEN:
    raise RuntimeError(
        "❌ Переменная BOT_TOKEN не задана.\n"
        "Создайте файл .env на основе .env.example и вставьте токен от @BotFather."
    )

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

@dp.message(Command("start"))
async def send_welcome(message: Message):
    await message.answer(
        "🔍 Привет! Я бот для поиска торрентов.\n"
        "Напиши название фильма, сериала или софта — и я найду его на трекере!\n\n"
        "Пример: `интерстеллар 2014`"
    )

@dp.message()
async def handle_search(message: Message):
    query = message.text.strip()
    if not query:
        await message.answer("Пожалуйста, введи поисковый запрос.")
        return

    # Кодируем запрос для URL
    safe_query = quote(query)
    search_url = SEARCH_URL_TEMPLATE.format(safe_query)

    await message.answer(
        f"Ищу «{query}»...\n\n🔗 [Результаты поиска]({search_url})",
        parse_mode="MarkdownV2",
        disable_web_page_preview=True
    )

async def main():
    print("✅ bt-dl-bot запущен. Ожидание сообщений...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

