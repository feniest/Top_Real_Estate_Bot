import os
import logging
import asyncio
from fastapi import FastAPI, Query, Request
from fastapi.responses import HTMLResponse
import uvicorn
from aiogram import Bot, Dispatcher
from aiogram.types import Message, WebAppInfo, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import CommandStart

# --- Безопасный импорт и адаптация database.py ---
try:
    import database
    # Проверяем, есть ли класс Database или отдельные функции
    if hasattr(database, "Database"):
        # Если в database.py используется класс
        # Подберите параметры подключения под ваши реальные переменные окружения
        db_config = {
            "dbname": os.getenv("DB_NAME", "postgres"),
            "user": os.getenv("DB_USER", "postgres"),
            "password": os.getenv("DB_PASSWORD", ""),
            "host": os.getenv("DB_HOST", "localhost"),
            "port": os.getenv("DB_PORT", "5432")
        }
        db_instance = database.Database(db_config) if callable(database.Database) else database.Database
        
        def get_districts():
            if hasattr(db_instance, "get_districts"):
                return db_instance.get_districts()
            return []
            
        def get_market_statistics(category=None, prop_type=None, rooms=None, district=None):
            if hasattr(db_instance, "get_market_statistics"):
                return db_instance.get_market_statistics(category=category, prop_type=prop_type, rooms=rooms, district=district)
            return {}
    else:
        # Если функции объявлены напрямую в модуле
        from database import get_districts, get_market_statistics
except Exception as e:
    logging.error(f"⚠️ Ошибка инициализации базы данных: {e}")
    def get_districts():
        return []
    def get_market_statistics(category=None, prop_type=None, rooms=None, district=None):
        return {}

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Получение токена и URL из переменных окружения
BOT_TOKEN = os.getenv("BOT_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN") or os.getenv("TOKEN")
WEBAPP_URL = os.getenv("WEBAPP_URL", "https://your-app.fadehost.app")

bot = Bot(token=BOT_TOKEN) if BOT_TOKEN else None
dp = Dispatcher()

# Инициализация FastAPI
app = FastAPI()

@app.get("/api/districts")
def api_get_districts():
    """Эндпоинт для получения списка районов"""
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
    """Эндпоинт для получения статистики рынка"""
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
    """Отдача index.html мини-приложения"""
    index_path = os.path.join("webapp", "index.html")
    if os.path.exists(index_path):
        with open(index_path, "r", encoding="utf-8") as f:
            return f.read()
    return "<h3>Файл webapp/index.html не найден!</h3>"


# --- Хендлеры Telegram-бота ---

@dp.message(CommandStart())
async def cmd_start(message: Message):
    """Стартовое сообщение с кнопкой открытия Mini App"""
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
        "Нажмите на кнопку ниже, чтобы открыть панель управления и статистику:",
        reply_markup=keyboard
    )


# --- Запуск ---

async def run_fastapi():
    config = uvicorn.Config(app, host="0.0.0.0", port=8000, log_level="info")
    server = uvicorn.Server(config)
    await server.serve()

async def main():
    if not bot:
        logger.error("❌ Бот не может быть запущен без токена!")
        return
        
    logger.info("🚀 Запуск сервера и Telegram-бота...")
    fastapi_task = asyncio.create_task(run_fastapi())
    await dp.start_polling(bot)
    await fastapi_task

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Приложение остановлено.")