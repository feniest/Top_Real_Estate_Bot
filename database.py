import psycopg2
from config import DB_CONFIG

def get_connection():
    return psycopg2.connect(**DB_CONFIG)

def search_ads(district_query: str = ""):
    """Поиск активных объявлений по району или ориентиру"""
    conn = get_connection()
    cursor = conn.cursor()
    
    query = """
        SELECT ad_number, category, property_type, rooms, district, landmark, price, floor, floors_total 
        FROM ads 
        WHERE is_active = 1 
    """
    params = []
    
    if district_query:
        query += " AND (district ILIKE %s OR landmark ILIKE %s)"
        params.extend([f"%{district_query}%", f"%{district_query}%"])
        
    query += " ORDER BY id DESC LIMIT 10;"
    
    cursor.execute(query, tuple(params))
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return rows

def get_ad_media_files(ad_number: str):
    """Извлечение бинарных данных медиафайлов по номеру объявления"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT file_name, file_data FROM ad_media WHERE ad_number = %s", (ad_number,))
    files = cursor.fetchall()
    cursor.close()
    conn.close()
    return files