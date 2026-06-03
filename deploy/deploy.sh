#!/bin/bash
# deploy.sh — รันบน VPS เพื่ออัปเดตโค้ดและ restart service
# ใช้: ssh jocky@109.123.233.155 "bash ~/deploy_foodcheck.sh"
# หรือรันตรงบน VPS: bash deploy.sh

set -e

APP_DIR="/home/jocky/web/foodcheck.jocky.website/app"
VENV_DIR="/home/jocky/web/foodcheck.jocky.website/venv"

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

# 4. restart service
sudo systemctl restart foodcheck
sudo systemctl status foodcheck --no-pager -l

echo "=== Deploy สำเร็จ ==="
