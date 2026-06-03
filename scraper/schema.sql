-- Thai FCD local snapshot schema
-- แหล่งข้อมูล: Thai Food Composition Database, INMU Mahidol University
-- ใช้เพื่อการส่วนตัว/ไม่แสวงกำไร อ้างอิงแหล่งที่มาเสมอ

PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

-- กลุ่มอาหาร (A, B, C, ...) พร้อม internal food_group_id ของระบบต้นทาง
CREATE TABLE IF NOT EXISTS food_group (
    status          TEXT PRIMARY KEY,        -- รหัสกลุ่ม เช่น 'A'
    food_group_id   INTEGER NOT NULL,        -- internal id ของต้นทาง เช่น 70
    name_en         TEXT NOT NULL
);

-- รายการอาหาร (master list)
CREATE TABLE IF NOT EXISTS food (
    id              INTEGER PRIMARY KEY,     -- internal id จากต้นทาง (เช่น 129 = A6)
    food_code       TEXT,                    -- รหัสอาหาร เช่น 'A6'
    status          TEXT NOT NULL,           -- กลุ่ม (FK -> food_group.status)
    food_group_id   INTEGER NOT NULL,
    name_th         TEXT,
    name_en         TEXT,
    scientific_name TEXT,
    dbcode          TEXT DEFAULT 'STD',
    -- สถานะการดึง nutrition: 0 = ยังไม่ดึง, 1 = ดึงสำเร็จ, -1 = error
    nutrient_fetched INTEGER NOT NULL DEFAULT 0,
    fetched_at      TEXT,
    FOREIGN KEY (status) REFERENCES food_group(status)
);

-- ค่าโภชนาการรายตัว (long format: 1 แถว = 1 nutrient ของ 1 อาหาร)
CREATE TABLE IF NOT EXISTS nutrient (
    food_id         INTEGER NOT NULL,
    nutrient_name   TEXT NOT NULL,
    unit            TEXT,
    per_100g        TEXT,                    -- เก็บเป็น TEXT เพราะต้นทางมี '-' ปนกับตัวเลข
    deriv_by        TEXT,
    n               TEXT,
    min_val         TEXT,
    max_val         TEXT,
    sd              TEXT,
    footnote        TEXT,
    last_updated    TEXT,
    PRIMARY KEY (food_id, nutrient_name),
    FOREIGN KEY (food_id) REFERENCES food(id)
);

CREATE INDEX IF NOT EXISTS idx_food_status        ON food(status);
CREATE INDEX IF NOT EXISTS idx_food_code          ON food(food_code);
CREATE INDEX IF NOT EXISTS idx_food_fetched       ON food(nutrient_fetched);
CREATE INDEX IF NOT EXISTS idx_nutrient_name      ON nutrient(nutrient_name);
