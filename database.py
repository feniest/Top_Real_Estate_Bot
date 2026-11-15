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
    
def get_filtered_ads(category: str = "all", prop_type: str = "all", district: str = "all", rooms: str = "all"):
    """Получение активных квартир и домов по выбранным фильтрам"""
    conn = get_connection()
    cursor = conn.cursor()
    
    query = """
        SELECT ad_number, category, property_type, rooms, district, landmark, area, floor, floors_total, price 
        FROM ads 
        WHERE is_active = 1
    """
    params = []
    
    if category != "all":
        query += " AND category = %s"
        params.append(category)
        
    if prop_type != "all":
        query += " AND property_type = %s"
        params.append(prop_type)
        
    if district != "all":
        query += " AND district = %s"
        params.append(district)
        
    if rooms != "all":
        query += " AND rooms = %s"
        params.append(rooms)
        
    query += " ORDER BY ad_number::integer ASC, id DESC;"
    
    cursor.execute(query, tuple(params))
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return rows

def get_active_districts(category: str = "all", prop_type: str = "all"):
    """Список районов, где есть актуальные объекты под выбранные фильтры"""
    conn = get_connection()
    cursor = conn.cursor()
    
    query = "SELECT DISTINCT district FROM ads WHERE is_active = 1 AND district IS NOT NULL AND district != ''"
    params = []
    
    if category != "all":
        query += " AND category = %s"
        params.append(category)
    if prop_type != "all":
        query += " AND property_type = %s"
        params.append(prop_type)
        
    query += " ORDER BY district;"
    cursor.execute(query, tuple(params))
    districts = [row[0] for row in cursor.fetchall()]
    cursor.close()
    conn.close()
    return districts 