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
    """Возвращает агрегированную статистику по категориям (Аренда / Продажа)"""
    conn = db.get_connection() # Используйте вашу функцию подключения к БД
    cursor = conn.cursor()
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
            # Поддерживаем и словарь, и кортеж в зависимости от настроек курсора
            if isinstance(row, dict):
                cat = row.get('category')
                stats[cat] = {
                    "count": row.get('total_count', 0),
                    "min_price": row.get('min_price', 0),
                    "avg_price": row.get('avg_price', 0)
                }
            else:
                cat, count, min_p, avg_p = row
                stats[cat] = {
                    "count": count,
                    "min_price": min_p,
                    "avg_price": avg_p
                }
        return stats
    except Exception as e:
        print(f"⚠️ Ошибка получения статистики: {e}")
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