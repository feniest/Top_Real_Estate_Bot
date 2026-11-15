import os
import logging
import asyncio
import psycopg2
from aiogram import Bot, Dispatcher, Router, types
from aiogram.filters import CommandStart
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
import uvicorn
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, Response
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

# --- ПОДКЛЮЧЕНИЕ К POSTGRESQL ДЛЯ МЕДИАФАЙЛОВ ---
def get_pg_connection():
    return psycopg2.connect(
        host="37.187.139.87",
        port=35919,
        database="fh7cba1949de20442fb8484660cc696208",
        user="postgres",
        password="7H6SEUopuXHTa9Hu9vpJ04onLYZ4",
        connect_timeout=5
    )

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

# 1. Возвращает список всех ID медиафайлов для объявления (фото и видео)
@app.get("/api/media-list/{ad_num}")
async def get_ad_media_list(ad_num: str):
    try:
        conn = get_pg_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, file_name FROM ad_media WHERE ad_number = %s ORDER BY id ASC",
            (str(ad_num),)
        )
        rows = cursor.fetchall()
        cursor.close()
        conn.close()

        media_items = []
        for media_id, file_name in rows:
            ext = file_name.lower().split('.')[-1]
            m_type = "video" if ext in ['mp4', 'avi', 'mov', 'mkv', 'webm'] else "image"
            media_items.append({"id": media_id, "type": m_type, "name": file_name})
        return media_items
    except Exception as e:
        logging.error(f"Ошибка получения списка медиа: {e}")
        return []

# 2. Отдает конкретный файл (фото или видео) по его ID из таблицы ad_media
@app.get("/api/media-file/{media_id}")
async def get_media_file(media_id: int):
    try:
        conn = get_pg_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT file_name, file_data FROM ad_media WHERE id = %s",
            (media_id,)
        )
        row = cursor.fetchone()
        cursor.close()
        conn.close()

        if not row:
            return Response(status_code=404)

        file_name, file_data = row
        ext = file_name.lower().split('.')[-1]
        
        mime_types = {
            "jpg": "image/jpeg",
            "jpeg": "image/jpeg",
            "png": "image/png",
            "webp": "image/webp",
            "gif": "image/gif",
            "mp4": "video/mp4",
            "mov": "video/quicktime",
            "webm": "video/webm"
        }
        content_type = mime_types.get(ext, "application/octet-stream")
        return Response(content=bytes(file_data), media_type=content_type)
    except Exception as e:
        logging.error(f"Ошибка отдачи медиафайла {media_id}: {e}")
        return Response(status_code=500, content=str(e))

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
    port = int(os.getenv("PORT", 8080))
    logging.info("🤖 Запуск Telegram-бота и FastAPI сервера...")

    bot_task = asyncio.create_task(dp.start_polling(bot))

    config = uvicorn.Config(app, host="0.0.0.0", port=port, log_level="info")
    server = uvicorn.Server(config)
    
    await server.serve()
    await bot_task

if __name__ == "__main__":
    asyncio.run(main())