# CLAUDE.md — foodcheck.jocky.website

คู่มือนี้สำหรับ Claude Code เวลาทำงานในโปรเจกต์นี้ อ่านก่อนเริ่มเสมอ

## โปรเจกต์นี้คืออะไร

เครื่องมือส่วนตัวไว้เช็ค Nutrition Facts ของอาหารไทย จากฐานข้อมูล
Thai Food Composition Database (Thai FCD) ของสถาบันโภชนาการ ม.มหิดล (INMU)

แรงจูงใจหลัก: ใช้ในครอบครัว โดยเฉพาะการดูค่าโภชนาการที่สำคัญต่อ
**ผู้ป่วยล้างไตทางช่องท้อง (PD)** เช่น โปรตีน ฟอสฟอรัส โพแทสเซียม โซเดียม

โดเมน: https://foodcheck.jocky.website
เป็น personal / non-commercial site ไม่มีโฆษณา ไม่เก็บเงิน

## ⚠️ ข้อควรระวังสำคัญที่สุด (อ่านก่อนทำอะไร)

### 1. เรื่องลิขสิทธิ์ข้อมูล
ข้อมูลทั้งหมดเป็นของ INMU Mahidol ใช้ได้เฉพาะ non-commercial และ
**ต้องแสดงการอ้างอิงแหล่งที่มา (INMU) บนหน้าเว็บเสมอ** หากวันใด
foodcheck เปลี่ยนเป็นเชิงพาณิชย์ ต้องขออนุญาต INMU ก่อน
(kunchit.jud@mahidol.ac.th, piyanut.sri@mahidol.ac.th)
อย่าลบ credit / source attribution ออกจากหน้าเว็บหรือไฟล์ export โดยเด็ดขาด

### 2. เรื่องสุขภาพ (สำคัญมากเพราะเกี่ยวกับผู้ป่วย)
ตัวเลขในฐานข้อมูลเป็น **ค่าเฉลี่ยต่อ 100 กรัม** ไม่ใช่คำแนะนำเฉพาะบุคคล
ผู้ป่วยล้างไตแต่ละคนมีเพดานสารอาหารที่แพทย์/นักโภชนาการกำหนดต่างกัน
- ห้ามให้ UI หรือโค้ดสรุปว่าอาหารใด "กินได้/ห้ามกิน" สำหรับผู้ป่วยแบบฟันธง
- ให้แสดงตัวเลขตามจริง + ข้อความเตือนว่าควรปรึกษานักโภชนาการประจำตัว
- เมื่อทำฟีเจอร์เกี่ยวกับ PD/ผู้ป่วย ให้ระวังเป็นพิเศษ ไม่ให้คำแนะนำทางการแพทย์

### 3. มารยาทต่อ server ต้นทาง
ตอน scrape **ห้ามลดค่าหน่วง** (REQUEST_DELAY ใน config.py) ต่ำกว่า 1 วินาที
เป้าหมายคือยุ่งกับ server เขาให้น้อยที่สุด ดึงครั้งเดียวเก็บลง DB เราเอง
ไม่ยิงซ้ำโดยไม่จำเป็น ใช้ flag nutrient_fetched เพื่อ resume เสมอ

## โครงสร้างโปรเจกต์

```
foodcheck/
├── CLAUDE.md              # ไฟล์นี้
├── README.md              # คู่มือใช้งาน
├── requirements.txt
├── .gitignore
├── scraper/               # ตัวดึงข้อมูล (รันครั้งเดียวพอ)
│   ├── config.py          # ค่าตั้ง endpoint, delay, รายชื่อกลุ่ม
│   ├── db.py              # เปิด/สร้าง SQLite
│   ├── fetcher.py         # HTTP client + retry + หน่วง (อย่าตั้งชื่อ http.py!)
│   ├── schema.sql         # โครงสร้าง DB
│   ├── build_food_list.py # ขั้น 1: ดึง master list (id ทุกตัว)
│   ├── fetch_nutrients.py # ขั้น 2: ดึง nutrition ทีละตัว (resume ได้)
│   └── export.py          # ขั้น 3: export CSV/JSON (optional)
├── data/                  # ผลลัพธ์ (gitignore ตัว sqlite/csv ขนาดใหญ่)
│   └── thaifcd.sqlite
├── web/                   # เว็บแอป (ยังไม่เริ่ม — เฟสถัดไป)
└── docs/
```

## ขั้นตอนการดึงข้อมูล (เรียงตามนี้)

```bash
cd scraper
python db.py                      # สร้าง DB เปล่า
python build_food_list.py A       # ทดสอบทีละกลุ่มก่อน (กลุ่ม A)
python build_food_list.py         # ดึง master list ครบทุกกลุ่ม
python fetch_nutrients.py --limit 5   # ทดสอบดึง nutrient 5 ตัวแรก
python fetch_nutrients.py             # ดึงที่เหลือทั้งหมด (resume ได้)
python fetch_nutrients.py --retry     # ถ้ามีตัว error ค่อยรันซ้ำ
python export.py                  # (optional) ออก CSV/JSON
```

## สถาปัตยกรรมข้อมูล

- ต้นทางมี 3 ชั้น: Food Group (A–Z) -> รายการอาหาร (มี internal `id`) -> Nutrition
- กุญแจคือ internal `id` (เช่น A6 = id 129) ดึงมาจาก href ใน list
- `status` = รหัสกลุ่ม (A,B,..) | `food_group_id` = internal id ของกลุ่ม (เช่น 70)
- endpoint list: `/foodsearch/food_group_result?status=A&mode=food_group_result&page_no=N`
- endpoint nutrient: `/foodsearch/food_name/?dbcode=STD&food_group_id=70&id=129&name=...`
- ไฟล์ที่ปุ่ม "Save as Excel" โหลดมา จริง ๆ เป็น HTML table (ไม่ใช่ xls แท้)

## ข้อมูลเซิร์ฟเวอร์ / deploy

- VPS: `ssh -i ~/.ssh/id_ed25519 jocky@109.123.233.155`
- web root: `/home/jocky/web/foodcheck.jocky.website/public_html/`
- owner: `jocky` (ใช้ ssh key เดียวกับ project jocky.website)
- GitHub: https://github.com/atiroop/foodcheck.git
- จัดการผ่าน HestiaCP (เหมือน project อื่นบน VPS นี้)

## แนวทางโค้ด

- Python 3.12+ ใช้ type hints
- คอมเมนต์/ข้อความ log เป็นภาษาไทยได้ (เจ้าของอ่านไทย)
- เก็บค่าตัวเลขโภชนาการเป็น TEXT ใน DB เพราะต้นทางปน '-' กับตัวเลข
  (ค่อย cast ตอนแสดงผล/คำนวณ)
- อย่าตั้งชื่อไฟล์ทับ stdlib (`http.py`, `json.py` ฯลฯ) — เคยพังมาแล้ว

## เฟสถัดไป (ยังไม่ทำ จนกว่าจะสั่ง)

1. เว็บแอปค้นหา (Flask/FastAPI) อ่านจาก SQLite
2. หน้าเปรียบเทียบอาหาร + ไฮไลต์สารอาหารที่ผู้ป่วย PD ต้องระวัง
3. deploy ขึ้น VPS ผ่าน HestiaCP + systemd
