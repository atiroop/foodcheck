# Project Instruction — foodcheck.jocky.website

เอกสารนี้อธิบายเป้าหมาย ขอบเขต และแผนงานของโปรเจกต์อย่างละเอียด
(CLAUDE.md เป็นฉบับย่อสำหรับ Claude Code ส่วนไฟล์นี้เป็นฉบับเต็ม)

## 1. วัตถุประสงค์

สร้างเครื่องมือเช็คข้อมูลโภชนาการอาหารไทยไว้ใช้ในครอบครัว ดึงข้อมูลจาก
Thai FCD (INMU Mahidol) มาเก็บในฐานข้อมูลของเราเอง เพื่อ:

1. ดูค่าโภชนาการของเมนู/วัตถุดิบได้เร็ว ไม่ต้องเปิดเว็บต้นทางทีละครั้ง
2. โฟกัสสารอาหารที่สำคัญต่อผู้ป่วยล้างไตทางช่องท้อง (PD) ในบ้าน:
   โปรตีน ฟอสฟอรัส โพแทสเซียม โซเดียม พลังงาน
3. เปรียบเทียบอาหารหลายตัวพร้อมกันได้

## 2. ขอบเขต (สำคัญ)

**อยู่ในขอบเขต**
- ดึงข้อมูล Thai FCD ครั้งเดียวเก็บลง SQLite
- เว็บค้นหา/แสดงผล/เปรียบเทียบ สำหรับใช้ส่วนตัว non-commercial
- แสดง credit INMU เสมอ

**นอกขอบเขต / ห้ามทำ**
- ใช้เชิงพาณิชย์ ขายข้อมูล หรือทำ API สาธารณะให้คนอื่นดึงต่อ โดยไม่ขออนุญาต INMU
- ให้คำแนะนำทางการแพทย์ / ฟันธงว่าอาหารใดผู้ป่วยกินได้หรือห้ามกิน
- scrape ซ้ำ ๆ ถี่ ๆ รบกวน server ต้นทาง

## 3. ที่มาของข้อมูล (เทคนิค)

โครงสร้างต้นทาง 3 ชั้น:
```
Food Group (A–Z)
   └─ รายการอาหาร (แต่ละตัวมี internal id)
         └─ Nutrition Facts (ตารางสารอาหาร)
```

Endpoints ที่ค้นพบ (CodeIgniter + AJAX):

1. **List ต่อกลุ่ม** (คืน HTML table ผ่าน XHR):
   ```
   GET /thaifcd/foodsearch/food_group_result
       ?status=A                    # รหัสกลุ่ม A..Z
       &food_group_id=
       &mode=food_group_result
       &page_no=1                   # paginate
   ```
   ใน response มี `<a href>` ที่ฝัง `id`, `food_group_id`, `name` ของแต่ละอาหาร

2. **Nutrition ต่ออาหาร**:
   ```
   GET /thaifcd/foodsearch/food_name/
       ?dbcode=STD
       &food_group_id=70            # internal id ของกลุ่ม
       &id=129                      # internal id ของอาหาร (A6=129)
       &name=Rice, brown, germinated, raw
   ```

หมายเหตุ: ปุ่ม "Save as Excel" ดาวน์โหลดไฟล์ .xls ที่จริงเป็น HTML table
จึง parse ด้วย BeautifulSoup ได้เหมือนหน้าเว็บปกติ

## 4. โครงฐานข้อมูล

ดู `scraper/schema.sql` — 3 ตาราง: food_group, food, nutrient
- ค่าโภชนาการเก็บเป็น TEXT (ต้นทางปน '-' กับตัวเลข) cast ตอนใช้งาน
- flag `nutrient_fetched` (0/1/-1) ใช้ทำ resume กันดึงซ้ำ

## 5. แผนงานเป็นเฟส

### เฟส 1 — Scraper ✅ (เสร็จแล้ว)
ดึง master list + nutrition เก็บลง SQLite

### เฟส 2 — เว็บแอป (ถัดไป)
- FastAPI หรือ Flask อ่านจาก SQLite (read-only)
- หน้าค้นหาด้วยชื่อไทย/อังกฤษ/รหัส
- หน้ารายละเอียดแสดงตารางโภชนาการเต็ม
- ไฮไลต์ 4 ตัวที่ผู้ป่วย PD ต้องระวัง + ข้อความเตือนให้ปรึกษาผู้เชี่ยวชาญ
- footer แสดง credit INMU + ลิงก์ต้นทาง

### เฟส 3 — Deploy
- repo: https://github.com/atiroop/foodcheck.git
- VPS: jocky@109.123.233.155
- web root: /home/jocky/web/foodcheck.jocky.website/public_html/
- systemd service + reverse proxy ผ่าน HestiaCP (รูปแบบเดียวกับ project อื่นบน VPS)

## 6. หลักการออกแบบ UI สำหรับข้อมูลสุขภาพ

- แสดงตัวเลขตามจริง ไม่ตีความแทนผู้ใช้
- ทุกหน้าที่เกี่ยวกับผู้ป่วยต้องมี disclaimer ว่าเป็นข้อมูลอ้างอิง
  ไม่ทดแทนคำแนะนำของแพทย์/นักโภชนาการ
- ไม่ใช้สีเขียว/แดงแบบฟันธง "ดี/ไม่ดี" กับอาหาร เพราะเพดานของผู้ป่วย
  แต่ละคนต่างกัน — ใช้การแสดงค่าและหน่วยที่ชัดเจนแทน
