import os
import logging
import asyncio
from fastapi import FastAPI, Query, Request
from fastapi.responses import HTMLResponse
import uvicorn
from aiogram import Bot, Dispatcher
from aiogram.types import Message, WebAppInfo, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import CommandStart

# Прямой импорт ваших реальных функций из database.py
from database import get_districts, get_market_statistics

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Получение токена и URL из переменных окружения
BOT_TOKEN = os.getenv("BOT_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN") or os.getenv("TOKEN")
WEBAPP_URL = os.getenv("WEBAPP_URL", "https://your-app.fadehost.app")

if not BOT_TOKEN:
    logger.error("❌ Не найден токен бота в переменных окружения!")

bot = Bot(token=BOT_TOKEN) if BOT_TOKEN else None
dp = Dispatcher()

# Инициализация FastAPI для мини-приложения
app = FastAPI()

@app.get("/api/districts")
def api_get_districts():
    """Эндпоинт для получения списка уникальных районов из базы"""
    try:
        return get_districts()
    except Exception as e:
        logger.error(f"Ошибка в /api/districts: {e}")
        return []

@app.get("/api/stats")
def api_get_stats(
    category: str = Query(None),
    prop_type: str = Query(None),
    rooms: str = Query(None),
    district: str = Query(None)
):
    """Эндпоинт для получения статистики рынка по фильтрам"""
    try:
        return get_market_statistics(
            category=category,
            prop_type=prop_type,
            rooms=rooms,
            district=district
        )
    except Exception as e:
        logger.error(f"Ошибка в /api/stats: {e}")
        return {}

@app.get("/", response_class=HTMLResponse)
def serve_webapp(request: Request):
    """Отдача фронтенда веб-приложения (index.html)"""
    index_path = os.path.join("webapp", "index.html")
    if os.path.exists(index_path):
        with open(index_path, "r", encoding="utf-8") as f:
            return f.read()
    return "<h3>Файл webapp/index.html не найден! Убедитесь, что папка webapp находится в корне проекта.</h3>"


# --- Хендлеры Telegram-бота ---

@dp.message(CommandStart())
async def cmd_start(message: Message):
    """Приветствие пользователя и кнопка запуска Mini App"""
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🏢 Открыть рынок недвижимости",
                    web_app=WebAppInfo(url=WEBAPP_URL)
                )
            ]
        ]
    )
    
    await message.answer(
        "👋 Добро пожаловать!\n\n"
        "Нажмите на кнопку ниже, чтобы открыть интерактивную панель управления и статистику:",
        reply_markup=keyboard
    )


# --- Одновременный запуск FastAPI и Telegram-бота ---

async def run_fastapi():
    config = uvicorn.Config(app, host="0.0.0.0", port=8000, log_level="info")
    server = uvicorn.Server(config)
    await server.serve()

async def main():
    if not bot:
        logger.error("❌ Запуск отменен: отсутствует токен бота.")
        return
        
    logger.info("🚀 Запуск веб-сервера и Telegram-бота...")
    fastapi_task = asyncio.create_task(run_fastapi())
    
    # Запуск поллинга бота
    await dp.start_polling(bot)
    await fastapi_task

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Приложение остановлено.")