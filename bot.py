import asyncio
import logging
import sys
from aiogram import Bot, Dispatcher
from config import BOT_TOKEN
from handlers.catalog import router as catalog_router
from handlers.search import router as search_router

async def main():
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()
    
    # Подключаем роутеры (catalog_router первым, чтобы /start открывал новую витрину)
    dp.include_router(catalog_router)
    dp.include_router(search_router)
    
    print("🤖 Telegram-бот запущен и готов к работе с базой данных...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        print("Бот остановлен.")