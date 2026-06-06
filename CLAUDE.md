# CLAUDE.md — foodcheck.jocky.website

คู่มือนี้สำหรับ Claude Code เวลาทำงานในโปรเจกต์นี้ อ่านก่อนเริ่มเสมอ

ใช้กฎเดียวกับ Codex ใน `AGENTS.md` และรายละเอียดเต็มใน `docs/PROJECT_INSTRUCTIONS.md`

สรุปสั้น:

- โปรเจกต์นี้เป็น personal / non-commercial site สำหรับค้นหา Nutrition Facts อาหารไทยจาก Thai FCD ของ INMU Mahidol
- ต้องแสดง source attribution ของ INMU เสมอ
- ห้ามให้คำแนะนำทางการแพทย์แบบฟันธง หรือสรุปว่าอาหารใด "กินได้/ห้ามกิน"
- ใช้ SQLite เป็นหลัก: `data/foodcheck.sqlite`
- Schema หลัก: `scraper/schema_complete.sql`
- Web app อยู่ใน `web/` และรันด้วย FastAPI/uvicorn
- VPS path จริง: `/home/jocky/apps/foodcheck`
- ห้ามลด `REQUEST_DELAY` ต่ำกว่า 1.5 วินาที
- PD nutrient names ต้องใช้ชื่อจริงใน DB: `Energy, by calculation`, `Protein, total`, `Phosphorus`, `Potassium`, `Sodium`, `Moisture`
