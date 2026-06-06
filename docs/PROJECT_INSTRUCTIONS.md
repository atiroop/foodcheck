# Project Instructions — foodcheck.jocky.website

## ภาพรวม

เครื่องมือส่วนตัวสำหรับเช็ค Nutrition Facts ของอาหารไทย ใช้ภายในครอบครัว
แรงจูงใจหลักคือดูค่าโภชนาการสำหรับ **ผู้ป่วยล้างไตทางช่องท้อง (Peritoneal Dialysis — PD)**
เช่น โปรตีน ฟอสฟอรัส โพแทสเซียม โซเดียม

- โดเมน: https://foodcheck.jocky.website
- ภาษาหลัก: Python 3.12+
- DB: SQLite (ไฟล์เดียว `data/foodcheck.sqlite`)
- ใช้ส่วนตัว / non-commercial เท่านั้น

---

## ⚠️ กฎที่ห้ามละเมิดเด็ดขาด

### 1. ลิขสิทธิ์ข้อมูล
- ข้อมูล Thai FCD เป็นของ **INMU Mahidol University** — ใช้ได้เฉพาะ non-commercial
- ต้องแสดง attribution INMU บนทุกหน้าที่แสดงผลโภชนาการเสมอ
- ข้อมูล USDA FoodData Central — Public Domain ใช้ได้ทุกอย่าง
- ห้ามลบ credit / source ออกจาก UI หรือ export ไฟล์

### 2. ความปลอดภัยด้านสุขภาพ
- ค่าโภชนาการทั้งหมดคือ **ค่าเฉลี่ยต่อ 100 กรัม** ไม่ใช่คำแนะนำเฉพาะบุคคล
- ห้าม UI หรือโค้ดตัดสินว่าอาหารใด "กินได้" หรือ "ห้ามกิน" สำหรับผู้ป่วย
- ทุกหน้าที่เกี่ยวกับผู้ป่วย PD ต้องมี disclaimer ให้ปรึกษานักโภชนาการ
- ห้ามใช้สีเขียว/แดงแบบ binary — ใช้การแสดงตัวเลขและหน่วยที่ชัดเจนแทน

### 3. มารยาทต่อ server ต้นทาง
- scraper ต้องหน่วงอย่างน้อย **1.5 วินาที** ต่อ request (ห้ามลดค่านี้)
- ใช้ flag `nutrient_fetched` ใน DB กันดึงซ้ำ — resume ได้เสมอ
- ห้ามตั้งชื่อไฟล์ทับ Python stdlib เช่น `http.py`, `json.py` (เคยพังมาแล้ว ใช้ `fetcher.py` แทน)

---

## โครงสร้างโปรเจกต์

```
foodcheck/
├── PROJECT_INSTRUCTIONS.md   # ไฟล์นี้
├── CLAUDE.md                 # สำหรับ Claude Code (ฉบับย่อ)
├── README.md
├── requirements.txt
├── .gitignore
│
├── scraper/                  # ดึงข้อมูล Thai FCD (รันครั้งเดียว)
│   ├── config.py             # endpoint, delay, รายชื่อกลุ่ม A–Z
│   ├── db.py                 # เปิด/สร้าง SQLite
│   ├── fetcher.py            # HTTP client + retry + หน่วง
│   ├── schema_complete.sql   # โครงสร้าง DB ทั้งหมด
│   ├── build_food_list.py    # ขั้น 1: ดึง master list (id ทุกตัว)
│   ├── fetch_nutrients.py    # ขั้น 2: ดึง nutrient ทีละตัว (resume ได้)
│   └── export.py             # ขั้น 3: export CSV/JSON (optional)
│
├── web/                      # เว็บแอป FastAPI ปัจจุบัน
│   ├── main.py               # FastAPI entry point
│   └── templates/            # HTML + Alpine.js
│
└── data/
    └── foodcheck.sqlite      # DB หลัก (gitignore)
```

---

## Database Schema (สรุป)

Schema เต็มอยู่ใน `scraper/schema_complete.sql` — อ่านก่อนแตะ DB เสมอ

### 9 ตาราง

| กลุ่ม | ตาราง | หน้าที่ |
|---|---|---|
| Thai FCD | `food_group`, `food`, `nutrient` | ข้อมูลหลัก scrape มาจาก INMU |
| USDA Fallback | `usda_food_mapping`, `usda_nutrient_cache` | cache ผล real-time API |
| Users | `user` | multi-user + PD profile เพดานรายคน |
| Recipe | `recipe`, `recipe_ingredient` | Recipe Builder |
| Config | `pd_nutrient` | 6 ตัว PD-critical ปรับได้ |

### 3 Views พร้อมใช้

```sql
v_food_nutrient       -- ค่าครบ พร้อม flag is_missing=1 ถ้าต้อง fallback USDA
v_pd_nutrient         -- 6 ตัว PD ของอาหาร รวม USDA fallback + บอก source
v_recipe_nutrition    -- คำนวณโภชนาการทั้ง recipe ตาม gram ที่กรอก
```

### Query ที่ใช้บ่อย

```sql
-- ค้นหาอาหาร
SELECT * FROM food WHERE name_th LIKE '%หมู%' OR name_en LIKE '%pork%';

-- 6 ตัว PD ของอาหาร id 42
SELECT * FROM v_pd_nutrient WHERE food_id = 42 ORDER BY sort_order;

-- ค่าที่ขาด (ควร fallback USDA)
SELECT * FROM v_pd_nutrient WHERE food_id = 42 AND value_per_100g IS NULL;

-- โภชนาการรวมของ recipe id 7
SELECT * FROM v_recipe_nutrition WHERE recipe_id = 7 ORDER BY sort_order;
```

---

## แหล่งข้อมูล

### Thai FCD (ข้อมูลหลัก — scrape ครั้งเดียว)

```
Base URL: https://inmu.mahidol.ac.th/thaifcd

Endpoint 1 — list ต่อกลุ่ม (XHR คืน HTML table):
GET /foodsearch/food_group_result
    ?status=A               # กลุ่ม A..Z
    &mode=food_group_result
    &page_no=1              # paginate จนหมด

Endpoint 2 — nutrient ต่ออาหาร:
GET /foodsearch/food_name/
    ?dbcode=STD
    &food_group_id=70       # internal id ของกลุ่ม (ดึงจาก href ใน list)
    &id=129                 # internal id ของอาหาร (เช่น A6 = 129)
    &name=Rice, brown, germinated, raw
```

กลุ่มอาหาร 17 กลุ่ม: A B C D E F G H J K M N Q S T U Z
(ไม่มี I L O P R — เว้นตามต้นทาง)

### USDA FoodData Central (fallback real-time)

```
API Key: เก็บใน environment variable USDA_API_KEY
Base URL: https://api.nal.usda.gov/fdc/v1

Search:
GET /foods/search?query=pork+neck&api_key={KEY}&dataType=Foundation,SR Legacy

Get nutrients:
GET /food/{fdc_id}?api_key={KEY}
```

**Trigger**: query USDA เมื่อ `v_pd_nutrient.value_per_100g IS NULL`
**Cache**: บันทึกผลลงตาราง `usda_nutrient_cache` ป้องกันยิงซ้ำ
**ความสำคัญ**: ใช้ fallback ได้เฉพาะ **วัตถุดิบเดี่ยว** (ingredient) เท่านั้น
ห้าม fallback USDA สำหรับเมนูสำเร็จ เพราะ recipe ต่างกัน

---

## 3 ระดับของ Features

### Level 1 — ค้นหาวัตถุดิบ (Ingredient Search)
- ค้นด้วยชื่อไทย/อังกฤษ/รหัส
- แสดงตาราง nutrient เต็ม + ไฮไลต์ 6 ตัว PD
- ถ้าค่า PD ขาด (`is_missing=1`) → query USDA real-time → cache → แสดง
- แสดง badge "Thai FCD" หรือ "USDA (fallback)" ให้ชัด

### Level 2 — Recipe Builder
- ผู้ใช้เลือก ingredient จาก food list + กรอกกรัม
- คำนวณโภชนาการรวมอัตโนมัติผ่าน `v_recipe_nutrition`
- บันทึก/แก้ไข/ลบ recipe ส่วนตัวได้
- แสดงผลต่อ serving + เทียบกับเพดาน PD ของผู้ใช้ (ถ้าตั้งไว้)
- รองรับหลาย user (แต่ละคน login ดู recipe ตัวเอง)

### Level 3 — เมนูสำเร็จ (Prepared Food)
- แสดงเฉพาะ item ใน Thai FCD ที่ `nutrient_fetched = 1`
- ค่าไหนขาด → แสดง "ไม่มีข้อมูล" ชัดเจน **ไม่ fallback USDA**
- เพราะเมนูสำเร็จคือ recipe ไม่ใช่ ingredient

---

## PD Mode — 6 ตัวที่ต้องไฮไลต์

| # | nutrient_name | ชื่อไทย | หน่วย | risk_direction |
|---|---|---|---|---|
| 1 | Energy, by calculation | พลังงาน | kcal | low (ต้องการพอ) |
| 2 | Protein, total | โปรตีน | g | low (ต้องการพอ) |
| 3 | Phosphorus | ฟอสฟอรัส | mg | high (ระวังสูง) |
| 4 | Potassium | โพแทสเซียม | mg | high (ระวังสูง) |
| 5 | Sodium | โซเดียม | mg | high (ระวังสูง) |
| 6 | Moisture | น้ำ/ความชื้น | g | high (ระวังสูง) |

`risk_direction = 'high'` → แสดงสีเหลืองเตือนถ้าค่าสูง (ห้ามฟันธง "ห้ามกิน")
`risk_direction = 'low'`  → แสดงสีเหลืองเตือนถ้าค่าต่ำกว่าเพดาน

---

## ข้อมูลเซิร์ฟเวอร์

```
VPS:       ssh -i ~/.ssh/id_ed25519 jocky@109.123.233.155
app root:  /home/jocky/apps/foodcheck
repo:      /home/jocky/apps/foodcheck/app
DB:        /home/jocky/apps/foodcheck/data/foodcheck.sqlite
uvicorn:   127.0.0.1:8010
owner:     jocky (SSH key เดียวกับ jocky.website)
GitHub:    https://github.com/atiroop/foodcheck.git
Panel:     HestiaCP (รูปแบบเดียวกับ project อื่นบน VPS)
```

---

## ขั้นตอน Populate ข้อมูล (รันครั้งเดียว)

```bash
cd scraper
python db.py                          # สร้าง DB จาก schema_complete.sql
python build_food_list.py A           # ทดสอบกลุ่ม A ก่อน
python build_food_list.py             # ดึง master list ครบทุกกลุ่ม
python fetch_nutrients.py --limit 10  # ทดสอบ 10 ตัว
python fetch_nutrients.py             # ดึงทั้งหมด (resume ได้)
python fetch_nutrients.py --retry     # ถ้า error ค่อยรันซ้ำ
```

---

## Environment Variables

```
USDA_API_KEY=<key จาก api.data.gov>
SECRET_KEY=<สำหรับ session/JWT>
DATABASE_PATH=data/foodcheck.sqlite   # default ถ้าไม่ set
```

---

## แนวทางโค้ด

- Python 3.12+ ใช้ type hints ทุกที่
- คอมเมนต์และ log ภาษาไทยได้ (เจ้าของอ่านไทย)
- เก็บค่าโภชนาการ Thai FCD เป็น TEXT ใน DB (ต้นทางปน `-`) → cast REAL ตอนใช้
- USDA cache เก็บเป็น REAL เพราะ API คืนตัวเลขจริง
- อย่าตั้งชื่อไฟล์ทับ stdlib: `http.py`, `json.py`, `re.py` ฯลฯ
- ใช้ `fetcher.py` สำหรับ HTTP client เสมอ
