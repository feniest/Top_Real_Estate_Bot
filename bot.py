import os
import logging
import asyncio
import psycopg2
from psycopg2.extras import RealDictCursor
from fastapi import FastAPI, Query, Request
from fastapi.responses import HTMLResponse, Response
import uvicorn
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, WebAppInfo, InlineKeyboardMarkup, InlineKeyboardButton, InputMediaPhoto, InputMediaVideo, BufferedInputFile
from aiogram.filters import CommandStart, Command
from pydantic import BaseModel

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Получение токена и URL из переменных окружения
BOT_TOKEN = os.getenv("BOT_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN") or os.getenv("TOKEN")
WEBAPP_URL = os.getenv("WEBAPP_URL", "https://toprealestatebot.fadehost.app")

# Константы для связи с риелтором
REALTOR_TELEGRAM_ID = 123456789  # <--- Замените на реальный Telegram ID риелтора
REALTOR_PHONE = "+998901234567"
REALTOR_TG_USERNAME = "realtor_username"

if not BOT_TOKEN:
    logger.error("❌ Не найден токен бота в переменных окружения!")

bot = Bot(token=BOT_TOKEN) if BOT_TOKEN else None
dp = Dispatcher()

# Инициализация FastAPI для веб-приложения
app = FastAPI()

# --- Встроенные функции работы с базой данных ---

def get_connection():
    """Подключение к базе данных PostgreSQL"""
    return psycopg2.connect(
        dbname=os.getenv("DB_NAME", "postgres"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD", ""),
        host=os.getenv("DB_HOST", "localhost"),
        port=os.getenv("DB_PORT", "5432")
    )

def create_indexes():
    """Автоматически создает индексы для ускорения фильтрации в PostgreSQL при старте"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_ads_active_category ON ads (is_active, category);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_ads_active_prop_type ON ads (is_active, property_type);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_ads_active_district ON ads (is_active, district);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_ads_rooms_num ON ads ((NULLIF(rooms, '')::integer));")
        conn.commit()
        cursor.close()
        conn.close()
        logger.info("⚡ Индексы базы данных успешно проверены/созданы — фильтрация будет работать быстро.")
    except Exception as e:
        logger.error(f"⚠️ Ошибка при создании индексов базы данных: {e}")

def get_object_by_number(ad_number: str):
    """Получает полную информацию об объекте по его номеру"""
    try:
        conn = get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("SELECT * FROM ads WHERE ad_number = %s", (ad_number,))
        row = cursor.fetchone()
        cursor.close()
        conn.close()
        return row
    except Exception as e:
        logger.error(f"⚠️ Ошибка получения объекта {ad_number}: {e}")
        return None

def get_ad_media(ad_number: str):
    """Возвращает список медиафайлов (имя и бинарные данные) для объекта из таблицы ad_media"""
    try:
        conn = get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute(
            "SELECT file_name, file_data FROM ad_media WHERE ad_number = %s", 
            (ad_number,)
        )
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return rows
    except Exception as e:
        logger.error(f"⚠️ Ошибка получения медиа для объекта {ad_number}: {e}")
        return []

def get_districts():
    """Возвращает список уникальных районов только по активным объявлениям (is_active = 1)"""
    try:
        conn = get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("""
            SELECT DISTINCT district 
            FROM ads 
            WHERE is_active = 1 AND district IS NOT NULL AND district != '' 
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
    """Возвращает детальную статистику по активным объявлениям (is_active = 1)"""
    try:
        conn = get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        query = """
            SELECT 
                category,
                COUNT(*) as total_count,
                COUNT(*) FILTER (WHERE NULLIF(rooms, '')::integer = 1) as rooms_1,
                COUNT(*) FILTER (WHERE NULLIF(rooms, '')::integer = 2) as rooms_2,
                COUNT(*) FILTER (WHERE NULLIF(rooms, '')::integer = 3) as rooms_3,
                COUNT(*) FILTER (WHERE NULLIF(rooms, '')::integer = 4) as rooms_4,
                COUNT(*) FILTER (WHERE NULLIF(rooms, '')::integer >= 5) as rooms_5_plus,
                MIN(price) as min_price,
                MAX(price) as max_price,
                ROUND(AVG(price)::numeric, 0) as avg_price
            FROM ads
            WHERE is_active = 1
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
                query += " AND NULLIF(rooms, '')::integer >= 5"
            else:
                query += " AND NULLIF(rooms, '')::integer = %s"
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

def get_filtered_objects(
    category: str = None,
    prop_type: str = None,
    rooms: str = None,
    district: str = None
):
    """Возвращает полный список активных объектов по заданным фильтрам"""
    try:
        conn = get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        query = """
            SELECT 
                ad_number,
                category,
                property_type,
                rooms,
                district,
                landmark,
                area,
                floor,
                floors_total,
                price
            FROM ads
            WHERE is_active = 1
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
                query += " AND NULLIF(rooms, '')::integer >= 5"
            else:
                query += " AND NULLIF(rooms, '')::integer = %s"
                params.append(int(rooms))

        if district and district != 'all':
            query += " AND district = %s"
            params.append(district)

        query += r" ORDER BY NULLIF(regexp_replace(ad_number, '\D', '', 'g'), '')::integer ASC, ad_number ASC;"

        cursor.execute(query, params)
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        results = []
        for r in rows:
            ad_num = r.get("ad_number")
            type_label = "Квартира" if r.get("property_type") == "Apartments" else "Дом / участок"
            title_text = f"№ {ad_num} • {r.get('rooms')}-комн. ({type_label})"
            if r.get("landmark"):
                title_text += f" — {r.get('landmark')}"
                
            media_rows = get_ad_media(ad_num)
            media_urls = [f"/api/media/{ad_num}/{i}" for i in range(len(media_rows))] if media_rows else []

            results.append({
                "id": ad_num, # Добавлено поле id для корректной сортировки на фронтенде
                "ad_number": ad_num,
                "title": title_text,
                "district": r.get("district"),
                "landmark": r.get("landmark"),
                "rooms": r.get("rooms"),
                "area": r.get("area"),
                "floor": r.get("floor"),
                "floors_total": r.get("floors_total"),
                "price": r.get("price"),
                "currency": "у.е.",
                "media": media_urls
            })
        return results
    except Exception as e:
        logger.error(f"⚠️ Ошибка в get_filtered_objects: {e}")
        return []


# --- Модели данных Pydantic ---

class RealtorLead(BaseModel):
    user_name: str
    user_phone: str
    ad_number: str
    object_title: str
    object_price: float | int | None = None
    category: str | None = None


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

@app.get("/api/objects")
def api_get_objects(
    category: str = Query(None),
    prop_type: str = Query(None),
    rooms: str = Query(None),
    district: str = Query(None)
):
    return get_filtered_objects(
        category=category,
        prop_type=prop_type,
        rooms=rooms,
        district=district
    )

@app.post("/api/realtor-lead")
async def api_realtor_lead(lead: RealtorLead):
    """Принимает заявку из веб-приложения и отправляет сообщение риелтору в Telegram"""
    try:
        if not bot:
            return {"status": "error", "message": "Bot is not initialized"}

        price_str = f"{lead.object_price:,.0f}" if lead.object_price else "Не указана"
        
        message_text = (
            "🔔 **Новая заявка по объекту!**\n\n"
            f"🏢 **Объект:** № {lead.ad_number}\n"
            f"📌 **Название:** {lead.object_title}\n"
            f"💰 **Цена:** {price_str} у.е.\n\n"
            f"👤 **Имя клиента:** {lead.user_name}\n"
            f"📞 **Телефон:** `{lead.user_phone}`"
        )

        await bot.send_message(
            chat_id=REALTOR_TELEGRAM_ID,
            text=message_text,
            parse_mode="Markdown"
        )
        
        logger.info(f"✅ Заявка по объекту № {lead.ad_number} от клиента {lead.user_name} успешно отправлена риелтору.")
        return {"status": "ok"}
    except Exception as e:
        logger.error(f"⚠️ Ошибка отправки лида риелтору: {e}")
        return {"status": "error", "message": str(e)}

@app.get("/api/media/{ad_number}/{index}")
def api_get_media_file(ad_number: str, index: int):
    """Эндпоинт для отдачи картинок и видео в веб-приложение"""
    media_rows = get_ad_media(ad_number)
    if not media_rows or index >= len(media_rows):
        return Response(status_code=404)
    
    row = media_rows[index]
    file_bytes = bytes(row['file_data'])
    file_name = (row['file_name'] or "").lower()
    
    video_extensions = ('.mp4', '.mov', '.avi', '.mkv', '.webm', '.m4v', '.3gp')
    
    if file_name.endswith(video_extensions):
        content_type = "video/mp4"
    elif file_name.endswith('.png'):
        content_type = "image/png"
    elif file_name.endswith('.webp'):
        content_type = "image/webp"
    else:
        content_type = "image/jpeg"
        
    return Response(
        content=file_bytes, 
        media_type=content_type,
        headers={"Cache-Control": "public, max-age=86400"}
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
        "Нажмите на кнопку ниже, чтобы открыть панель управления и статистику,\n"
        "или введите команду получения объекта, например: `/object 101`",
        reply_markup=keyboard
    )

@dp.message(Command("object"))
async def cmd_get_object(message: Message):
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer("⚠️ Пожалуйста, укажите номер объекта. Пример: `/object 1`", parse_mode="Markdown")
        return
    
    ad_number = args[1].strip()
    obj_data = get_object_by_number(ad_number)
    
    if not obj_data:
        await message.answer(f"❌ Объект с номером **{ad_number}** не найден в базе данных.", parse_mode="Markdown")
        return

    prop_type_label = "Квартира" if obj_data.get("property_type") == "Apartments" else "Дом / участок"
    description = (
        f"🏢 **Объект № {obj_data.get('ad_number')}**\n"
        f"📂 Категория: {obj_data.get('category')}\n"
        f"🏠 Тип: {prop_type_label}\n"
        f"🚪 Комнат: {obj_data.get('rooms')}\n"
        f"📍 Район: {obj_data.get('district')}\n"
        f"🏷 Ориентир: {obj_data.get('landmark', 'Не указан')}\n"
        f"📐 Площадь: {obj_data.get('area')} кв.м.\n"
        f"🏢 Этаж: {obj_data.get('floor')} / {obj_data.get('floors_total')}\n"
        f"💰 Цена: **{obj_data.get('price')} у.е.**"
    )

    media_rows = get_ad_media(ad_number)

    if media_rows:
        media_group = []
        video_extensions = ('.mp4', '.mov', '.avi', '.mkv', '.webm')
        
        for idx, row in enumerate(media_rows[:10]):
            try:
                file_bytes = bytes(row['file_data'])
                file_name = (row['file_name'] or f"media_{idx}").lower()
                
                input_file = BufferedInputFile(file_bytes, filename=row['file_name'] or f"file_{idx}")
                
                caption = description if idx == 0 else None
                parse_mode = "Markdown" if idx == 0 else None
                
                if file_name.endswith(video_extensions):
                    media_group.append(
                        InputMediaVideo(media=input_file, caption=caption, parse_mode=parse_mode)
                    )
                else:
                    media_group.append(
                        InputMediaPhoto(media=input_file, caption=caption, parse_mode=parse_mode)
                    )
            except Exception as ex:
                logger.error(f"Ошибка обработки медиафайла для объекта {ad_number}: {ex}")

        if media_group:
            try:
                await message.answer_media_group(media=media_group)
                return
            except Exception as e:
                logger.error(f"Ошибка отправки медиа-группы в Telegram: {e}")

    await message.answer(description, parse_mode="Markdown")


# --- Запуск ---

async def run_fastapi():
    port = int(os.getenv("PORT", 8080))
    config = uvicorn.Config(app, host="0.0.0.0", port=port, log_level="info")
    server = uvicorn.Server(config)
    await server.serve()

async def main():
    if not bot:
        logger.error("❌ Запуск отменен: отсутствует токен бота.")
        return
        
    create_indexes()
        
    logger.info("🚀 Запуск веб-сервера и Telegram-бота...")
    fastapi_task = asyncio.create_task(run_fastapi())
    await dp.start_polling(bot)
    await fastapi_task

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Приложение остановлено.")