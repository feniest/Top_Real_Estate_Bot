import os
import json
import asyncio
import logging
import sys
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
import uvicorn
from aiogram import Bot, Dispatcher, types, F, Router

# 1. Инициализация FastAPI
app = FastAPI()

# Подключаем папку webapp со статическими файлами (картинки, стили, скрипты)
app.mount("/static", StaticFiles(directory="webapp"), name="static")

# Отдаем файл index.html при открытии главного адреса или мини-приложения
@app.get("/")
def serve_webapp():
    return FileResponse("webapp/index.html")

# 2. Настройка бота и роутера для приема заявок
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


async def main():
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not bot_token:
        raise ValueError("Не найден TELEGRAM_BOT_TOKEN в переменных окружения!")

    bot = Bot(token=bot_token)
    dp = Dispatcher()
    dp.include_router(router)

    # Запускаем телеграм-бота в фоновом режиме
    asyncio.create_task(dp.start_polling(bot))
    print("Telegram бот запущен в фоновом режиме...")

    # Запускаем веб-сервер FastAPI на порту хостинга
    port = int(os.getenv("PORT", 8080))
    config = uvicorn.Config(app, host="0.0.0.0", port=port, log_level="info")
    server = uvicorn.Server(config)
    
    await server.serve()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    asyncio.run(main())