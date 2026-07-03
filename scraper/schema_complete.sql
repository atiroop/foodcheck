-- =============================================================================
-- foodcheck.jocky.website — Complete Database Schema
-- =============================================================================
-- ออกแบบรองรับ 3 ระดับ:
--   Level 1 : ค้นหาวัตถุดิบ (Thai FCD + USDA real-time fallback)
--   Level 2 : Recipe Builder (หลาย user, บันทึก recipe ส่วนตัวได้)
--   Level 3 : เมนูสำเร็จ (Thai FCD เท่านั้น แสดง "ไม่มีข้อมูล" ถ้าขาด)
--
-- DB หลัก  : foodcheck.sqlite  (โภชนาการ + users + recipes)
-- Source 1 : Thai FCD — INMU Mahidol (non-commercial, cite required)
-- Source 2 : USDA FoodData Central — Public Domain (real-time fallback via API)
--
-- ⚠️  ข้อมูลโภชนาการเป็นของ INMU / USDA เท่านั้น
--     ไม่ใช้เพื่อการพาณิชย์ ต้องแสดง attribution บนหน้าเว็บเสมอ
-- ⚠️  ค่าตัวเลขเป็นค่าเฉลี่ย ไม่ใช่คำแนะนำทางการแพทย์เฉพาะบุคคล
-- =============================================================================

PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

-- =============================================================================
-- SECTION 1 : THAI FCD — ข้อมูลโภชนาการหลัก
-- =============================================================================

-- กลุ่มอาหาร A–Z
CREATE TABLE IF NOT EXISTS food_group (
    status          TEXT PRIMARY KEY,       -- 'A', 'B', ... 'Z'
    food_group_id   INTEGER NOT NULL,       -- internal id ของ Thai FCD (เช่น 70)
    name_en         TEXT NOT NULL
);

-- รายการอาหารทั้งหมดจาก Thai FCD
CREATE TABLE IF NOT EXISTS food (
    id              INTEGER PRIMARY KEY,    -- internal id จาก Thai FCD (เช่น 129)
    food_code       TEXT,                   -- รหัส เช่น 'A6', 'F42'
    status          TEXT NOT NULL,          -- กลุ่ม → food_group.status
    food_group_id   INTEGER NOT NULL,
    name_th         TEXT,
    name_en         TEXT,
    scientific_name TEXT,
    dbcode          TEXT DEFAULT 'STD',
    -- scraper tracking
    nutrient_fetched INTEGER NOT NULL DEFAULT 0,  -- 0=ยังไม่ดึง 1=สำเร็จ -1=error
    fetched_at      TEXT,
    source          TEXT NOT NULL DEFAULT 'thaifcd_inmu',  -- แหล่งข้อมูล: 'thaifcd_inmu' | 'thaifcd_anamai'
    FOREIGN KEY (status) REFERENCES food_group(status)
);

-- ค่าโภชนาการจาก Thai FCD (long format: 1 แถว = 1 nutrient ของ 1 อาหาร)
-- เก็บค่าเป็น TEXT เพราะต้นทางปน '-' กับตัวเลข  →  cast ตอนใช้งาน
CREATE TABLE IF NOT EXISTS nutrient (
    food_id         INTEGER NOT NULL,
    nutrient_name   TEXT NOT NULL,          -- ชื่อตามต้นทาง เช่น 'Phosphorus'
    unit            TEXT,                   -- 'mg', 'g', 'kcal', ...
    per_100g        TEXT,                   -- ค่าต่อ 100 g (หรือ '-' ถ้าไม่มีข้อมูล)
    deriv_by        TEXT,                   -- 'Analysed' | 'Calculated' | 'Not analysed'
    n               TEXT,                   -- จำนวนตัวอย่างที่วิเคราะห์
    min_val         TEXT,
    max_val         TEXT,
    sd              TEXT,
    footnote        TEXT,
    last_updated    TEXT,
    source          TEXT NOT NULL DEFAULT 'thaifcd_inmu',  -- แหล่งข้อมูล: 'thaifcd_inmu' | 'thaifcd_anamai'
    PRIMARY KEY (food_id, nutrient_name),
    FOREIGN KEY (food_id) REFERENCES food(id)
);

-- =============================================================================
-- SECTION 1B : กรมอนามัย (ANAMAI) — แหล่งข้อมูลใหม่
-- =============================================================================
-- เก็บแยกจาก food/nutrient ของ INMU เพราะใช้ fID (ข้อความ, zero-padded) แทน
-- internal id ตัวเลข และมีโครงสร้างหมวดหมู่ nutrient ต่างกัน
-- =============================================================================

CREATE TABLE IF NOT EXISTS anamai_food (
    fid             TEXT PRIMARY KEY,        -- เช่น '07034'
    name_th         TEXT,
    name_en         TEXT,
    food_group_th   TEXT,
    food_group_en   TEXT,
    food_type       TEXT,
    nutrient_fetched INTEGER NOT NULL DEFAULT 0,  -- 0=ยังไม่ดึง 1=สำเร็จ -1=error
    fetched_at      TEXT
);

CREATE TABLE IF NOT EXISTS anamai_nutrient (
    fid             TEXT NOT NULL,
    category        TEXT,                    -- 'Main nutrients' | 'Minerals' | 'Vitamins' | ...
    nutrient_name   TEXT NOT NULL,
    amount          REAL,
    unit            TEXT,
    PRIMARY KEY (fid, nutrient_name),
    FOREIGN KEY (fid) REFERENCES anamai_food(fid)
);

-- =============================================================================
-- SECTION 2 : USDA FALLBACK CACHE
-- =============================================================================
-- เมื่อ nutrient ของ Thai FCD เป็น '-' หรือ 'Not analysed'
-- ระบบจะ query USDA FoodData Central real-time แล้ว cache ผลลัพธ์ไว้ที่นี่
-- ป้องกันการยิง API ซ้ำสำหรับ ingredient เดิม
-- =============================================================================

-- mapping: food ของ Thai FCD ↔ fdc_id ของ USDA (manual หรือ auto-match)
CREATE TABLE IF NOT EXISTS usda_food_mapping (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    thai_food_id    INTEGER NOT NULL,       -- → food.id
    fdc_id          INTEGER NOT NULL,       -- USDA FoodData Central id
    fdc_description TEXT,                   -- ชื่อจาก USDA เพื่อให้คนตรวจสอบได้
    match_method    TEXT NOT NULL DEFAULT 'auto',  -- 'auto' | 'manual'
    confidence      TEXT,                   -- 'high' | 'medium' | 'low'
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(thai_food_id, fdc_id),
    FOREIGN KEY (thai_food_id) REFERENCES food(id)
);

-- cache ค่าโภชนาการจาก USDA (long format เหมือน nutrient)
CREATE TABLE IF NOT EXISTS usda_nutrient_cache (
    fdc_id          INTEGER NOT NULL,
    nutrient_name   TEXT NOT NULL,          -- ชื่อ normalize แล้ว เช่น 'Phosphorus'
    unit            TEXT,
    per_100g        REAL,                   -- USDA คืนตัวเลขจริง ไม่มี '-'
    usda_nutrient_id INTEGER,               -- id ของ nutrient ใน USDA API
    cached_at       TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (fdc_id, nutrient_name)
);

-- =============================================================================
-- SECTION 3 : USERS
-- =============================================================================
-- รองรับหลาย user ใช้งาน recipe builder ร่วมกัน
-- auth แบบง่าย (username + hashed password) เหมาะกับ personal/family use
-- =============================================================================

CREATE TABLE IF NOT EXISTS user (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    username        TEXT NOT NULL UNIQUE,
    password_hash   TEXT NOT NULL,          -- bcrypt hash
    display_name    TEXT,
    -- PD patient profile (optional) — เก็บเพื่อช่วยแสดงผลเฉพาะบุคคล
    -- ⚠️ ไม่ใช้ตัดสินทางการแพทย์ ใช้แค่สำหรับ highlight UI
    is_pd_patient   INTEGER NOT NULL DEFAULT 0,  -- 0=ไม่ใช่ 1=ผู้ป่วย PD
    -- เพดานที่แพทย์กำหนด (NULL = ไม่ได้ตั้ง)
    pd_protein_g    REAL,   -- โปรตีน กรัม/วัน
    pd_phosphorus_mg REAL,  -- ฟอสฟอรัส มก./วัน
    pd_potassium_mg  REAL,  -- โพแทสเซียม มก./วัน
    pd_sodium_mg     REAL,  -- โซเดียม มก./วัน
    pd_energy_kcal   REAL,  -- พลังงาน กิโลแคลอรี/วัน
    pd_fluid_ml      REAL,  -- น้ำ มล./วัน
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

-- =============================================================================
-- SECTION 4 : RECIPE BUILDER
-- =============================================================================

-- recipe header (ของ user คนใดคนหนึ่ง)
CREATE TABLE IF NOT EXISTS recipe (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         INTEGER NOT NULL,
    name            TEXT NOT NULL,          -- เช่น 'ส้มตำปูปลาร้า'
    description     TEXT,
    servings        REAL NOT NULL DEFAULT 1,  -- จำนวนที่ทำได้
    serving_unit    TEXT DEFAULT 'จาน',
    is_public       INTEGER NOT NULL DEFAULT 0,  -- 0=ส่วนตัว 1=ให้ user อื่นดูได้
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (user_id) REFERENCES user(id) ON DELETE CASCADE
);

-- รายการ ingredient ใน recipe (เชื่อมกับ food ของ Thai FCD)
CREATE TABLE IF NOT EXISTS recipe_ingredient (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    recipe_id       INTEGER NOT NULL,
    food_id         INTEGER NOT NULL,       -- → food.id (Thai FCD)
    amount_g        REAL NOT NULL,          -- น้ำหนัก กรัม (ผู้ใช้กรอก)
    note            TEXT,                   -- หมายเหตุ เช่น 'ไม่รวมน้ำจิ้ม'
    sort_order      INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (recipe_id) REFERENCES recipe(id) ON DELETE CASCADE,
    FOREIGN KEY (food_id)   REFERENCES food(id)
);

-- =============================================================================
-- SECTION 5 : PD NUTRIENT CONFIG
-- =============================================================================
-- กำหนดว่า nutrient_name ใดเป็น "PD-critical"
-- ใช้ join กับตาราง nutrient/usda_nutrient_cache เพื่อ highlight UI
-- แยกตารางไว้เผื่ออนาคตเพิ่ม/ลด/ปรับ order ได้โดยไม่ต้องแก้โค้ด
-- =============================================================================

CREATE TABLE IF NOT EXISTS pd_nutrient (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    nutrient_name   TEXT NOT NULL UNIQUE,   -- ต้องตรงกับ nutrient.nutrient_name
    display_name_th TEXT NOT NULL,          -- ชื่อแสดงบนหน้าเว็บ
    unit            TEXT NOT NULL,
    sort_order      INTEGER NOT NULL DEFAULT 0,
    -- ทิศทางความเสี่ยงสำหรับผู้ป่วย PD (ใช้แค่ highlight สี ไม่ตัดสิน)
    -- 'high' = ถ้าค่าสูงต้องระวัง  |  'low' = ถ้าค่าต่ำต้องระวัง
    risk_direction  TEXT NOT NULL DEFAULT 'high'
);

-- seed ข้อมูลเริ่มต้น 6 ตัว PD-critical
INSERT OR IGNORE INTO pd_nutrient
    (nutrient_name,         display_name_th,    unit,   sort_order, risk_direction)
VALUES
    ('Energy, by calculation', 'พลังงาน',       'kcal', 1,          'low'),
    ('Protein, total',         'โปรตีน',         'g',    2,          'low'),
    ('Phosphorus',             'ฟอสฟอรัส',       'mg',   3,          'high'),
    ('Potassium',              'โพแทสเซียม',     'mg',   4,          'high'),
    ('Sodium',                 'โซเดียม',        'mg',   5,          'high'),
    ('Moisture',               'น้ำ/ความชื้น',   'g',    6,          'high');

-- =============================================================================
-- SECTION 6 : INDEXES
-- =============================================================================

CREATE INDEX IF NOT EXISTS idx_food_status         ON food(status);
CREATE INDEX IF NOT EXISTS idx_food_code           ON food(food_code);
CREATE INDEX IF NOT EXISTS idx_food_fetched        ON food(nutrient_fetched);
CREATE INDEX IF NOT EXISTS idx_food_name_th        ON food(name_th);
CREATE INDEX IF NOT EXISTS idx_food_name_en        ON food(name_en);

CREATE INDEX IF NOT EXISTS idx_nutrient_food       ON nutrient(food_id);
CREATE INDEX IF NOT EXISTS idx_nutrient_name       ON nutrient(nutrient_name);

CREATE INDEX IF NOT EXISTS idx_anamai_food_fetched ON anamai_food(nutrient_fetched);
CREATE INDEX IF NOT EXISTS idx_anamai_food_name_th ON anamai_food(name_th);
CREATE INDEX IF NOT EXISTS idx_anamai_food_name_en ON anamai_food(name_en);
CREATE INDEX IF NOT EXISTS idx_anamai_nutrient_fid ON anamai_nutrient(fid);

CREATE INDEX IF NOT EXISTS idx_usda_map_thai       ON usda_food_mapping(thai_food_id);
CREATE INDEX IF NOT EXISTS idx_usda_cache_fdc      ON usda_nutrient_cache(fdc_id);

CREATE INDEX IF NOT EXISTS idx_recipe_user         ON recipe(user_id);
CREATE INDEX IF NOT EXISTS idx_recipe_ingredient   ON recipe_ingredient(recipe_id);
CREATE INDEX IF NOT EXISTS idx_recipe_food         ON recipe_ingredient(food_id);

-- =============================================================================
-- SECTION 7 : VIEWS — query สำเร็จรูปสำหรับ app
-- =============================================================================

-- View 1: ค่าโภชนาการรวม Thai FCD ทุกตัว พร้อม flag ว่าขาดหรือไม่
CREATE VIEW IF NOT EXISTS v_food_nutrient AS
SELECT
    f.id            AS food_id,
    f.food_code,
    f.name_th,
    f.name_en,
    f.status        AS food_group,
    n.nutrient_name,
    n.unit,
    n.per_100g,
    n.deriv_by,
    -- is_missing: 1 ถ้าค่าไม่มีจริง (ควร fallback USDA)
    CASE WHEN n.per_100g IS NULL
              OR trim(n.per_100g) = '-'
              OR lower(trim(n.deriv_by)) = 'not analysed'
         THEN 1 ELSE 0
    END             AS is_missing
FROM food f
JOIN nutrient n ON n.food_id = f.id;

-- View 2: เฉพาะ 6 ตัว PD-critical ของอาหารแต่ละตัว
--         พร้อมแหล่งที่มา (Thai FCD หรือ USDA cache)
CREATE VIEW IF NOT EXISTS v_pd_nutrient AS
SELECT
    f.id            AS food_id,
    f.food_code,
    f.name_th,
    f.name_en,
    pd.nutrient_name,
    pd.display_name_th,
    pd.unit,
    pd.sort_order,
    pd.risk_direction,
    -- ค่าจาก Thai FCD ก่อน
    COALESCE(
        CASE WHEN n.per_100g IS NOT NULL
                  AND trim(n.per_100g) != '-'
                  AND lower(trim(n.deriv_by)) != 'not analysed'
             THEN CAST(n.per_100g AS REAL) END,
        -- fallback: ค่าจาก USDA cache ถ้า map ไว้แล้ว
        uc.per_100g
    )               AS value_per_100g,
    -- แหล่งที่มาของค่า
    CASE
        WHEN n.per_100g IS NOT NULL
             AND trim(n.per_100g) != '-'
             AND lower(trim(n.deriv_by)) != 'not analysed'
        THEN 'Thai FCD'
        WHEN uc.per_100g IS NOT NULL
        THEN 'USDA (fallback)'
        ELSE NULL
    END             AS value_source
FROM food f
CROSS JOIN pd_nutrient pd
LEFT JOIN nutrient n
       ON n.food_id = f.id AND n.nutrient_name = pd.nutrient_name
LEFT JOIN usda_food_mapping um ON um.thai_food_id = f.id
LEFT JOIN usda_nutrient_cache uc
       ON uc.fdc_id = um.fdc_id AND uc.nutrient_name = pd.nutrient_name;

-- View 3: คำนวณโภชนาการของ recipe (รวม ingredient ตาม amount_g)
CREATE VIEW IF NOT EXISTS v_recipe_nutrition AS
SELECT
    ri.recipe_id,
    r.name          AS recipe_name,
    r.user_id,
    r.servings,
    pd.nutrient_name,
    pd.display_name_th,
    pd.unit,
    pd.sort_order,
    pd.risk_direction,
    -- รวมค่าตาม proportion กรัม
    SUM(
        COALESCE(
            CASE WHEN n.per_100g IS NOT NULL
                      AND trim(n.per_100g) != '-'
                      AND lower(trim(n.deriv_by)) != 'not analysed'
                 THEN CAST(n.per_100g AS REAL) END,
            uc.per_100g
        ) * ri.amount_g / 100.0
    )               AS total_value,   -- ค่ารวมทั้ง recipe (ทุก serving)
    SUM(
        COALESCE(
            CASE WHEN n.per_100g IS NOT NULL
                      AND trim(n.per_100g) != '-'
                      AND lower(trim(n.deriv_by)) != 'not analysed'
                 THEN CAST(n.per_100g AS REAL) END,
            uc.per_100g
        ) * ri.amount_g / 100.0
    ) / r.servings  AS per_serving_value   -- ค่าต่อ 1 serving
FROM recipe_ingredient ri
JOIN recipe r         ON r.id = ri.recipe_id
JOIN food f           ON f.id = ri.food_id
CROSS JOIN pd_nutrient pd
LEFT JOIN nutrient n
       ON n.food_id = f.id AND n.nutrient_name = pd.nutrient_name
LEFT JOIN usda_food_mapping um ON um.thai_food_id = f.id
LEFT JOIN usda_nutrient_cache uc
       ON uc.fdc_id = um.fdc_id AND uc.nutrient_name = pd.nutrient_name
GROUP BY ri.recipe_id, pd.nutrient_name;

-- =============================================================================
-- END OF SCHEMA
-- หมายเหตุสำหรับ developer:
--
-- ลำดับ populate ข้อมูล:
--   1. python scraper/build_food_list.py   → food_group, food
--   2. python scraper/fetch_nutrients.py   → nutrient
--   3. USDA API real-time                  → usda_food_mapping, usda_nutrient_cache
--      (trigger เมื่อ v_pd_nutrient.value_source IS NULL)
--
-- Query ที่ใช้บ่อย:
--   ค้นหาอาหาร:   SELECT * FROM food WHERE name_th LIKE '%หมู%'
--   ค่า PD:        SELECT * FROM v_pd_nutrient WHERE food_id = ?
--   ค่า recipe:    SELECT * FROM v_recipe_nutrition WHERE recipe_id = ?
--   ค่าขาดทั้งหมด: SELECT * FROM v_food_nutrient WHERE is_missing = 1
-- =============================================================================
