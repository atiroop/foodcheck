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

from web.unit_conversion import get_unit_conversions
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


def parse_food_id(food_id: str) -> tuple[str, str]:
    """แยก food_id เป็น (source, raw_id) — id เปล่า (เช่น '129') ถือเป็น INMU เสมอ
    เพื่อไม่ให้ลิงก์เดิมที่แจกไปแล้วพัง"""
    if ":" in food_id:
        source, raw = food_id.split(":", 1)
        if source in ("thaifcd_inmu", "thaifcd_anamai"):
            return source, raw
    return "thaifcd_inmu", food_id


# ─────────────────────────────────────────────
# API endpoints
# ─────────────────────────────────────────────

@app.get("/api/search")
def search(
    q: str = Query("", min_length=0),
    group: str = Query(""),
    source: str = Query("", description="จำกัดแหล่งข้อมูล: 'thaifcd_inmu' | 'thaifcd_anamai' (ว่าง = ทั้งสองแหล่ง)"),
) -> dict:
    """ค้นหาอาหาร — ส่ง q=... (ชื่อไทย/อังกฤษ) และ/หรือ group=A (กรองด้วย group รองรับเฉพาะ INMU)"""
    if len(q.strip()) < 2 and not group:
        return {"results": [], "total": 0}

    conn = get_db()
    results: list[dict] = []

    if source != "thaifcd_anamai":
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
            f"""SELECT f.id, f.food_code, f.name_th, f.name_en, f.status, f.source,
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
        results += [dict(r) for r in rows]

    # anamai ไม่มี taxonomy กลุ่มอาหาร A-Z แบบ INMU จึงข้ามเมื่อกรองด้วย group
    if source != "thaifcd_inmu" and not group and q.strip():
        like = f"%{q.strip()}%"
        rows = conn.execute(
            """SELECT af.fid, af.fid AS food_code, af.name_th, af.name_en,
                      af.food_type AS status, 'thaifcd_anamai' AS source,
                      af.food_group_th AS group_name,
                      (SELECT value_per_100g FROM v_pd_nutrient
                        WHERE food_uid='thaifcd_anamai:'||af.fid AND nutrient_name='Energy, by calculation') AS energy,
                      (SELECT value_per_100g FROM v_pd_nutrient
                        WHERE food_uid='thaifcd_anamai:'||af.fid AND nutrient_name='Protein, total') AS protein,
                      (SELECT value_per_100g FROM v_pd_nutrient
                        WHERE food_uid='thaifcd_anamai:'||af.fid AND nutrient_name='Phosphorus') AS phosphorus,
                      (SELECT value_per_100g FROM v_pd_nutrient
                        WHERE food_uid='thaifcd_anamai:'||af.fid AND nutrient_name='Potassium') AS potassium,
                      (SELECT value_per_100g FROM v_pd_nutrient
                        WHERE food_uid='thaifcd_anamai:'||af.fid AND nutrient_name='Sodium') AS sodium
               FROM anamai_food af
               WHERE af.name_th LIKE ? OR af.name_en LIKE ? OR af.fid LIKE ?
               ORDER BY af.name_th
               LIMIT 30""",
            [like, like, like],
        ).fetchall()
        for r in rows:
            d = dict(r)
            d["id"] = "thaifcd_anamai:" + d.pop("fid")
            results.append(d)

    conn.close()
    results.sort(key=lambda r: r.get("name_th") or r.get("name_en") or "")
    results = results[:40]

    return {"results": results, "total": len(results)}


@app.get("/api/food/{food_id}")
def food_detail(
    food_id: str,
    admin_token: str = Query(""),
    x_admin_token: str = Header("", alias="X-Admin-Token"),
) -> dict:
    """ดึง nutrient ของอาหารชิ้นนั้น — รองรับทั้ง INMU (id ตัวเลข) และ
    กรมอนามัย (id นำหน้าด้วย 'thaifcd_anamai:')"""
    source, raw_id = parse_food_id(food_id)
    conn = get_db()

    if source == "thaifcd_anamai":
        food = conn.execute(
            "SELECT * FROM anamai_food WHERE fid = ?", (raw_id,)
        ).fetchone()
        if not food:
            conn.close()
            raise HTTPException(status_code=404, detail="ไม่พบรายการอาหาร")

        rows = conn.execute(
            """SELECT an.nutrient_name AS raw_name, an.unit, an.amount, map.canonical_name
               FROM anamai_nutrient an
               LEFT JOIN nutrient_name_map map
                      ON map.source = 'thaifcd_anamai' AND map.source_name = an.nutrient_name
               WHERE an.fid = ?
               ORDER BY an.rowid""",
            (raw_id,),
        ).fetchall()
        conn.close()

        food_dict = {
            "id": f"thaifcd_anamai:{food['fid']}",
            "food_code": food["fid"],
            "name_th": food["name_th"],
            "name_en": food["name_en"],
            "status": food["food_type"],
            "group_name": food["food_group_th"],
            "scientific_name": None,
            "source": "thaifcd_anamai",
        }
        nutrient_list = [
            {
                "nutrient_name": r["canonical_name"] or r["raw_name"],
                "unit": r["unit"],
                "per_100g": r["amount"],
            }
            for r in rows
        ]
        sanity_check = run_nutrition_sanity_check(
            food_dict,
            nutrient_list,
            include_debug=is_admin_debug_enabled(admin_token, x_admin_token),
        )
        return {
            "food": food_dict,
            "nutrients": nutrient_list,
            "sanity_check": sanity_check,
            "unit_conversions": get_unit_conversions(food_dict, nutrient_list),
        }

    try:
        inmu_id = int(raw_id)
    except ValueError:
        conn.close()
        raise HTTPException(status_code=404, detail="ไม่พบรายการอาหาร")

    food = conn.execute(
        """SELECT f.*, fg.name_en AS group_name
           FROM food f LEFT JOIN food_group fg ON f.status = fg.status
           WHERE f.id = ?""",
        (inmu_id,),
    ).fetchone()
    if not food:
        conn.close()
        raise HTTPException(status_code=404, detail="ไม่พบรายการอาหาร")

    nutrients = conn.execute(
        "SELECT nutrient_name, unit, per_100g FROM nutrient WHERE food_id = ? ORDER BY rowid",
        (inmu_id,),
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
        "unit_conversions": get_unit_conversions(food_dict, nutrient_list),
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
                    "unit_conversions": get_unit_conversions(food_dict, nutrient_list),
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
def food_page(food_id: str):
    return read_template("detail.html")


@app.get("/compare", response_class=HTMLResponse)
def compare_page():
    return read_template("compare.html")
