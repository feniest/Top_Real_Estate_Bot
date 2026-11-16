from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
import database as db

app = FastAPI()

@app.get("/api/stats")
def api_get_stats():
    """Эндпоинт для получения легкой статистики рынка (кол-во, мин/средняя цена)"""
    try:
        stats = db.get_market_statistics()
        return stats
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/ads")
def api_get_ads(category: str = "Rent", prop_type: str = "all"):
    """Эндпоинт выдачи карточек при переходе в конкретный раздел"""
    try:
        ads = db.get_filtered_ads(category=category, prop_type=prop_type)
        return ads
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/", response_class=HTMLResponse)
def serve_index():
    with open("index.html", "r", encoding="utf-8") as f:
        return f.read()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)