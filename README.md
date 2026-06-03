# foodcheck

เครื่องมือส่วนตัวเช็ค Nutrition Facts ของอาหารไทย จากฐานข้อมูล
**Thai Food Composition Database (Thai FCD)** สถาบันโภชนาการ มหาวิทยาลัยมหิดล (INMU)

> ⚠️ ข้อมูลโภชนาการทั้งหมดเป็นของ INMU Mahidol University
> ใช้เพื่อการส่วนตัว / ไม่แสวงหากำไรเท่านั้น และอ้างอิงแหล่งที่มาเสมอ
> แหล่งข้อมูล: https://inmu.mahidol.ac.th/thaifcd/

> ⚠️ ตัวเลขเป็นค่าเฉลี่ยต่อ 100 กรัม ไม่ใช่คำแนะนำทางการแพทย์เฉพาะบุคคล
> ผู้ป่วยล้างไต/โรคไตควรใช้เป็นข้อมูลประกอบการปรึกษานักโภชนาการประจำตัว

## ติดตั้ง

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## ดึงข้อมูล (ทำครั้งเดียว)

```bash
cd scraper
python db.py                        # สร้างฐานข้อมูลเปล่า

# ขั้น 1: ดึงรายการอาหารทั้งหมด (id ทุกตัว)
python build_food_list.py A         # ลองกลุ่มเดียวก่อน
python build_food_list.py           # ครบทุกกลุ่ม

# ขั้น 2: ดึงค่าโภชนาการทีละตัว (หยุดแล้วรันต่อได้ resume อัตโนมัติ)
python fetch_nutrients.py --limit 5 # ทดสอบ 5 ตัว
python fetch_nutrients.py           # ที่เหลือทั้งหมด
python fetch_nutrients.py --retry   # รันซ้ำเฉพาะตัวที่ error

# ขั้น 3 (ถ้าต้องการไฟล์ CSV/JSON)
python export.py
```

ผลลัพธ์อยู่ใน `data/thaifcd.sqlite`

## โครงสร้างฐานข้อมูล

- `food_group` — กลุ่มอาหาร A–Z
- `food` — รายการอาหาร (id, รหัส, ชื่อไทย/อังกฤษ, ชื่อวิทยาศาสตร์)
- `nutrient` — ค่าโภชนาการรายตัว (long format)

ดูตัวอย่าง query:

```sql
-- ค่าที่ผู้ป่วย PD ต้องระวัง ของข้าวกล้องงอกดิบ (A6)
SELECT n.nutrient_name, n.per_100g, n.unit
FROM nutrient n JOIN food f ON f.id = n.food_id
WHERE f.food_code = 'A6'
  AND n.nutrient_name IN ('Protein, total','Phosphorus','Potassium','Sodium');
```

## การมีส่วนกับ server ต้นทางอย่างมีมารยาท

สคริปต์หน่วง 1.5 วินาทีต่อ request และข้ามตัวที่ดึงสำเร็จแล้ว
จึงรบกวน server ของ INMU น้อยที่สุด **กรุณาอย่าลดค่าหน่วงนี้**
