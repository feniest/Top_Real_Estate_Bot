import psycopg2
import psycopg2.extras
from config import DB_CONFIG, DATABASE_URL

def get_connection():
    if DATABASE_URL:
        # cursor_factory=RealDictCursor заставляет БД отдавать словари вместо кортежей
        return psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
    return psycopg2.connect(**DB_CONFIG, cursor_factory=psycopg2.extras.RealDictCursor)

def get_filtered_ads(category: str = "all", prop_type: str = "all", district: str = "all", rooms: str = "all"):
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
    rows = cursor.fetchall()  # Теперь это список словарей (благодаря RealDictCursor)
    cursor.close()
    conn.close()
    return rows

def get_ad_media_files(ad_number: str):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT file_name, file_data, mime_type FROM ad_media WHERE ad_number = %s ORDER BY id ASC", (str(ad_number),))
    files = cursor.fetchall()
    cursor.close()
    conn.close()
    return files

def get_active_districts(category: str = "all", prop_type: str = "all"):
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
    districts = [row['district'] for row in cursor.fetchall() if 'district' in row]
    cursor.close()
    conn.close()
    return districts