"""ขั้นที่ 1 (กรมอนามัย): ดึง master list ทั้งหมดในการ GET ครั้งเดียว

ต่างจาก INMU ตรงที่ server คืน HTML ที่มีข้อมูลครบทุกแถว (1,484 รายการ) มาในทีเดียว
(ตาราง DataTables โหลด/แบ่งหน้าแบบ client-side ไม่มี pagination บน server)

parse <a href="view.php?fID=XXXXX"> เพื่อดึง fid (zero-padded 5 หลัก)
เก็บลงตาราง anamai_food

รันครั้งเดียวก็พอ ถ้ารันซ้ำจะ upsert ทับของเดิม (ไม่ลบ nutrient ที่ดึงไว้แล้ว)
"""
import re

from bs4 import BeautifulSoup

import fetcher
from db import get_conn, init_db

ANAMAI_SEARCH_URL = "https://thaifcd.anamai.moph.go.th/nss/search.php"

# แถวรายการ: "ชื่อไทย, รายละเอียด (English name)"
NAME_RE = re.compile(r"^(?P<th>.*?)\s*\((?P<en>[^()]*)\)\s*$")


def parse_name(text: str) -> tuple[str | None, str | None]:
    """แยกชื่อไทย/อังกฤษจาก 'ชื่อไทย (English name)'."""
    text = text.strip()
    m = NAME_RE.match(text)
    if m:
        return m.group("th").strip() or None, m.group("en").strip() or None
    return text or None, None


def parse_fid(href: str) -> str | None:
    m = re.search(r"fID=(\w+)", href)
    return m.group(1) if m else None


def parse_rows(html: str) -> list[dict]:
    """parse ตาราง DataTables ทุกแถว คืน list ของ anamai_food."""
    soup = BeautifulSoup(html, "lxml")
    table = soup.find("table", class_="mydatatable")
    if table is None:
        return []

    foods: dict[str, dict] = {}
    # 'Foundation Foods' ใช้ view.php, 'Branded Food Products' ใช้ view_branded.php
    for tr in table.find_all("tr"):
        link = tr.find("a", href=re.compile(r"view(?:_branded)?\.php\?fID="))
        if not link:
            continue
        fid = parse_fid(link.get("href", ""))
        if not fid:
            continue

        tds = tr.find_all("td")
        if len(tds) < 3:
            continue
        name_th, name_en = parse_name(tds[0].get_text(" ", strip=True))
        food_group_th = tds[1].get_text(strip=True) if len(tds) > 1 else None
        food_type = tds[2].get_text(strip=True) if len(tds) > 2 else None

        foods[fid] = {
            "fid": fid,
            "name_th": name_th,
            "name_en": name_en,
            "food_group_th": food_group_th,
            "food_group_en": None,  # ไม่มีในหน้า list ต้องเปิด detail ถึงจะเห็น
            "food_type": food_type,
        }

    return list(foods.values())


def upsert_foods(conn, foods: list[dict]) -> None:
    for f in foods:
        conn.execute(
            """INSERT INTO anamai_food(fid, name_th, name_en, food_group_th,
                   food_group_en, food_type)
               VALUES (:fid,:name_th,:name_en,:food_group_th,
                   :food_group_en,:food_type)
               ON CONFLICT(fid) DO UPDATE SET
                   name_th=excluded.name_th,
                   name_en=excluded.name_en,
                   food_group_th=excluded.food_group_th,
                   food_type=excluded.food_type""",
            f,
        )


def main() -> None:
    init_db()
    conn = get_conn()

    print("ดึง list ทั้งหมดจาก search.php ...")
    html = fetcher.get(
        ANAMAI_SEARCH_URL,
        params={
            "keyword": "",
            "nutrient": "00",
            "foodgroup": "00",
            "type": "00",
            "btn_search": "",
        },
    )
    foods = parse_rows(html)
    upsert_foods(conn, foods)
    conn.commit()

    total = conn.execute("SELECT COUNT(*) FROM anamai_food").fetchone()[0]
    conn.close()
    print(f"เก็บ {len(foods)} รายการ | รวมใน DB ทั้งหมด {total} รายการ")


if __name__ == "__main__":
    main()
