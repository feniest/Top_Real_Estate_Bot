import os
import json
import asyncio
import logging
import sys
import psycopg2
import psycopg2.extras
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
import uvicorn
from aiogram import Bot, Dispatcher, types, F, Router

# --- 1. НАСТРОЙКА БАЗЫ ДАННЫХ POSTGRESQL ---
def get_db_connection():
    # Проверяем общую строку подключения, если она задана
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        return psycopg2.connect(database_url, cursor_factory=psycopg2.extras.RealDictCursor)
    
    # Иначе собираем параметры автоматически из переменных окружения FadeHost (DB_*)
    db_host = os.getenv("DB_HOST")
    db_port = os.getenv("DB_PORT", "5432")
    db_name = os.getenv("DB_NAME")
    db_user = os.getenv("DB_USER")
    db_password = os.getenv("DB_PASSWORD")
    
    if all([db_host, db_name, db_user, db_password]):
        return psycopg2.connect(
            host=db_host,
            port=db_port,
            dbname=db_name,
            user=db_user,
            password=db_password,
            cursor_factory=psycopg2.extras.RealDictCursor
        )
    
    raise RuntimeError(
        "Не найдены параметры подключения к базе данных! "
        "Убедитесь, что задана переменная DATABASE_URL или набор переменных DB_HOST, DB_NAME, DB_USER, DB_PASSWORD."
    )


# --- 2. НАСТРОЙКА FASTAPI И ВЕБ-СЕРВЕРА ---
app = FastAPI()

# Подключаем статические файлы и корневую страницу мини-приложения
app.mount("/static", StaticFiles(directory="webapp"), name="static")

@app.get("/")
def serve_webapp():
    return FileResponse("webapp/index.html")

# API для получения списка объявлений (каталог с фильтрами)
@app.get("/api/ads")
def get_ads(category: str = "Rent", prop_type: str = "all"):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        query = "SELECT * FROM ads WHERE category = %s"
        params = [category]
        
        if prop_type != "all":
            query += " AND prop_type = %s"
            params.append(prop_type)
            
        cursor.execute(query, params)
        ads = cursor.fetchall()
        
        cursor.close()
        conn.close()
        return ads
    except Exception as e:
        print(f"Ошибка при получении объявлений: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# API для получения списка медиафайлов (фото/видео) конкретного объекта
@app.get("/api/media-list/{ad_num}")
def get_media_list(ad_num: int):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT id, type FROM media WHERE ad_num = %s ORDER BY id ASC", (ad_num,))
        media = cursor.fetchall()
        
        cursor.close()
        conn.close()
        return media
    except Exception as e:
        print(f"Ошибка при получении списка медиа: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# API для скачивания конкретного файла медиа из базы
@app.get("/api/media-file/{media_id}")
def get_media_file(media_id: int):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT file_data, mime_type FROM media WHERE id = %s", (media_id,))
        row = cursor.fetchone()
        
        cursor.close()
        conn.close()
        
        if not row:
            raise HTTPException(status_code=404, detail="Файл не найден")
            
        return Response(content=row['file_data'], media_type=row['mime_type'])
    except Exception as e:
        print(f"Ошибка при отдаче медиафайла: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# --- 3. НАСТРОЙКА TELEGRAM-БОТА И РОУТЕРА ЗАЯВОК ---
router = Router()

REALTOR_ID_STR = os.getenv("REALTOR_ID") or os.getenv("ADMIN_ID")
if not REALTOR_ID_STR:
    raise ValueError("Не найден REALTOR_ID в переменных окружения!")
REALTOR_ID = int(REALTOR_ID_STR)

@router.message(F.web_app_data)
async def handle_web_app_data(message: types.Message):
    try:
        data = json.loads(message.web_app_data.data)
        if data.get("action") == "contact":
            ad_num = data.get("ad_num")
            
            client_name = message.from_user.full_name
            client_username = f"@{message.from_user.username}" if message.from_user.username else "скрыт"
            client_id = message.from_user.id
            
            realtor_text = (
                f"🚨 **Новая заявка из мини-приложения!**\n\n"
                f"🏠 Объект №: **{ad_num}**\n"
                f"👤 Клиент: {client_name} ({client_username})\n"
                f"🆔 Telegram ID: `{client_id}`"
            )

            keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
                [types.InlineKeyboardButton(text="💬 Написать клиенту", url=f"tg://user?id={client_id}")]
            ])

            await message.bot.send_message(
                chat_id=REALTOR_ID,
                text=realtor_text,
                parse_mode="Markdown",
                reply_markup=keyboard
            )

            await message.answer("✅ Ваша заявка успешно отправлена нашему риелтору! Скоро с вами свяжутся.")
            
    except Exception as e:
        print(f"Ошибка обработки Web App данных: {e}")
        await message.answer("❌ Произошла ошибка при отправке заявки. Попробуйте еще раз.")


# --- 4. ГЛАВНАЯ ТОЧКА ЗАПУСКА ---
async def main():
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not bot_token:
        raise ValueError("Не найден TELEGRAM_BOT_TOKEN в переменных окружения!")

    bot = Bot(token=bot_token)
    dp = Dispatcher()
    dp.include_router(router)

    # Запускаем телеграм-бота в фоне
    asyncio.create_task(dp.start_polling(bot))
    print("Telegram бот запущен в фоновом режиме...")

    # Запускаем FastAPI сервер на порту хостинга
    port = int(os.getenv("PORT", 8080))
    config = uvicorn.Config(app, host="0.0.0.0", port=port, log_level="info")
    server = uvicorn.Server(config)
    
    await server.serve()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    asyncio.run(main())