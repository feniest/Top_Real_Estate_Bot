import psycopg2
from psycopg2.extras import RealDictCursor

# Укажите ваши настройки подключения к базе данных
DB_CONFIG = {
    "dbname": "your_db",
    "user": "your_user",
    "password": "your_password",
    "host": "localhost",
    "port": "5432"
}

def get_connection():
    return psycopg2.connect(**DB_CONFIG)

def get_market_statistics():
    """Возвращает агрегированную статистику по категориям (Rent / Sales) для главного экрана"""
    conn = get_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cursor.execute("""
            SELECT 
                category,
                COUNT(*) as total_count,
                MIN(price) as min_price,
                ROUND(AVG(price), 0) as avg_price
            FROM ads
            GROUP BY category;
        """)
        rows = cursor.fetchall()
        stats = {}
        for row in rows:
            cat = row.get('category')
            stats[cat] = {
                "count": row.get('total_count', 0),
                "min_price": row.get('min_price', 0),
                "avg_price": row.get('avg_price', 0)
            }
        return stats
    except Exception as e:
        print(f"⚠️ Ошибка получения статистики рынка: {e}")
        return {}
    finally:
        cursor.close()
        conn.close()

def get_filtered_ads(category: str = None, prop_type: str = None):
    """Стандартная функция получения объявлений для конкретного раздела"""
    conn = get_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        query = "SELECT * FROM ads WHERE 1=1"
        params = []
        
        if category and category != 'all':
            query += " AND category = %s"
            params.append(category)
            
        if prop_type and prop_type != 'all':
            query += " AND property_type = %s"
            params.append(prop_type)
            
        cursor.execute(query, params)
        return cursor.fetchall()
    except Exception as e:
        print(f"⚠️ Ошибка фильтрации объявлений: {e}")
        return []
    finally:
        cursor.close()
        conn.close()