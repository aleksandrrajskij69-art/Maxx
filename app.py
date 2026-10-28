import asyncio
import os
import tempfile
from pathlib import Path

from dotenv import load_dotenv
from aiomax2 import Bot, Dispatcher, Router
from aiomax2.filters import Command
from aiomax2.types import Message  # Убран FSInputFile
from pollinations import Pollinations

load_dotenv()
MAX_BOT_TOKEN = os.getenv("MAX_BOT_TOKEN")
POLLINATIONS_API_KEY = os.getenv("POLLINATIONS_API_KEY")

if not MAX_BOT_TOKEN or not POLLINATIONS_API_KEY:
    raise RuntimeError("Проверьте переменные окружения MAX_BOT_TOKEN и POLLINATIONS_API_KEY")

GREETING = "Здравствуйте, я бот для генерации фото, напишите свой запрос и я создам фото"

# Создаем бота с отключенной проверкой SSL (для работы на сервере)
bot = Bot(MAX_BOT_TOKEN, verify_ssl=False)
pollinations = Pollinations(api_key=POLLINATIONS_API_KEY)
router = Router()
greeted_chats = set()

@router.message(Command("start"))
async def cmd_start(message: Message):
    chat_id = message.recipient.chat_id
    greeted_chats.add(chat_id)
    await message.answer(GREETING)

@router.message()
async def handle_message(message: Message):
    if not message.text:
        return

    text = message.text.strip()
    chat_id = message.recipient.chat_id

    if chat_id not in greeted_chats:
        greeted_chats.add(chat_id)
        await message.answer(GREETING)

    prompt = text
    await message.answer("Генерирую изображение... Пожалуйста, подождите.")

    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp_file:
            tmp_path = tmp_file.name

        # Скачиваем картинку
        await asyncio.to_thread(
            pollinations.download_image,
            prompt=prompt,
            output_path=tmp_path,  # Используем output_path
            model="flux",
            width=1024,
            height=1024
        )

        # Загружаем изображение на сервер MAX и получаем объект вложения
        attachment = await bot.upload_image(tmp_path)

        # Отправляем сообщение с прикрепленным фото
        await message.answer(
            text=f"Ваше изображение по запросу: «{prompt}»",
            attachments=[attachment]
        )

    except Exception as e:
        await message.answer(f"Ошибка при создании или отправке изображения: {e}")
    finally:
        # Удаляем временный файл
        if tmp_path and Path(tmp_path).exists():
            Path(tmp_path).unlink(missing_ok=True)

async def main():
    print("Бот запущен и ожидает сообщения...")
    dp = Dispatcher()
    dp.include_router(router)

    # Удаляем старые вебхуки, чтобы polling работал корректно
    try:
        subscriptions = await bot.get_subscriptions()
        for sub in subscriptions:
            await bot.unsubscribe(sub.url)
            print(f"Удалена подписка: {sub.url}")
    except Exception as e:
        print(f"Не удалось удалить подписки: {e}")

    try:
        await dp.start_polling(bot)
    except Exception as e:
        print(f"Критическая ошибка при работе бота: {e}")
    finally:
        await bot.close()
        await dp.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Бот остановлен пользователем.")