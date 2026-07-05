"""Convert nutrient values between standard serving units for FoodCheck.

Thai FCD / Anamai data is stored per 100 g. Mass units (g, kg, oz) always
convert directly. Volume units (mL, L, tsp, tbsp, cup) need the food's
density (g per mL) to convert to grams — either an explicit `Density`
nutrient from the source database, or a rough fallback for a few
well-known condiments where density is never analysed.
"""
from __future__ import annotations

from typing import Any

from web.nutrition_sanity import parse_number

TEASPOON_ML = 5
TABLESPOON_ML = 15
CUP_ML = 240
OZ_TO_G = 28.3495

FALLBACK_DENSITIES = [
    {
        "category": "table_salt",
        "keywords": ["เกลือ", "salt"],
        "density_g_per_ml": 1.2,
        "match_mode": "exact_start",
        "note": "ค่าประมาณทั่วไปสำหรับเกลือป่น; ความละเอียดและวิธีตักมีผลต่อกรัมจริง",
    },
    {
        "category": "granulated_sugar",
        "keywords": ["น้ำตาลทราย", "sugar cane, brown", "sugar, granulated"],
        "density_g_per_ml": 0.8,
        "match_mode": "contains",
        "note": "ค่าประมาณทั่วไปสำหรับน้ำตาลทราย; ชนิดน้ำตาลและวิธีตักมีผลต่อกรัมจริง",
    },
    {
        "category": "sauce_without_density",
        "keywords": ["ซอส", "sauce", "น้ำปลา", "fish sauce", "ซีอิ๊ว", "soy sauce"],
        "density_g_per_ml": 1.0,
        "match_mode": "condiment",
        "note": "ค่าประมาณทั่วไปเมื่อไม่มี density ในฐานข้อมูล; ซอสแต่ละชนิดอาจหนักต่างกัน",
    },
]

# หน่วยมาตรฐานที่ FoodCheck รองรับ — "mass" แปลงได้เสมอ, "volume" ต้องรู้ density
STANDARD_UNITS: list[dict[str, Any]] = [
    {"code": "g", "label": "กรัม (g)", "kind": "mass", "factor": 1},
    {"code": "kg", "label": "กิโลกรัม (kg)", "kind": "mass", "factor": 1000},
    {"code": "oz", "label": "ออนซ์ (oz)", "kind": "mass", "factor": OZ_TO_G},
    {"code": "ml", "label": "มิลลิลิตร (mL)", "kind": "volume", "ml": 1},
    {"code": "l", "label": "ลิตร (L)", "kind": "volume", "ml": 1000},
    {"code": "tsp", "label": "ช้อนชา (tsp)", "kind": "volume", "ml": TEASPOON_ML},
    {"code": "tbsp", "label": "ช้อนโต๊ะ (tbsp)", "kind": "volume", "ml": TABLESPOON_ML},
    {"code": "cup", "label": "ถ้วยตวง (cup, 240 mL)", "kind": "volume", "ml": CUP_ML},
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


def resolve_density(food: dict[str, Any], nutrients: list[dict[str, Any]]) -> tuple[float | None, str | None, str]:
    """Return (density_g_per_ml, source_key, note), or (None, None, "") if unresolvable."""
    density = _nutrient_value(nutrients, "Density")
    if density and density > 0:
        return density, "density", "คำนวณจาก density ในฐานข้อมูล (กรัมต่อมิลลิลิตร)"

    for rule in FALLBACK_DENSITIES:
        if _matches_fallback(food, rule):
            return rule["density_g_per_ml"], rule["category"], rule["note"]

    return None, None, ""


def get_unit_conversions(food: dict[str, Any], nutrients: list[dict[str, Any]]) -> dict[str, Any]:
    """Return grams-per-unit for every standard unit FoodCheck supports.

    Mass units (g/kg/oz) are always available. Volume units (mL/L/tsp/tbsp/cup)
    are only available when this food's density can be resolved.
    """
    density, density_source, note = resolve_density(food, nutrients)

    units = []
    for unit in STANDARD_UNITS:
        if unit["kind"] == "mass":
            grams_per_unit = unit["factor"]
        else:
            grams_per_unit = round(density * unit["ml"], 6) if density else None
        units.append(
            {
                "code": unit["code"],
                "label": unit["label"],
                "grams_per_unit": grams_per_unit,
                "available": grams_per_unit is not None,
            }
        )

    return {
        "density_available": density is not None,
        "density_source": density_source,
        "note": note,
        "units": units,
    }
