"""ขั้นที่ 3 (optional): export ข้อมูลจาก SQLite เป็น CSV + JSON

รัน:
  python export.py
ได้ไฟล์ใน data/: foods.csv, nutrients.csv, foodcheck.json
"""
import csv
import json

from config import DATA_DIR
from db import get_conn


def export_csv(conn) -> None:
    foods = conn.execute("SELECT * FROM food ORDER BY food_code").fetchall()
    with open(DATA_DIR / "foods.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(foods[0].keys() if foods else [])
        for r in foods:
            w.writerow(list(r))

    nutr = conn.execute(
        "SELECT * FROM nutrient ORDER BY food_id, nutrient_name"
    ).fetchall()
    with open(DATA_DIR / "nutrients.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(nutr[0].keys() if nutr else [])
        for r in nutr:
            w.writerow(list(r))
    print(f"เขียน foods.csv ({len(foods)}) + nutrients.csv ({len(nutr)})")


def export_json(conn) -> None:
    """รวมเป็นโครงสร้างซ้อน: อาหาร -> nutrients[]"""
    foods = conn.execute("SELECT * FROM food ORDER BY food_code").fetchall()
    out = []
    for f in foods:
        d = dict(f)
        d["nutrients"] = [
            dict(n) for n in conn.execute(
                "SELECT nutrient_name, unit, per_100g, deriv_by, n, "
                "min_val, max_val, sd, footnote, last_updated "
                "FROM nutrient WHERE food_id=? ORDER BY nutrient_name",
                (f["id"],),
            ).fetchall()
        ]
        out.append(d)
    with open(DATA_DIR / "foodcheck.json", "w", encoding="utf-8") as fh:
        json.dump({
            "source": "Thai Food Composition Database, INMU Mahidol University",
            "source_url": "https://inmu.mahidol.ac.th/thaifcd/",
            "note": "For personal / non-commercial use. Cite INMU.",
            "count": len(out),
            "foods": out,
        }, fh, ensure_ascii=False, indent=2)
    print(f"เขียน foodcheck.json ({len(out)} อาหาร)")


def main() -> None:
    conn = get_conn()
    export_csv(conn)
    export_json(conn)
    conn.close()


if __name__ == "__main__":
    main()
