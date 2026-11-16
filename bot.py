import asyncio
import logging
import sys
import os
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from aiogram import Bot, Dispatcher, types, F, Router
import database as db
from handlers import catalog
from config import BOT_TOKEN, REALTOR_ID

app = FastAPI(title="Top Real Estate Mini App")

# Автоматически создаем папку webapp для Mini App и копируем интерфейс
os.makedirs("webapp", exist_ok=True)
if os.path.exists("index_3.html") and not os.path.exists("webapp/index.html"):
    with open("index_3.html", "r", encoding="utf-8") as f_src:
        with open("webapp/index.html", "w", encoding="utf-8") as f_dst:
            f_dst.write(f_src.read())

if os.path.exists("webapp/index.html"):
    app.mount("/static", StaticFiles(directory="webapp"), name="static")

@app.get("/", response_class=HTMLResponse)
def serve_webapp():
    if os.path.exists("webapp/index.html"):
        with open("webapp/index.html", "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>Мини-приложение загружается или файл index.html не найден</h1>"

@app.get("/api/ads")
def get_ads(category: str = "Rent", prop_type: str = "all"):
    try:
        ads = db.get_filtered_ads(category=category, prop_type=prop_type)
        result = []
        for ad in ads:
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
        return result
    except Exception as e:
        print(f"Ошибка при получении объявлений: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/media-list/{ad_num}")
def get_media_list(ad_num: str):
    try:
        files = db.get_ad_media_files(ad_num)
        media = []
        for idx, row in enumerate(files):
            fname = row.get('file_name', '')
            ext = fname.lower().split('.')[-1] if '.' in fname else 'jpg'
            m_type = 'video' if ext in ['mp4', 'avi', 'mov', 'mkv'] else 'photo'
            media.append({"id": f"{ad_num}_{idx}", "type": m_type, "file_name": fname})
        return media
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/media-file/{media_identifier}")
def get_media_file(media_identifier: str):
    try:
        parts = media_identifier.split("_", 1)
        if len(parts) != 2:
            raise HTTPException(status_code=404, detail="Неверный идентификатор")
        ad_num, idx_str = parts
        idx = int(idx_str)
        files = db.get_ad_media_files(ad_num)
        if idx >= len(files):
            raise HTTPException(status_code=404, detail="Файл не найден")
        row = files[idx]
        mime = row.get('mime_type', 'image/jpeg')
        if not mime:
            mime = 'image/jpeg'
        return Response(content=row['file_data'], media_type=mime)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Обработка заявок из Mini App (кнопка связи с риелтором)
webapp_router = Router()

@webapp_router.message(F.web_app_data)
async def handle_web_app_data(message: types.Message):
    try:
        import json
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