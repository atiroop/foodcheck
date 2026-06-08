"""Approximate household measure conversions for FoodCheck."""
from __future__ import annotations

from typing import Any

from web.nutrition_sanity import parse_number


TEASPOON_ML = 5
TABLESPOON_ML = 15

FALLBACK_DENSITIES = [
    {
        "category": "table_salt",
        "keywords": ["เกลือ", "salt"],
        "grams_per_teaspoon": 6,
        "match_mode": "exact_start",
        "note": "ค่าประมาณทั่วไปสำหรับเกลือป่น; ความละเอียดและวิธีตักมีผลต่อกรัมจริง",
    },
    {
        "category": "granulated_sugar",
        "keywords": ["น้ำตาลทราย", "sugar cane, brown", "sugar, granulated"],
        "grams_per_teaspoon": 4,
        "match_mode": "contains",
        "note": "ค่าประมาณทั่วไปสำหรับน้ำตาลทราย; ชนิดน้ำตาลและวิธีตักมีผลต่อกรัมจริง",
    },
    {
        "category": "sauce_without_density",
        "keywords": ["ซอส", "sauce", "น้ำปลา", "fish sauce", "ซีอิ๊ว", "soy sauce"],
        "grams_per_teaspoon": 5,
        "match_mode": "condiment",
        "note": "ค่าประมาณทั่วไปเมื่อไม่มี density ในฐานข้อมูล; ซอสแต่ละชนิดอาจหนักต่างกัน",
    },
]


def _food_text(food: dict[str, Any]) -> str:
    fields = [
        food.get("name_th"),
        food.get("name_en"),
        food.get("scientific_name"),
        food.get("group_name"),
        food.get("food_code"),
    ]
    return " ".join(str(field) for field in fields if field).lower()


def _nutrient_value(nutrients: list[dict[str, Any]], nutrient_name: str) -> float | None:
    for nutrient in nutrients:
        if nutrient.get("nutrient_name") == nutrient_name:
            return parse_number(nutrient.get("per_100g"))
    return None


def _matches_fallback(food: dict[str, Any], rule: dict[str, Any]) -> bool:
    text = _food_text(food)
    name_th = str(food.get("name_th") or "").strip().lower()
    name_en = str(food.get("name_en") or "").strip().lower()
    status = str(food.get("status") or "").upper()

    if rule["match_mode"] == "exact_start":
        return any(name_th.startswith(keyword) or name_en.startswith(keyword) for keyword in rule["keywords"])

    if rule["match_mode"] == "condiment":
        return status == "N" and any(keyword in text for keyword in rule["keywords"])

    return any(keyword in text for keyword in rule["keywords"])


def _format_grams(value: float) -> float:
    return round(value, 2)


def get_household_measures(food: dict[str, Any], nutrients: list[dict[str, Any]]) -> dict[str, Any]:
    """Return teaspoon/tablespoon gram estimates when FoodCheck can infer them.

    Values are practical serving-size helpers, not original nutrient facts.
    """
    density = _nutrient_value(nutrients, "Density")
    if density and density > 0:
        tsp = density * TEASPOON_ML
        tbsp = density * TABLESPOON_ML
        return {
            "available": True,
            "source": "density",
            "note": "คำนวณจาก density ในฐานข้อมูล: 1 ช้อนชา = 5 mL, 1 ช้อนโต๊ะ = 15 mL",
            "measures": [
                {"label": "100 กรัม", "grams": 100},
                {"label": "1 ช้อนชา", "grams": _format_grams(tsp), "volume_ml": TEASPOON_ML},
                {"label": "1 ช้อนโต๊ะ", "grams": _format_grams(tbsp), "volume_ml": TABLESPOON_ML},
            ],
        }

    for rule in FALLBACK_DENSITIES:
        if _matches_fallback(food, rule):
            tsp = rule["grams_per_teaspoon"]
            tbsp = tsp * 3
            return {
                "available": True,
                "source": rule["category"],
                "note": rule["note"],
                "measures": [
                    {"label": "100 กรัม", "grams": 100},
                    {"label": "1 ช้อนชา", "grams": _format_grams(tsp), "volume_ml": TEASPOON_ML},
                    {"label": "1 ช้อนโต๊ะ", "grams": _format_grams(tbsp), "volume_ml": TABLESPOON_ML},
                ],
            }

    return {"available": False, "source": None, "note": "", "measures": []}
