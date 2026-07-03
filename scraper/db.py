"""Helper สำหรับเปิด/เตรียม SQLite database."""
import sqlite3
from config import DB_PATH, SCHEMA_PATH, DATA_DIR


def get_conn() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def _ensure_column(conn: sqlite3.Connection, table: str, column: str, add_sql: str) -> None:
    """เพิ่ม column ถ้ายังไม่มี (ALTER TABLE ไม่รองรับ IF NOT EXISTS)."""
    cols = {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
    if column not in cols:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {add_sql}")


def init_db() -> None:
    """สร้างตารางตาม schema.sql (idempotent) + migrate column ที่เพิ่มใหม่."""
    conn = get_conn()
    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        conn.executescript(f.read())
    _ensure_column(conn, "food", "source", "source TEXT NOT NULL DEFAULT 'thaifcd_inmu'")
    _ensure_column(conn, "nutrient", "source", "source TEXT NOT NULL DEFAULT 'thaifcd_inmu'")
    conn.commit()
    conn.close()


if __name__ == "__main__":
    init_db()
    print(f"DB ready at {DB_PATH}")
