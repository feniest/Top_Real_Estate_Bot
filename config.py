import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "9220852767:AAHsifZAM6M3vQE1Zq-mixaDjpKHgFO_DFg")

# Параметры вашей удаленной базы данных PostgreSQL
DB_CONFIG = {
    "host": "37.187.139.87",
    "port": 35919,
    "database": "fh7cba1949de20442fb8484660cc696208",
    "user": "postgres",
    "password": "7H6SEUopuXHTa9Hu9vpJ04onLYZ4"
}