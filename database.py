def get_market_statistics(
    category: str = None,
    prop_type: str = None,
    rooms: str = None,
    district: str = None
):
    """Возвращает детальную статистику по категориям (Rent / Sale) с учетом фильтров"""
    conn = get_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        query = """
            SELECT 
                category,
                COUNT(*) as total_count,
                COUNT(*) FILTER (WHERE rooms = 1) as rooms_1,
                COUNT(*) FILTER (WHERE rooms = 2) as rooms_2,
                COUNT(*) FILTER (WHERE rooms = 3) as rooms_3,
                COUNT(*) FILTER (WHERE rooms = 4) as rooms_4,
                COUNT(*) FILTER (WHERE rooms >= 5) as rooms_5_plus,
                MIN(price) as min_price,
                MAX(price) as max_price,
                ROUND(AVG(price)::numeric, 0) as avg_price
            FROM ads
            WHERE 1=1
        """
        params = []

        if category and category != 'all':
            query += " AND category = %s"
            params.append(category)

        if prop_type and prop_type != 'all':
            query += " AND property_type = %s"
            params.append(prop_type)

        if rooms and rooms != 'all':
            if rooms == '5+':
                query += " AND rooms >= 5"
            else:
                query += " AND rooms = %s"
                params.append(int(rooms))

        if district and district != 'all':
            query += " AND district = %s"
            params.append(district)

        query += " GROUP BY category;"

        cursor.execute(query, params)
        rows = cursor.fetchall()
        stats = {}
        for row in rows:
            cat = row.get('category')
            stats[cat] = {
                "count": row.get('total_count', 0),
                "rooms_1": row.get('rooms_1', 0),
                "rooms_2": row.get('rooms_2', 0),
                "rooms_3": row.get('rooms_3', 0),
                "rooms_4": row.get('rooms_4', 0),
                "rooms_5_plus": row.get('rooms_5_plus', 0),
                "min_price": row.get('min_price', 0),
                "max_price": row.get('max_price', 0),
                "avg_price": row.get('avg_price', 0)
            }
        return stats
    except Exception as e:
        print(f"⚠️ Ошибка в get_market_statistics: {e}")
        return {}
    finally:
        cursor.close()
        conn.close()