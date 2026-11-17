import os
import logging
import asyncio
import psycopg2
from psycopg2.extras import RealDictCursor
from fastapi import FastAPI, Query, Request
from fastapi.responses import HTMLResponse
import uvicorn
from aiogram import Bot, Dispatcher
from aiogram.types import Message, WebAppInfo, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import CommandStart

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

# Инициализация FastAPI для веб-приложения
app = FastAPI()

# --- Встроенные функции работы с базой данных (напрямую через psycopg2) ---

def get_connection():
    """Подключение к базе данных PostgreSQL"""
    return psycopg2.connect(
        dbname=os.getenv("DB_NAME", "postgres"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD", ""),
        host=os.getenv("DB_HOST", "localhost"),
        port=os.getenv("DB_PORT", "5432")
    )

def get_districts():
    """Возвращает список уникальных районов из таблицы ads"""
    try:
        conn = get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("""
            SELECT DISTINCT district 
            FROM ads 
            WHERE district IS NOT NULL AND district != '' 
            ORDER BY district;
        """)
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return [row['district'] for row in rows]
    except Exception as e:
        logger.error(f"⚠️ Ошибка в get_districts: {e}")
        return []

def get_market_statistics(
    category: str = None,
    prop_type: str = None,
    rooms: str = None,
    district: str = None
):
    """Возвращает детальную статистику по категориям (Rent / Sale) с учетом фильтров"""
    try:
        conn = get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        query = """
            SELECT 
                category,
                COUNT(*) as total_count,
                COUNT(*) FILTER (WHERE rooms = 1) as rooms_1,
                COUNT(*) FILTER (WHERE rooms = 2) as rooms_2,
                COUNT(*) FILTER (WHERE rooms = 3) as rooms_3,
                COUNT(*) FILTER (WHERE rooms = 4) as rooms_4,
                COUNT(*) FILTER (WHERE rooms >= 5) as rooms_5_plus,
                MIN(price) as min_price,
                MAX(price) as max_price,
                ROUND(AVG(price)::numeric, 0) as avg_price
            FROM ads
            WHERE 1=1
        """
        params = []

        if category and category != 'all':
            query += " AND category = %s"
            params.append(category)

        if prop_type and prop_type != 'all':
            query += " AND property_type = %s"
            params.append(prop_type)

        if rooms and rooms != 'all':
            if rooms == '5+':
                query += " AND rooms >= 5"
            else:
                query += " AND rooms = %s"
                params.append(int(rooms))

        if district and district != 'all':
            query += " AND district = %s"
            params.append(district)

        query += " GROUP BY category;"

        cursor.execute(query, params)
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        stats = {}
        for row in rows:
            cat = row.get('category')
            stats[cat] = {
                "count": row.get('total_count', 0),
                "rooms_1": row.get('rooms_1', 0),
                "rooms_2": row.get('rooms_2', 0),
                "rooms_3": row.get('rooms_3', 0),
                "rooms_4": row.get('rooms_4', 0),
                "rooms_5_plus": row.get('rooms_5_plus', 0),
                "min_price": row.get('min_price', 0),
                "max_price": row.get('max_price', 0),
                "avg_price": row.get('avg_price', 0)
            }
        return stats
    except Exception as e:
        logger.error(f"⚠️ Ошибка в get_market_statistics: {e}")
        return {}


# --- Эндпоинты FastAPI ---

@app.get("/api/districts")
def api_get_districts():
    return get_districts()

@app.get("/api/stats")
def api_get_stats(
    category: str = Query(None),
    prop_type: str = Query(None),
    rooms: str = Query(None),
    district: str = Query(None)
):
    return get_market_statistics(
        category=category,
        prop_type=prop_type,
        rooms=rooms,
        district=district
    )

@app.get("/", response_class=HTMLResponse)
def serve_webapp(request: Request):
    index_path = os.path.join("webapp", "index.html")
    if os.path.exists(index_path):
        with open(index_path, "r", encoding="utf-8") as f:
            return f.read()
    return "<h3>Файл webapp/index.html не найден!</h3>"


# --- Хендлеры Telegram-бота ---

@dp.message(CommandStart())
async def cmd_start(message: Message):
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
        logger.error("❌ Запуск отменен: отсутствует токен бота.")
        return
        
    logger.info("🚀 Запуск веб-сервера и Telegram-бота...")
    fastapi_task = asyncio.create_task(run_fastapi())
    await dp.start_polling(bot)
    await fastapi_task

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Приложение остановлено.")