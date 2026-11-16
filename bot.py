import os
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
import database as db

app = FastAPI()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Подключаем папку webapp для раздачи статических файлов (картинок, стилей, скриптов)
if os.path.exists(os.path.join(BASE_DIR, "webapp")):
    app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "webapp")), name="static")

@app.get("/api/stats")
def api_get_stats():
    """Эндпоинт для получения легкой статистики рынка"""
    try:
        return db.get_market_statistics()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/ads")
def api_get_ads(category: str = "Rent", prop_type: str = "all"):
    """Эндпоинт выдачи карточек при переходе в конкретный раздел"""
    try:
        return db.get_filtered_ads(category=category, prop_type=prop_type)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/", response_class=HTMLResponse)
def serve_index():
    # Читаем index.html строго из папки webapp
    index_path = os.path.join(BASE_DIR, "webapp", "index.html")
    if not os.path.exists(index_path):
        raise HTTPException(status_code=404, detail="Файл webapp/index.html не найден")
    
    with open(index_path, "r", encoding="utf-8") as f:
        return f.read()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)