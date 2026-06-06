#!/bin/bash
# deploy.sh — รันบน VPS เพื่ออัปเดตโค้ดและ restart service
# ใช้: ssh -i ~/.ssh/id_ed25519 jocky@109.123.233.155 "bash /home/jocky/apps/foodcheck/app/deploy/deploy.sh"
# หรือรันตรงบน VPS: bash deploy.sh

set -e

APP_ROOT="/home/jocky/apps/foodcheck"
APP_DIR="$APP_ROOT/app"
VENV_DIR="$APP_ROOT/venv"
DATA_DIR="$APP_ROOT/data"
DB_PATH="$DATA_DIR/foodcheck.sqlite"
LEGACY_DB_PATH="$DATA_DIR/thaifcd.sqlite"
SERVICE_FILE="/etc/systemd/system/foodcheck.service"

echo "=== FoodCheck Deploy ==="

# 1. pull โค้ดล่าสุด
cd "$APP_DIR"
git pull origin main

# 2. activate venv (สร้างถ้ายังไม่มี)
if [ ! -d "$VENV_DIR" ]; then
  echo "สร้าง virtualenv..."
  python3 -m venv "$VENV_DIR"
fi
source "$VENV_DIR/bin/activate"

# 3. install/upgrade dependencies
pip install -q -r requirements.txt

# 4. เตรียม DB path หลัก (ช่วง migration จาก thaifcd.sqlite -> foodcheck.sqlite)
mkdir -p "$DATA_DIR"
if [ ! -f "$DB_PATH" ] && [ -f "$LEGACY_DB_PATH" ]; then
  cp "$LEGACY_DB_PATH" "$DB_PATH"
fi

# 5. apply schema_complete.sql แบบ idempotent
(
  cd "$APP_DIR/scraper"
  DATABASE_PATH="$DB_PATH" python db.py
)

# 6. update systemd unit
sudo cp "$APP_DIR/deploy/foodcheck.service" "$SERVICE_FILE"
sudo systemctl daemon-reload
sudo systemctl enable foodcheck

# 7. restart service
sudo systemctl restart foodcheck
sudo systemctl status foodcheck --no-pager -l

echo "=== Deploy สำเร็จ ==="
