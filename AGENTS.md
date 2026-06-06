# AGENTS.md — foodcheck.jocky.website

คู่มือนี้สำหรับ Codex เวลาทำงานในโปรเจกต์นี้ อ่านก่อนเริ่มเสมอ

## โปรเจกต์นี้คืออะไร

FoodCheck เป็นเว็บส่วนตัว / non-commercial สำหรับค้นหาและเปรียบเทียบ Nutrition Facts ของอาหารไทยจาก Thai Food Composition Database (Thai FCD) ของ INMU Mahidol ใช้ในครอบครัว โดยเน้นสารอาหารที่เกี่ยวข้องกับผู้ป่วยล้างไตทางช่องท้อง (PD)

โดเมน: https://foodcheck.jocky.website

## กฎสำคัญ

1. ต้องแสดง attribution แหล่งข้อมูล INMU บนหน้าเว็บและไฟล์ export เสมอ ห้ามลบ credit/source
2. ตัวเลขเป็นค่าเฉลี่ยต่อ 100 กรัม ไม่ใช่คำแนะนำเฉพาะบุคคล ห้ามสรุปว่าอาหารใด "กินได้" หรือ "ห้ามกิน" สำหรับผู้ป่วย
3. ทุก UI ที่เกี่ยวกับ PD ต้องเตือนให้ปรึกษาแพทย์/นักโภชนาการประจำตัว
4. ห้ามใช้สีเขียว/แดงแบบ binary เพื่อบอกว่าค่าโภชนาการดี/แย่
5. Scraper ต้องหน่วงอย่างน้อย 1.5 วินาทีต่อ request และใช้ `nutrient_fetched` เพื่อ resume กันดึงซ้ำ

## Database

ใช้ SQLite เป็นหลัก เพราะโปรเจกต์เป็น personal/family app อ่านเยอะ เขียนน้อย และ deploy ง่ายกว่า MariaDB

- DB หลัก: `data/foodcheck.sqlite`
- Legacy fallback ช่วง migration: `data/thaifcd.sqlite`
- Schema หลัก: `scraper/schema_complete.sql`
- ค่า Thai FCD ใน `nutrient.per_100g` เก็บเป็น TEXT เพราะต้นทางมี `-` ปนตัวเลข

Schema complete มี 9 tables และ 3 views:

- Thai FCD: `food_group`, `food`, `nutrient`
- USDA fallback: `usda_food_mapping`, `usda_nutrient_cache`
- Users/recipes: `user`, `recipe`, `recipe_ingredient`
- Config: `pd_nutrient`
- Views: `v_food_nutrient`, `v_pd_nutrient`, `v_recipe_nutrition`

## PD Nutrients

ใช้ชื่อ nutrient ตาม DB จริง:

- `Energy, by calculation`
- `Protein, total`
- `Phosphorus`
- `Potassium`
- `Sodium`
- `Moisture`

## โครงสร้างสำคัญ

```text
scraper/                  # scraper + schema
web/                      # FastAPI app + templates
data/                     # SQLite files, ignored by git
deploy/                   # systemd/nginx/deploy scripts
docs/PROJECT_INSTRUCTIONS.md
```

## Deploy

- GitHub: https://github.com/atiroop/foodcheck.git
- VPS: `ssh -i ~/.ssh/id_ed25519 jocky@109.123.233.155`
- App root บน VPS: `/home/jocky/apps/foodcheck`
- Git checkout: `/home/jocky/apps/foodcheck/app`
- DB: `/home/jocky/apps/foodcheck/data/foodcheck.sqlite`
- systemd service: `foodcheck`
- uvicorn: `127.0.0.1:8010`

หลัง deploy ให้เช็ค:

```bash
curl https://foodcheck.jocky.website/api/groups
curl "https://foodcheck.jocky.website/api/search?q=rice"
sudo systemctl status foodcheck --no-pager -l
```
