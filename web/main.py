"""FoodCheck Web App — FastAPI backend
อ่าน SQLite foodcheck.sqlite ตอบ API + serve HTML pages
"""
from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, Query, HTTPException, Header
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
import sqlite3

from web.nutrition_sanity import run_nutrition_sanity_check

ROOT_DIR = Path(__file__).parent.parent
DEFAULT_DB_PATH = ROOT_DIR / "data" / "foodcheck.sqlite"
LEGACY_DB_PATH = ROOT_DIR / "data" / "thaifcd.sqlite"
DB_PATH = Path(os.getenv("DATABASE_PATH", DEFAULT_DB_PATH))
if not DB_PATH.exists() and LEGACY_DB_PATH.exists():
    DB_PATH = LEGACY_DB_PATH

STATIC_DIR = Path(__file__).parent / "static"
TEMPLATES_DIR = Path(__file__).parent / "templates"

app = FastAPI(title="FoodCheck API", docs_url=None, redoc_url=None)

# Static files
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def is_admin_debug_enabled(admin_token: str = "", x_admin_token: str = "") -> bool:
    expected = os.getenv("FOODCHECK_ADMIN_TOKEN", "")
    if not expected:
        return False
    return admin_token == expected or x_admin_token == expected


# ─────────────────────────────────────────────
# API endpoints
# ─────────────────────────────────────────────

@app.get("/api/search")
def search(q: str = Query("", min_length=0), group: str = Query("")) -> dict:
    """ค้นหาอาหาร — ส่ง q=... (ชื่อไทย/อังกฤษ) และ/หรือ group=A"""
    if len(q.strip()) < 2 and not group:
        return {"results": [], "total": 0}

    conn = get_db()
    params: list = []
    where_parts: list[str] = []

    if q.strip():
        like = f"%{q.strip()}%"
        where_parts.append("(f.name_th LIKE ? OR f.name_en LIKE ? OR f.food_code LIKE ?)")
        params += [like, like, like]

    if group:
        where_parts.append("f.status = ?")
        params.append(group.upper())

    where = " AND ".join(where_parts) if where_parts else "1=1"

    rows = conn.execute(
        f"""SELECT f.id, f.food_code, f.name_th, f.name_en, f.status,
                   fg.name_en AS group_name,
                   (SELECT per_100g FROM nutrient WHERE food_id=f.id AND nutrient_name='Energy, by calculation') AS energy,
                   (SELECT per_100g FROM nutrient WHERE food_id=f.id AND nutrient_name='Protein, total') AS protein,
                   (SELECT per_100g FROM nutrient WHERE food_id=f.id AND nutrient_name='Phosphorus') AS phosphorus,
                   (SELECT per_100g FROM nutrient WHERE food_id=f.id AND nutrient_name='Potassium') AS potassium,
                   (SELECT per_100g FROM nutrient WHERE food_id=f.id AND nutrient_name='Sodium') AS sodium
            FROM food f
            LEFT JOIN food_group fg ON f.status = fg.status
            WHERE {where}
            ORDER BY f.name_th
            LIMIT 30""",
        params,
    ).fetchall()
    conn.close()

    return {
        "results": [dict(r) for r in rows],
        "total": len(rows),
    }


@app.get("/api/food/{food_id}")
def food_detail(
    food_id: int,
    admin_token: str = Query(""),
    x_admin_token: str = Header("", alias="X-Admin-Token"),
) -> dict:
    """ดึง nutrient ครบ 40 ตัวของอาหารชิ้นนั้น"""
    conn = get_db()
    food = conn.execute(
        """SELECT f.*, fg.name_en AS group_name
           FROM food f LEFT JOIN food_group fg ON f.status = fg.status
           WHERE f.id = ?""",
        (food_id,),
    ).fetchone()
    if not food:
        conn.close()
        raise HTTPException(status_code=404, detail="ไม่พบรายการอาหาร")

    nutrients = conn.execute(
        "SELECT nutrient_name, unit, per_100g FROM nutrient WHERE food_id = ? ORDER BY rowid",
        (food_id,),
    ).fetchall()
    conn.close()

    food_dict = dict(food)
    nutrient_list = [dict(n) for n in nutrients]
    sanity_check = run_nutrition_sanity_check(
        food_dict,
        nutrient_list,
        include_debug=is_admin_debug_enabled(admin_token, x_admin_token),
    )

    return {
        "food": food_dict,
        "nutrients": nutrient_list,
        "sanity_check": sanity_check,
    }


@app.get("/api/compare")
def compare(ids: str = Query(..., description="food ids คั่นด้วยจุลภาค เช่น 129,130,131")) -> dict:
    """เปรียบเทียบอาหาร 2-4 รายการ"""
    id_list = [int(x.strip()) for x in ids.split(",") if x.strip().isdigit()][:4]
    if len(id_list) < 2:
        raise HTTPException(status_code=400, detail="ต้องการ id อย่างน้อย 2 ตัว")

    conn = get_db()
    foods = []
    for fid in id_list:
        food = conn.execute(
            """SELECT f.*, fg.name_en AS group_name
               FROM food f LEFT JOIN food_group fg ON f.status = fg.status
               WHERE f.id=?""",
            (fid,),
        ).fetchone()
        if food:
            nutrients = conn.execute(
                "SELECT nutrient_name, unit, per_100g FROM nutrient WHERE food_id=? ORDER BY rowid",
                (fid,),
            ).fetchall()
            food_dict = dict(food)
            nutrient_list = [dict(n) for n in nutrients]
            foods.append(
                {
                    "food": food_dict,
                    "nutrients": nutrient_list,
                    "sanity_check": run_nutrition_sanity_check(food_dict, nutrient_list),
                }
            )
    conn.close()
    return {"items": foods}


@app.get("/api/groups")
def groups() -> dict:
    """รายชื่อกลุ่มอาหารทั้งหมด"""
    conn = get_db()
    rows = conn.execute("SELECT status, name_en FROM food_group ORDER BY status").fetchall()
    conn.close()
    return {"groups": [dict(r) for r in rows]}


# ─────────────────────────────────────────────
# HTML pages
# ─────────────────────────────────────────────

def read_template(name: str) -> str:
    return (TEMPLATES_DIR / name).read_text(encoding="utf-8")


@app.get("/", response_class=HTMLResponse)
def index():
    return read_template("index.html")


@app.get("/food/{food_id}", response_class=HTMLResponse)
def food_page(food_id: int):
    return read_template("detail.html")


@app.get("/compare", response_class=HTMLResponse)
def compare_page():
    return read_template("compare.html")
