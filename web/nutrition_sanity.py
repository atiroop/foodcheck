"""Nutrition data-quality checks for high-risk FoodCheck nutrients."""
from __future__ import annotations

import re
from typing import Any


PD_NUTRIENT_NAMES = {
    "energy": "Energy, by calculation",
    "protein": "Protein, total",
    "phosphorus": "Phosphorus",
    "potassium": "Potassium",
    "sodium": "Sodium",
    "water": "Moisture",
}

NUTRIENT_META = {
    "sodium": {"label": "โซเดียม", "unit": "mg/100g", "expected": "0-40000 mg/100g"},
    "potassium": {"label": "โพแทสเซียม", "unit": "mg/100g", "expected": "0-5000 mg/100g"},
    "phosphorus": {"label": "ฟอสฟอรัส", "unit": "mg/100g", "expected": "0-3000 mg/100g"},
    "protein": {"label": "โปรตีน", "unit": "g/100g", "expected": "0-100 g/100g"},
    "energy": {"label": "พลังงาน", "unit": "kcal/100g", "expected": "0-900 kcal/100g"},
    "water": {"label": "น้ำ/ความชื้น", "unit": "g/100g", "expected": "0-100 g/100g"},
}

SALTY_CONDIMENT_KEYWORDS = {
    "fish_sauce": ["น้ำปลา", "fish sauce"],
    "salt": ["เกลือ", "salt"],
    "soy_sauce": ["ซีอิ๊ว", "ซีอิ้ว", "soy sauce"],
    "seasoning_sauce": ["ซอสปรุงรส", "seasoning sauce"],
    "shrimp_paste": ["กะปิ", "shrimp paste"],
    "fermented_fish_sauce": ["น้ำปลาร้า", "ปลาร้า", "fermented fish sauce"],
    "oyster_sauce": ["oyster sauce"],
    "miso": ["miso"],
    "bouillon": ["bouillon"],
    "stock_cube": ["stock cube"],
}


def parse_number(raw: Any) -> float | None:
    """Parse Thai FCD text values while treating missing markers as unknown."""
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        return float(raw)

    text = str(raw).strip()
    if not text or text in {"-", "—"}:
        return None

    normalized = text.replace(",", "")
    match = re.search(r"-?\d+(?:\.\d+)?", normalized)
    if not match:
        return None
    return float(match.group(0))


def _nutrient_lookup(nutrients: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(n.get("nutrient_name")): n for n in nutrients}


def _field_text(food: dict[str, Any]) -> str:
    parts = [
        food.get("name_th"),
        food.get("name_en"),
        food.get("scientific_name"),
        food.get("group_name"),
        food.get("category"),
        food.get("tags"),
        food.get("food_code"),
    ]
    return " ".join(str(part) for part in parts if part).lower()


def _matched_food_categories(food: dict[str, Any]) -> list[str]:
    haystack = _field_text(food)
    matched: list[str] = []
    for category, keywords in SALTY_CONDIMENT_KEYWORDS.items():
        for keyword in keywords:
            if keyword.lower() in haystack:
                matched.append(category)
                break
    return matched


def _status_from_flags(flags: list[dict[str, Any]]) -> str:
    if any(flag["severity"] == "severe" for flag in flags):
        return "severe"
    if flags:
        return "warning"
    return "ok"


def _flag(
    *,
    nutrient: str,
    severity: str,
    message: str,
    rule: str,
    value: float,
    expected: str,
    debug: dict[str, Any],
) -> dict[str, Any]:
    meta = NUTRIENT_META[nutrient]
    item = {
        "nutrient": nutrient,
        "severity": severity,
        "message": message,
        "rule": rule,
        "value": value,
        "unit": meta["unit"],
        "expected": expected,
    }
    if debug:
        item["debug"] = {
            **debug,
            "matched_rule": rule,
            "suspicious_nutrient": nutrient,
            "current_value": value,
            "expected_rough_range": expected,
        }
    return item


def run_nutrition_sanity_check(
    food: dict[str, Any],
    nutrients: list[dict[str, Any]] | None = None,
    *,
    include_debug: bool = False,
) -> dict[str, Any]:
    """Return data-quality warnings for one food item.

    This is not a medical recommendation engine. It only flags values that look
    impossible or suspicious for imported nutrition data.
    """
    if nutrients is None:
        nutrients = food.get("nutrients", [])

    lookup = _nutrient_lookup(nutrients)
    values: dict[str, float | None] = {}
    for key, nutrient_name in PD_NUTRIENT_NAMES.items():
        values[key] = parse_number(lookup.get(nutrient_name, {}).get("per_100g"))

    debug_context = {}
    if include_debug:
        debug_context = {
            "food_id": food.get("id") or food.get("food_id"),
            "food_code": food.get("food_code"),
            "source_database": food.get("source_database") or food.get("dbcode") or "Thai FCD",
            "import_batch": food.get("import_batch") or food.get("fetched_at"),
        }

    flags: list[dict[str, Any]] = []

    invalid_rules = [
        ("sodium", "sodium_negative", "ค่าโซเดียมติดลบ ซึ่งเป็นไปไม่ได้สำหรับข้อมูลต่อ 100 กรัม"),
        ("potassium", "potassium_negative", "ค่าโพแทสเซียมติดลบ ซึ่งเป็นไปไม่ได้สำหรับข้อมูลต่อ 100 กรัม"),
        ("phosphorus", "phosphorus_negative", "ค่าฟอสฟอรัสติดลบ ซึ่งเป็นไปไม่ได้สำหรับข้อมูลต่อ 100 กรัม"),
        ("protein", "protein_negative", "ค่าโปรตีนติดลบ ซึ่งเป็นไปไม่ได้สำหรับข้อมูลต่อ 100 กรัม"),
        ("energy", "energy_negative", "ค่าพลังงานติดลบ ซึ่งเป็นไปไม่ได้สำหรับข้อมูลต่อ 100 กรัม"),
        ("water", "water_negative", "ค่าน้ำ/ความชื้นติดลบ ซึ่งเป็นไปไม่ได้สำหรับข้อมูลต่อ 100 กรัม"),
    ]
    for nutrient, rule, message in invalid_rules:
        value = values[nutrient]
        if value is not None and value < 0:
            flags.append(
                _flag(
                    nutrient=nutrient,
                    severity="warning",
                    message=message,
                    rule=rule,
                    value=value,
                    expected=NUTRIENT_META[nutrient]["expected"],
                    debug=debug_context,
                )
            )

    upper_rules = [
        ("water", "water_over_100g", 100, "ค่าน้ำ/ความชื้นมากกว่า 100 กรัมต่อ 100 กรัม จึงน่าจะผิดปกติ"),
        ("protein", "protein_over_100g", 100, "ค่าโปรตีนมากกว่า 100 กรัมต่อ 100 กรัม จึงน่าจะผิดปกติ"),
        ("energy", "energy_over_900kcal", 900, "ค่าพลังงานสูงกว่า 900 kcal ต่อ 100 กรัม จึงควรตรวจสอบหน่วยหรือแหล่งข้อมูล"),
        ("sodium", "sodium_over_40000mg", 40000, "ค่าโซเดียมสูงผิดปกติ จึงควรตรวจสอบหน่วยหรือแหล่งข้อมูล"),
        ("potassium", "potassium_over_5000mg", 5000, "ค่าโพแทสเซียมสูงผิดปกติ จึงควรตรวจสอบหน่วยหรือแหล่งข้อมูล"),
        ("phosphorus", "phosphorus_over_3000mg", 3000, "ค่าฟอสฟอรัสสูงผิดปกติ จึงควรตรวจสอบหน่วยหรือแหล่งข้อมูล"),
    ]
    for nutrient, rule, limit, message in upper_rules:
        value = values[nutrient]
        if value is not None and value > limit:
            flags.append(
                _flag(
                    nutrient=nutrient,
                    severity="warning",
                    message=message,
                    rule=rule,
                    value=value,
                    expected=f"<= {limit:g} {NUTRIENT_META[nutrient]['unit']}",
                    debug=debug_context,
                )
            )

    sodium = values["sodium"]
    categories = _matched_food_categories(food)
    if sodium is not None and categories:
        if "fish_sauce" in categories and sodium < 3000:
            message = "ค่าโซเดียมอาจผิดพลาด: อาหารประเภทเครื่องปรุงเค็มไม่ควรมีโซเดียมต่ำผิดปกติ"
            if 1 <= sodium <= 50:
                message += " อาจเป็นกรณีบันทึกหน่วยกรัมเป็นมิลลิกรัม เช่น 9 g ควรเป็น 9,000 mg"
            flags.append(
                _flag(
                    nutrient="sodium",
                    severity="severe",
                    message=message,
                    rule="fish_sauce_low_sodium",
                    value=sodium,
                    expected=">= 3000 mg/100g",
                    debug=debug_context,
                )
            )
        elif sodium < 500:
            message = "ค่าโซเดียมอาจผิดพลาด: อาหารประเภทเครื่องปรุงเค็มไม่ควรมีโซเดียมต่ำผิดปกติ"
            if 1 <= sodium <= 50:
                message += " อาจเป็นกรณีบันทึกหน่วยกรัมเป็นมิลลิกรัม"
            flags.append(
                _flag(
                    nutrient="sodium",
                    severity="severe",
                    message=message,
                    rule="salty_condiment_low_sodium",
                    value=sodium,
                    expected=">= 500 mg/100g",
                    debug=debug_context,
                )
            )

    return {
        "status": _status_from_flags(flags),
        "flags": flags,
    }


def runNutritionSanityCheck(food: dict[str, Any]) -> dict[str, Any]:
    """Compatibility alias matching the requested API shape."""
    return run_nutrition_sanity_check(food)
