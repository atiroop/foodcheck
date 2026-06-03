"""ขั้นที่ 2: ดึง Nutrition Facts ทีละอาหาร

อ่าน id ที่ยังไม่ดึง (nutrient_fetched = 0) จากตาราง food
ยิง endpoint food_name parse ตาราง nutrient เก็บลงตาราง nutrient
อัปเดต flag กัน resume ซ้ำ

รัน:
  python fetch_nutrients.py            # ดึงทุกตัวที่ยังค้าง
  python fetch_nutrients.py --limit 20 # ทดสอบแค่ 20 ตัวแรก
  python fetch_nutrients.py --retry    # รวม id ที่เคย error (-1) ด้วย
"""
import argparse
import datetime as dt

from bs4 import BeautifulSoup

import fetcher
from config import BASE_URL, FOOD_NAME_URL
from db import get_conn, init_db

# Version 3: nutrient detail โหลดผ่าน AJAX endpoint นี้
NUTRIENT_RESULT_URL = BASE_URL + "/foodsearch/food_name_result"


def parse_nutrients(html: str) -> list[dict]:
    """parse ตาราง Nutrient จากหน้า food_name."""
    soup = BeautifulSoup(html, "lxml")
    rows: list[dict] = []

    # หาตารางที่มีหัวคอลัมน์ Per 100 g / Deriv.By
    target = None
    for table in soup.find_all("table"):
        head = table.get_text(" ", strip=True)
        if "Per 100" in head and "Deriv" in head:
            target = table
            break
    if target is None:
        return rows

    for tr in target.find_all("tr"):
        tds = [td.get_text(strip=True) for td in tr.find_all("td")]
        if len(tds) < 4:
            continue
        # คอลัมน์: Nutrient | Unit | Per100g | Deriv.By | n | Min | Max | SD | Footnote | LastUpdated
        def g(i):
            return tds[i] if i < len(tds) else None
        name = g(0)
        if not name:
            continue
        rows.append({
            "nutrient_name": name,
            "unit": g(1),
            "per_100g": g(2),
            "deriv_by": g(3),
            "n": g(4),
            "min_val": g(5),
            "max_val": g(6),
            "sd": g(7),
            "footnote": g(8),
            "last_updated": g(9),
        })
    return rows


def fetch_one(food: dict) -> list[dict]:
    # Version 3: ต้องส่ง selected_id / selected_dbcode ไปที่ food_name_result
    params = {
        "order_fields": "",
        "order_directions": "",
        "page_no": 1,
        "dummy_page_no": 1,
        "status": food["status"],
        "selected_name": food["name_en"] or "",
        "selected_id": food["id"],
        "selected_dbcode": food["dbcode"] or "STD",
        "food_group_id": food["food_group_id"],
        "food_name": food["name_en"] or "",
        "mode": "food_group_result",
    }
    html = fetcher.get(NUTRIENT_RESULT_URL, params=params)
    return parse_nutrients(html)


def save_nutrients(conn, food_id: int, rows: list[dict]) -> None:
    conn.execute("DELETE FROM nutrient WHERE food_id = ?", (food_id,))
    for r in rows:
        r["food_id"] = food_id
        conn.execute(
            """INSERT INTO nutrient(food_id, nutrient_name, unit, per_100g,
                   deriv_by, n, min_val, max_val, sd, footnote, last_updated)
               VALUES(:food_id,:nutrient_name,:unit,:per_100g,
                   :deriv_by,:n,:min_val,:max_val,:sd,:footnote,:last_updated)
               ON CONFLICT(food_id, nutrient_name) DO UPDATE SET
                   unit=excluded.unit, per_100g=excluded.per_100g,
                   deriv_by=excluded.deriv_by, n=excluded.n,
                   min_val=excluded.min_val, max_val=excluded.max_val,
                   sd=excluded.sd, footnote=excluded.footnote,
                   last_updated=excluded.last_updated""",
            r,
        )


def main(limit: int | None, include_retry: bool) -> None:
    init_db()
    conn = get_conn()

    where = "nutrient_fetched = 0"
    if include_retry:
        where = "nutrient_fetched IN (0, -1)"
    sql = f"SELECT * FROM food WHERE {where} ORDER BY id"
    if limit:
        sql += f" LIMIT {int(limit)}"
    pending = conn.execute(sql).fetchall()

    total = len(pending)
    print(f"มี {total} รายการที่ต้องดึง\n")
    ok = err = 0

    for i, row in enumerate(pending, 1):
        food = dict(row)
        tag = f"[{i}/{total}] {food['food_code']} {food['name_en']}"
        try:
            rows = fetch_one(food)
            if not rows:
                raise ValueError("ไม่พบตาราง nutrient ใน response")
            save_nutrients(conn, food["id"], rows)
            conn.execute(
                "UPDATE food SET nutrient_fetched=1, fetched_at=? WHERE id=?",
                (dt.datetime.now().isoformat(timespec="seconds"), food["id"]),
            )
            conn.commit()
            ok += 1
            print(f"{tag} -> {len(rows)} สารอาหาร")
        except Exception as e:  # noqa: BLE001
            conn.execute(
                "UPDATE food SET nutrient_fetched=-1 WHERE id=?", (food["id"],)
            )
            conn.commit()
            err += 1
            print(f"{tag} -> ERROR: {e}")

    conn.close()
    print(f"\nเสร็จ. สำเร็จ {ok} | error {err} | เหลือค้างให้รันซ้ำได้ทีหลัง")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--retry", action="store_true",
                    help="ดึง id ที่เคย error (-1) ซ้ำด้วย")
    args = ap.parse_args()
    main(args.limit, args.retry)
