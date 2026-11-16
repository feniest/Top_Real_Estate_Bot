import os
from dotenv import load_dotenv

load_dotenv()

# Токены бота (поддерживаем разные варианты названий из логов)
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN") or os.getenv("BOT_TOKEN") or os.getenv("TELEGRAM_TOKEN") or "9220852767:AAHsifZAM6M3vQE1Zq-mixaDjpKHgFO_DFg"

# ID риелтора / администратора (обязательно для заявок из Mini App)
REALTOR_ID = int(os.getenv("REALTOR_ID") or os.getenv("ADMIN_ID", "0"))

# Параметры базы данных PostgreSQL
DATABASE_URL = os.getenv("DATABASE_URL")
DB_CONFIG = {
    "host": os.getenv("DB_HOST", "37.187.139.87"),
    "port": int(os.getenv("DB_PORT", 35919)),
    "database": os.getenv("DB_NAME", "fh7cba1949de20442fb8484660cc696208"),
    "user": os.getenv("DB_USER", "postgres"),
    "password": os.getenv("DB_PASSWORD", "7H6SEUopuXHTa9Hu9vpJ04onLYZ4")
}