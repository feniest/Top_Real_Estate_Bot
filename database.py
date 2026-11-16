import os
import psycopg2
from psycopg2.extras import RealDictCursor

def get_connection():
    """Подключение к базе данных PostgreSQL"""
    return psycopg2.connect(
        dbname=os.getenv("DB_NAME", "postgres"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD", ""),
        host=os.getenv("DB_HOST", "localhost"),
        port=os.getenv("DB_PORT", "5432")
    )

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
                ROUND(AVG(price)::numeric, 0) as avg_price
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
        print(f"⚠️ Ошибка в get_market_statistics: {e}")
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
        print(f"⚠️ Ошибка в get_filtered_ads: {e}")
        return []
    finally:
        cursor.close()
        conn.close()