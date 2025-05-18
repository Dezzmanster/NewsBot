import os
import json
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import (
    Message,
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery
)
from dotenv import load_dotenv
import asyncio
import logging

from agents.agent_graph import process_news_channels
from utils.helpers import (
    format_report_for_telegram
)
from config.settings import TELEGRAM

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = Bot(token=TELEGRAM['BOT_TOKEN'])
dp = Dispatcher()

user_channels = dict()

main_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📰 Получить сводку последних новостей")],
        [KeyboardButton(text="ℹ️ Помощь"), KeyboardButton(text="📋 Список каналов")],
        [KeyboardButton(text="➕ Добавить канал"), KeyboardButton(text="❌ Удалить канал")],
    ],
    resize_keyboard=True
)

# Вспомогательные функции
# TODO: перенести их в helpers и сделать нормальную логику обработки
def save_user_channels():
    try:
        os.makedirs("data", exist_ok=True)
        with open("data/user_channels.json", "w", encoding="utf-8") as f:
            json.dump(user_channels, f)
    except Exception as e:
        logger.error(f"Ошибка при сохранении списка каналов: {e}")

def load_user_channels():
    global user_channels
    try:
        if os.path.exists("data/user_channels.json"):
            with open("data/user_channels.json", "r", encoding="utf-8") as f:
                user_channels = json.load(f)
    except Exception as e:
        logger.error(f"Ошибка при загрузке списка каналов: {e}")


@dp.message(Command("start"))
async def cmd_start(message: Message):
    load_user_channels()
    await message.answer(
        "👋 Привет! Я бот для агрегации новостей из Telegram-каналов.\n"
        "Пользуйся кнопками для управления.",
        reply_markup=main_kb
    )

@dp.message(lambda m: m.text == "ℹ️ Помощь")
async def help_handler(message: Message):
    await message.answer(
        "🤖 *Возможности бота:*\n\n"
        "📋 Список каналов - посмотреть каналы по котором собираются новости\n"
        "➕ Добавить канал - добавить канал для сбора новостей\n"
        "❌ Удалить канал - удалить канал из списка\n"
        "📰 Получить сводку последних новостей - собрать и проанализировать новости\n"
        "ℹ️ Помощь - это сообщение",
        parse_mode="Markdown"
    )

@dp.message(lambda m: m.text == "➕ Добавить канал")
async def add_channel_prompt(message: Message):
    await message.answer(
        "Введите ссылку или username канала (например, @channel или https://t.me/channel):",
        reply_markup=types.ForceReply()
    )

@dp.message(lambda m: m.reply_to_message and "Введите ссылку" in m.reply_to_message.text)
async def add_channel_handler(message: Message):
    channel = message.text.strip()
    if channel.startswith("https://t.me/"):
        channel = "@" + channel.split("/")[-1]
    elif not channel.startswith("@"):
        channel = "@" + channel

    user_id = str(message.from_user.id)
    if user_id not in user_channels:
        user_channels[user_id] = []
    if channel in user_channels[user_id]:
        await message.answer(f"❌ Канал {channel} уже добавлен.", reply_markup=main_kb)
        return

    user_channels[user_id].append(channel)
    save_user_channels()
    await message.answer(f"✅ Канал {channel} добавлен в список.", reply_markup=main_kb)

@dp.message(lambda m: m.text == "📋 Список каналов")
async def list_channels(message: Message):
    user_id = str(message.from_user.id)
    channels = user_channels.get(user_id, [])
    if not channels:
        await message.answer("У вас нет добавленных каналов.", reply_markup=main_kb)
        return
    txt = "\n".join([f"{i+1}. {c}" for i, c in enumerate(channels)])
    await message.answer(f"Ваши каналы:\n{txt}", reply_markup=main_kb)

@dp.message(lambda m: m.text == "❌ Удалить канал")
async def remove_channel_prompt(message: Message):
    user_id = str(message.from_user.id)
    channels = user_channels.get(user_id, [])
    if not channels:
        await message.answer("У вас нет добавленных каналов.", reply_markup=main_kb)
        return
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=f"Удалить {c}", callback_data=f"remove_{i}")]
            for i, c in enumerate(channels)
        ]
    )
    await message.answer("Выберите канал для удаления:", reply_markup=kb)

@dp.callback_query(lambda c: c.data.startswith("remove_"))
async def remove_channel_handler(callback: CallbackQuery):
    user_id = str(callback.from_user.id)
    index = int(callback.data.split("_")[1])
    channels = user_channels.get(user_id, [])
    if 0 <= index < len(channels):
        removed = channels.pop(index)
        user_channels[user_id] = channels
        save_user_channels()
        await callback.message.edit_text(f"Канал {removed} удалён.")
        await callback.message.answer("Выберите действие:", reply_markup=main_kb)
    else:
        await callback.answer("Ошибка!", show_alert=True)

@dp.message(lambda m: m.text == "📰 Получить сводку последних новостей")
async def get_news(message: Message):
    user_id = str(message.from_user.id)
    channels = user_channels.get(user_id, [])
    if not channels:
        await message.answer("У вас нет добавленных каналов.", reply_markup=main_kb)
        return

    processing_msg = await message.answer("⏳ Обработка каналов, пожалуйста, подождите...")

    try:
        report = await process_news_channels(channels)
        formatted = format_report_for_telegram(report)
        await bot.send_message(message.chat.id, formatted, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Ошибка при получении новостей: {e}")
        await message.answer("Произошла ошибка при получении новостей.", reply_markup=main_kb)
    finally:
        await processing_msg.delete()

async def main():
    load_user_channels()
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
