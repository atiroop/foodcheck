#!/bin/bash
# first_time_setup.sh — รันครั้งแรกบน VPS เท่านั้น
# ต้องรันด้วย sudo หรือ user ที่มีสิทธิ์ systemctl

set -e

APP_DIR="/home/jocky/web/foodcheck.jocky.website/app"
VENV_DIR="/home/jocky/web/foodcheck.jocky.website/venv"
DATA_DIR="/home/jocky/web/foodcheck.jocky.website/app/data"
SERVICE_FILE="/etc/systemd/system/foodcheck.service"

echo "=== FoodCheck First-Time Setup ==="

# 1. clone repo
mkdir -p /home/jocky/web/foodcheck.jocky.website
cd /home/jocky/web/foodcheck.jocky.website
git clone https://github.com/atiroop/foodcheck.git app

# 2. สร้าง venv
python3 -m venv "$VENV_DIR"
source "$VENV_DIR/bin/activate"
pip install -q -r "$APP_DIR/requirements.txt"

# 3. อัปโหลด thaifcd.sqlite (ต้องทำแยกผ่าน scp)
echo ""
echo "⚠️  อย่าลืม upload database:"
echo "   scp -i ~/.ssh/id_ed25519 data/thaifcd.sqlite jocky@109.123.233.155:$DATA_DIR/"
echo ""

# 4. ติดตั้ง systemd service
sudo cp "$APP_DIR/deploy/foodcheck.service" "$SERVICE_FILE"
sudo systemctl daemon-reload
sudo systemctl enable foodcheck
sudo systemctl start foodcheck

# 5. แสดง status
sudo systemctl status foodcheck --no-pager

echo ""
echo "=== Setup สำเร็จ ==="
echo "เว็บรันที่ http://127.0.0.1:8010"
echo "ตั้ง Nginx proxy ตาม deploy/nginx.conf"
