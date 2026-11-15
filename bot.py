import os
import logging
from aiogram import Bot, Dispatcher, Router, types
from aiogram.filters import CommandStart
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
import uvicorn
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
import database as db

# Настройка логирования
logging.basicConfig(level=logging.INFO)

# Инициализация бота и диспетчера
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN") or os.getenv("BOT_TOKEN")
if not TOKEN:
    raise ValueError("Не найден токен бота! Проверьте переменные окружения на хостинге.")

bot = Bot(token=TOKEN)
dp = Dispatcher()
router = Router()

# URL вашего мини-приложения на хостинге FadeHost Laplace
WEB_APP_URL = "https://toprealestatebot.fadehost.app"

# --- ОБРАБОТЧИКИ БОТА ---

@router.message(CommandStart())
async def cmd_start(message: types.Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="📱 Открыть каталог недвижимости",
                web_app=WebAppInfo(url=WEB_APP_URL)
            )
        ]
    ])
    await message.answer(
        text="<b>🏢 РБД УПРАВЛЕНИЕ НЕДВИЖИМОСТЬЮ</b>\n\n"
             "Нажмите на кнопку ниже, чтобы запустить удобный каталог с фильтрами и карточками объектов прямо в Telegram:",
        reply_markup=kb,
        parse_mode="HTML"
    )

dp.include_router(router)


# --- СЕРВЕР FASTAPI ДЛЯ MINI APP ---

app = FastAPI(title="Top Real Estate Mini App")

# Подключаем статический HTML-файл мини-приложения из папки webapp/index.html
@app.get("/", response_class=HTMLResponse)
async def serve_mini_app():
    index_path = os.path.join("webapp", "index.html")
    if os.path.exists(index_path):
        with open(index_path, "r", encoding="utf-8") as f:
            return f.read()
    return "<h3>Файл webapp/index.html не найден на сервере!</h3>"

# API для отдачи объектов недвижимости в мини-приложение
@app.get("/api/ads")
async def get_ads(category: str = "Rent", prop_type: str = "all"):
    raw_ads = db.get_filtered_ads(category=category, prop_type=prop_type)
    result = []
    
    for ad in raw_ads:
        result.append({
            "ad_num": ad[0],
            "category": ad[1],
            "prop_type": ad[2],
            "rooms": ad[3],
            "district": ad[4],
            "landmark": ad[5],
            "area": ad[6],
            "floor": ad[7],
            "floors_total": ad[8],
            "price": ad[9]
        })
    return result


# --- ЗАПУСК ВСЕЙ СИСТЕМЫ ---

async def main():
    # Получаем порт от хостинга FadeHost (или используем 8080 по умолчанию)
    port = int(os.getenv("PORT", 8080))
    
    logging.basicConfig(level=logging.INFO)
    logging.info("🤖 Запуск Telegram-бота и FastAPI сервера...")

    # Запускаем поллинг бота в фоновой задаче
    bot_task = asyncio.create_task(dp.start_polling(bot))

    # Запускаем веб-сервер uvicorn для Mini App
    config = uvicorn.Config(app, host="0.0.0.0", port=port, log_level="info")
    server = uvicorn.Server(config)
    
    await server.serve()
    await bot_task

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())