import asyncio
import logging
import sys
import os
import json
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, Response, FileResponse
from fastapi.staticfiles import StaticFiles
from aiogram import Bot, Dispatcher, types, F, Router
import database as db
from handlers import catalog
from config import BOT_TOKEN, REALTOR_ID

app = FastAPI(title="Top Real Estate Mini App")

# Словарь для хранения медиафайлов в оперативной памяти сервера (RAM)
MEDIA_CACHE = {}

# Автоматически создаем папку webapp для Mini App и копируем интерфейс при необходимости
os.makedirs("webapp", exist_ok=True)
if os.path.exists("index_3.html") and not os.path.exists("webapp/index.html"):
    with open("index_3.html", "r", encoding="utf-8") as f_src:
        with open("webapp/index.html", "w", encoding="utf-8") as f_dst:
            f_dst.write(f_src.read())

if os.path.exists("webapp"):
    app.mount("/static", StaticFiles(directory="webapp"), name="static")

@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    if os.path.exists("favicon.ico"):
        return FileResponse("favicon.ico")
    return Response(status_code=204)

@app.get("/", response_class=HTMLResponse)
def serve_webapp():
    if os.path.exists("webapp/index.html"):
        with open("webapp/index.html", "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>Мини-приложение загружается или файл webapp/index.html не найден</h1>"

@app.get("/api/ads")
def get_ads(category: str = "Rent", prop_type: str = "all"):
    try:
        ads = db.get_filtered_ads(category=category, prop_type=prop_type)
        result = []
        for ad in ads:
            if isinstance(ad, dict):
                result.append({
                    "ad_num": ad.get('ad_number'),
                    "category": ad.get('category'),
                    "prop_type": ad.get('property_type'),
                    "rooms": ad.get('rooms'),
                    "district": ad.get('district'),
                    "landmark": ad.get('landmark'),
                    "area": ad.get('area'),
                    "floor": ad.get('floor'),
                    "floors_total": ad.get('floors_total'),
                    "price": ad.get('price')
                })
            else:
                # На случай, если БД вернет кортеж (tuple)
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
    except Exception as e:
        print(f"⚠️ Ошибка при получении объявлений: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/media-list/{ad_num}")
def get_media_list(ad_num: str):
    try:
        files = db.get_ad_media_files(ad_num)
        if not files:
            return []
        media = []
        for idx, row in enumerate(files):
            fname = row.get('file_name', '') if isinstance(row, dict) else row[0]
            ext = fname.lower().split('.')[-1] if '.' in fname else 'jpg'
            m_type = 'video' if ext in ['mp4', 'avi', 'mov', 'mkv'] else 'photo'
            media.append({"id": f"{ad_num}_{idx}", "type": m_type, "file_name": fname})
        return media
    except Exception as e:
        print(f"⚠️ Ошибка в get_media_list для ad_num={ad_num}: {e}")
        return []

@app.get("/api/media-file/{media_identifier}")
def get_media_file(media_identifier: str):
    # 1. Проверяем наличие файла в RAM-кэше сервера
    if media_identifier in MEDIA_CACHE:
        content, mime = MEDIA_CACHE[media_identifier]
        return Response(
            content=content,
            media_type=mime,
            headers={"Cache-Control": "public, max-age=86400"}
        )

    # 2. Если в кэше нет — загружаем из PostgreSQL и сохраняем в RAM
    try:
        parts = media_identifier.split("_", 1)
        if len(parts) != 2:
            raise HTTPException(status_code=404, detail="Неверный идентификатор")
        ad_num, idx_str = parts
        idx = int(idx_str)

        files = db.get_ad_media_files(ad_num)
        if not files or idx >= len(files):
            raise HTTPException(status_code=404, detail="Файл не найден")

        row = files[idx]
        fname = row.get('file_name', '') if isinstance(row, dict) else row[0]
        fdata = row.get('file_data') if isinstance(row, dict) else row[1]

        ext = fname.lower().split('.')[-1] if '.' in fname else 'jpg'
        mime_map = {
            'mp4': 'video/mp4',
            'mov': 'video/quicktime',
            'avi': 'video/x-msvideo',
            'mkv': 'video/x-matroska',
            'png': 'image/png',
            'webp': 'image/webp'
        }
        mime = mime_map.get(ext, 'image/jpeg')

        # Ограничиваем кэш до 150 файлов для экономии памяти
        if len(MEDIA_CACHE) > 150:
            MEDIA_CACHE.clear()
        MEDIA_CACHE[media_identifier] = (fdata, mime)

        return Response(
            content=fdata,
            media_type=mime,
            headers={"Cache-Control": "public, max-age=86400"}
        )
    except HTTPException:
        raise
    except Exception as e:
        print(f"⚠️ Ошибка при отдаче файла {media_identifier}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Обработка заявок из Mini App (кнопка связи с риелтором)
webapp_router = Router()

@webapp_router.message(F.web_app_data)
async def handle_web_app_data(message: types.Message):
    try:
        data = json.loads(message.web_app_data.data)
        if data.get("action") == "contact" and REALTOR_ID:
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
            await message.bot.send_message(chat_id=REALTOR_ID, text=realtor_text, parse_mode="Markdown", reply_markup=keyboard)
            await message.answer("✅ Ваша заявка успешно отправлена нашему риелтору! Скоро с вами свяжутся.")
    except Exception as e:
        print(f"Ошибка Web App: {e}")

async def main():
    if not BOT_TOKEN:
        raise ValueError("Не найден TELEGRAM_BOT_TOKEN!")

    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()
    dp.include_router(catalog.router)
    dp.include_router(webapp_router)

    # Запуск Telegram-бота в фоновом режиме
    asyncio.create_task(dp.start_polling(bot))
    print("Telegram бот успешно запущен в фоновом режиме...")

    # Запуск FastAPI сервера для Mini App
    import uvicorn
    port = int(os.getenv("PORT", 8080))
    config = uvicorn.Config(app, host="0.0.0.0", port=port, log_level="info")
    server = uvicorn.Server(config)
    await server.serve()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    asyncio.run(main())