"""ค่าตั้งต้นส่วนกลางของ Thai FCD scraper."""
from pathlib import Path

BASE_URL = "https://inmu.mahidol.ac.th/thaifcd"

# endpoint
GROUP_LIST_URL = BASE_URL + "/foodsearch/food_group_result"
FOOD_NAME_URL = BASE_URL + "/foodsearch/food_name/"

# path
ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
DB_PATH = DATA_DIR / "thaifcd.sqlite"
SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"

# มารยาทต่อ server ต้นทาง: หน่วงระหว่าง request (วินาที)
REQUEST_DELAY = 1.5
TIMEOUT = 30
MAX_RETRIES = 3
RETRY_BACKOFF = 5  # วินาที คูณจำนวนครั้งที่ retry

USER_AGENT = (
    "foodcheck-personal-scraper/1.0 "
    "(non-commercial personal use; contact: admin@jocky.website)"
)

HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "th,en;q=0.8",
    "X-Requested-With": "XMLHttpRequest",
}

# Version 3 (Aug 2025): endpoint food_group_result รับ food_group_id (ตัวเลข)
# แทน status (ตัวอักษร) — mapping นี้ดึงมาจาก dropdown ของหน้า food_group
FOOD_GROUPS = {
    "A": "Cereals and their products",
    "B": "Starchy roots, tubers and their products",
    "C": "Legums, nuts, seeds and their products",
    "D": "Vegetables and their products",
    "E": "Fruits and their products",
    "F": "Meat, other animals and their products",
    "G": "Finfish, shellfish, other aquatic animals and their products",
    "H": "Eggs and their products",
    "J": "Milk and its products",
    "K": "Fats, oils and their products",
    "M": "Sugars, syrup and confectionery",
    "N": "Spices, herbs, condiments and other seasonings",
    "Q": "Beverages: nonalcoholic",
    "S": "Fast foods: franchise foods",
    "T": "Mixed foods: ready-to-eat",
    "U": "Miscellaneous",
    "Z": "Branded Food Products",
}

# food_group_id ตัวเลขที่ Version 3 ใช้ยิง endpoint (จาก dropdown option value)
FOOD_GROUP_IDS = {
    "A": 70, "B": 71, "C": 73, "D": 74, "E": 75,
    "F": 76, "G": 77, "H": 78, "J": 79, "K": 80,
    "M": 81, "N": 72, "Q": 82, "S": 83, "T": 84,
    "U": 85, "Z": 69,
}
