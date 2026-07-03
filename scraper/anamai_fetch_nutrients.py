"""ขั้นที่ 2 (กรมอนามัย): ดึง Nutrition Facts ทีละอาหารจาก view.php

อ่าน fid ที่ยังไม่ดึง (nutrient_fetched = 0) จากตาราง anamai_food
parse ตาราง #view-table แบ่งตาม category header (Main nutrients / Minerals / Vitamins / ...)
เก็บลงตาราง anamai_nutrient แล้วอัปเดต flag กัน resume ซ้ำ

รัน:
  python anamai_fetch_nutrients.py            # ดึงทุกตัวที่ยังค้าง
  python anamai_fetch_nutrients.py --limit 20 # ทดสอบแค่ 20 ตัวแรก
  python anamai_fetch_nutrients.py --retry    # รวม fid ที่เคย error (-1) ด้วย
"""
import argparse
import datetime as dt

from bs4 import BeautifulSoup

import fetcher
from db import get_conn, init_db

ANAMAI_VIEW_URL = "https://thaifcd.anamai.moph.go.th/nss/view.php"
# 'Branded Food Products' (fid ขึ้นต้นด้วย 'R') ใช้ endpoint นี้แทน — โครงสร้าง
# ตาราง #view-table เหมือนกัน แค่ไม่มี category header
ANAMAI_VIEW_BRANDED_URL = "https://thaifcd.anamai.moph.go.th/nss/view_branded.php"


def parse_nutrients(html: str) -> list[dict]:
    """parse ตาราง #view-table เป็น list ของ {category, nutrient_name, amount, unit}."""
    soup = BeautifulSoup(html, "lxml")
    table = soup.find("table", id="view-table")
    if table is None:
        return []

    rows: list[dict] = []
    category = None
    for tr in table.find_all("tr"):
        tds = tr.find_all("td")
        # แถวหัวหมวด: <td colspan="3">Main nutrients</td>
        if len(tds) == 1 and tds[0].get("colspan"):
            category = tds[0].get_text(strip=True)
            continue
        if len(tds) < 3:
            continue

        name = tds[0].get_text(strip=True)
        if not name:
            continue
        amount_text = tds[1].get_text(strip=True)
        unit = tds[2].get_text(strip=True)
        try:
            amount = float(amount_text.replace(",", ""))
        except ValueError:
            amount = None

        rows.append({
            "category": category,
            "nutrient_name": name,
            "amount": amount,
            "unit": unit,
        })
    return rows


def fetch_one(fid: str) -> list[dict]:
    url = ANAMAI_VIEW_BRANDED_URL if fid.startswith("R") else ANAMAI_VIEW_URL
    html = fetcher.get(url, params={"fID": fid})
    return parse_nutrients(html)


def save_nutrients(conn, fid: str, rows: list[dict]) -> None:
    conn.execute("DELETE FROM anamai_nutrient WHERE fid = ?", (fid,))
    for r in rows:
        r["fid"] = fid
        conn.execute(
            """INSERT INTO anamai_nutrient(fid, category, nutrient_name, amount, unit)
               VALUES (:fid,:category,:nutrient_name,:amount,:unit)
               ON CONFLICT(fid, nutrient_name) DO UPDATE SET
                   category=excluded.category,
                   amount=excluded.amount,
                   unit=excluded.unit""",
            r,
        )


def main(limit: int | None, include_retry: bool) -> None:
    init_db()
    conn = get_conn()

    where = "nutrient_fetched = 0"
    if include_retry:
        where = "nutrient_fetched IN (0, -1)"
    sql = f"SELECT * FROM anamai_food WHERE {where} ORDER BY fid"
    if limit:
        sql += f" LIMIT {int(limit)}"
    pending = conn.execute(sql).fetchall()

    total = len(pending)
    print(f"มี {total} รายการที่ต้องดึง\n")
    ok = err = 0

    for i, row in enumerate(pending, 1):
        food = dict(row)
        tag = f"[{i}/{total}] {food['fid']} {food['name_en'] or food['name_th']}"
        try:
            rows = fetch_one(food["fid"])
            if not rows:
                raise ValueError("ไม่พบตาราง nutrient ใน response")
            save_nutrients(conn, food["fid"], rows)
            conn.execute(
                "UPDATE anamai_food SET nutrient_fetched=1, fetched_at=? WHERE fid=?",
                (dt.datetime.now().isoformat(timespec="seconds"), food["fid"]),
            )
            conn.commit()
            ok += 1
            print(f"{tag} -> {len(rows)} สารอาหาร")
        except Exception as e:  # noqa: BLE001
            conn.execute(
                "UPDATE anamai_food SET nutrient_fetched=-1 WHERE fid=?", (food["fid"],)
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
                     help="ดึง fid ที่เคย error (-1) ซ้ำด้วย")
    args = ap.parse_args()
    main(args.limit, args.retry)
