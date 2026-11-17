import os
import logging
import asyncio
from fastapi import FastAPI, Query, Request
from fastapi.responses import HTMLResponse
import uvicorn
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, WebAppInfo, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import CommandStart

# Импортируем ваши функции работы с базой данных
from database import get_districts, get_market_statistics

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Токен вашего Telegram-бота (лучше передавать через переменные окружения)
BOT_TOKEN = os.getenv("BOT_TOKEN", "ВАШ_ТОКЕН_БОТА")

# URL вашего развернутого приложения (например, на FadeHost Laplace или ngrok)
WEBAPP_URL = os.getenv("WEBAPP_URL", "https://ваш-домен.fadehost.app")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Инициализация FastAPI для Mini App и API
app = FastAPI()

@app.get("/api/districts")
def api_get_districts():
    """Эндпоинт для получения списка уникальных районов"""
    return get_districts()

@app.get("/api/stats")
def api_get_stats(
    category: str = Query(None),
    prop_type: str = Query(None),
    rooms: str = Query(None),
    district: str = Query(None)
):
    """Эндпоинт для получения агрегированной статистики рынка"""
    return get_market_statistics(
        category=category,
        prop_type=prop_type,
        rooms=rooms,
        district=district
    )

@app.get("/", response_class=HTMLResponse)
def serve_webapp(request: Request):
    """Опциональная отдача index.html прямо с сервера (если папка webapp рядом)"""
    index_path = os.path.join("webapp", "index.html")
    if os.path.exists(index_path):
        with open(index_path, "r", encoding="utf-8") as f:
            return f.read()
    return "<h3>Файл webapp/index.html не найден на сервере!</h3>"


# --- Хендлеры Telegram-бота ---

@dp.message(CommandStart())
async def cmd_start(message: Message):
    """Приветствие и кнопка запуска мини-приложения при обращении к боту"""
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
        "Нажмите на кнопку ниже, чтобы открыть интерактивную панель управления и статистику недвижимости:",
        reply_markup=keyboard
    )


# --- Запуск FastAPI и Telegram-бота одновременно ---

async def run_fastapi():
    """Запуск Uvicorn сервера для API и веб-приложения"""
    config = uvicorn.Config(app, host="0.0.0.0", port=8000, log_level="info")
    server = uvicorn.Server(config)
    await server.serve()

async def main():
    logger.info("🚀 Запуск бота и FastAPI сервера...")
    # Запускаем FastAPI в фоне, а бота в основном потоке поллинга
    fastapi_task = asyncio.create_task(run_fastapi())
    
    # Запуск поллинга Telegram-бота
    await dp.start_polling(bot)
    
    await fastapi_task

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Бот остановлен.")