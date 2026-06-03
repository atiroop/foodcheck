"""ขั้นที่ 1: ดึง master list ของอาหารทุกกลุ่ม

ยิง endpoint food_group_result ทีละกลุ่ม (status A..Z) วน pagination จนหมด
parse <a href> เพื่อดึง internal id + food_group_id + ชื่อ + รหัส
เก็บลงตาราง food และ food_group

รันครั้งเดียวก็พอ ถ้ารันซ้ำจะ upsert ทับของเดิม (ไม่ลบ nutrient ที่ดึงไว้แล้ว)
"""
import re
import sys
from urllib.parse import urlparse, parse_qs, unquote

from bs4 import BeautifulSoup

import fetcher
from config import GROUP_LIST_URL, FOOD_GROUPS, FOOD_GROUP_IDS
from db import get_conn, init_db


def parse_food_id(href: str) -> dict | None:
    """ดึง id, food_group_id, dbcode, name จาก href ของลิงก์อาหาร."""
    qs = parse_qs(urlparse(href).query)
    if "id" not in qs:
        return None
    return {
        "id": int(qs["id"][0]),
        "food_group_id": int(qs.get("food_group_id", [0])[0]),
        "dbcode": qs.get("dbcode", ["STD"])[0],
        "name_en_href": unquote(qs.get("name", [""])[0]),
    }


def parse_rows(html: str, status: str) -> tuple[list[dict], int]:
    """parse ตารางผลลัพธ์ คืน (list ของ food, จำนวนแถวที่เจอ)."""
    soup = BeautifulSoup(html, "lxml")
    foods: dict[int, dict] = {}

    for tr in soup.select("tr"):
        link = tr.find("a", href=re.compile(r"food_name"))
        if not link:
            continue
        meta = parse_food_id(link.get("href", ""))
        if not meta:
            continue

        tds = tr.find_all("td")
        # โครงสร้าง: No. | Thai Name | English Name | Scientific Name | Food Code
        name_th = tds[1].get_text(strip=True) if len(tds) > 1 else None
        name_en = tds[2].get_text(strip=True) if len(tds) > 2 else None
        sci = tds[3].get_text(strip=True) if len(tds) > 3 else None
        code = tds[4].get_text(strip=True) if len(tds) > 4 else None
        if sci == "-":
            sci = None

        fid = meta["id"]
        foods[fid] = {
            "id": fid,
            "food_code": code,
            "status": status,
            "food_group_id": meta["food_group_id"],
            "name_th": name_th,
            "name_en": name_en or meta["name_en_href"],
            "scientific_name": sci,
            "dbcode": meta["dbcode"],
        }

    return list(foods.values()), len(foods)


def fetch_group(status: str) -> list[dict]:
    """ดึงทุกหน้าของกลุ่มหนึ่ง คืน list ของ food."""
    all_foods: dict[int, dict] = {}
    fg_id = FOOD_GROUP_IDS[status]
    page = 1
    while True:
        params = {
            "food_group_id": fg_id,
            "mode": "food_group_result",
            "page_no": page,
        }
        html = fetcher.get(GROUP_LIST_URL, params=params)
        foods, n = parse_rows(html, status)
        new = {f["id"]: f for f in foods if f["id"] not in all_foods}
        all_foods.update(new)

        print(f"  [{status}] page {page}: เจอ {n} แถว (ใหม่ {len(new)})")
        # หยุดเมื่อหน้านี้ไม่มีของใหม่เลย หรือไม่มีแถว
        if n == 0 or len(new) == 0:
            break
        page += 1
        if page > 100:  # safety guard
            print(f"  ! [{status}] เกิน 100 หน้า หยุดกันลูปค้าง")
            break

    return list(all_foods.values())


def upsert_group(conn, status: str, food_group_id: int) -> None:
    conn.execute(
        "INSERT INTO food_group(status, food_group_id, name_en) VALUES (?,?,?) "
        "ON CONFLICT(status) DO UPDATE SET food_group_id=excluded.food_group_id, "
        "name_en=excluded.name_en",
        (status, food_group_id, FOOD_GROUPS[status]),
    )


def upsert_foods(conn, foods: list[dict]) -> None:
    for f in foods:
        conn.execute(
            """INSERT INTO food(id, food_code, status, food_group_id,
                   name_th, name_en, scientific_name, dbcode)
               VALUES (:id,:food_code,:status,:food_group_id,
                   :name_th,:name_en,:scientific_name,:dbcode)
               ON CONFLICT(id) DO UPDATE SET
                   food_code=excluded.food_code,
                   name_th=excluded.name_th,
                   name_en=excluded.name_en,
                   scientific_name=excluded.scientific_name""",
            f,
        )


def main(only: str | None = None) -> None:
    init_db()
    conn = get_conn()
    targets = [only] if only else list(FOOD_GROUPS.keys())

    grand_total = 0
    for status in targets:
        if status not in FOOD_GROUPS:
            print(f"ข้าม '{status}' (ไม่ใช่รหัสกลุ่มที่รู้จัก)")
            continue
        print(f"== กลุ่ม {status}: {FOOD_GROUPS[status]} ==")
        foods = fetch_group(status)
        fg_id = foods[0]["food_group_id"] if foods else 0
        upsert_group(conn, status, fg_id)
        upsert_foods(conn, foods)
        conn.commit()
        grand_total += len(foods)
        print(f"  -> เก็บ {len(foods)} รายการ (food_group_id={fg_id})\n")

    total = conn.execute("SELECT COUNT(*) FROM food").fetchone()[0]
    conn.close()
    print(f"เสร็จ. รอบนี้ {grand_total} รายการ | รวมใน DB ทั้งหมด {total} รายการ")


if __name__ == "__main__":
    # ใช้ python build_food_list.py [STATUS]  เช่น A เพื่อทดสอบทีละกลุ่ม
    arg = sys.argv[1].upper() if len(sys.argv) > 1 else None
    main(arg)
