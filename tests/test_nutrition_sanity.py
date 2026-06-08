import unittest

from web.nutrition_sanity import runNutritionSanityCheck, run_nutrition_sanity_check


def make_food(name_th="", name_en="", **nutrient_values):
    nutrient_names = {
        "energy": ("Energy, by calculation", "kcal"),
        "protein": ("Protein, total", "g"),
        "phosphorus": ("Phosphorus", "mg"),
        "potassium": ("Potassium", "mg"),
        "sodium": ("Sodium", "mg"),
        "water": ("Moisture", "g"),
    }
    nutrients = [
        {
            "nutrient_name": nutrient_name,
            "unit": unit,
            "per_100g": value,
        }
        for key, value in nutrient_values.items()
        for nutrient_name, unit in [nutrient_names[key]]
    ]
    return {
        "id": 1,
        "food_code": "T1",
        "name_th": name_th,
        "name_en": name_en,
        "scientific_name": "",
        "group_name": "",
        "nutrients": nutrients,
    }


class NutritionSanityCheckTests(unittest.TestCase):
    def test_fish_sauce_9mg_sodium_is_severe(self):
        result = runNutritionSanityCheck(make_food(name_th="น้ำปลา", sodium=9))

        self.assertEqual(result["status"], "severe")
        self.assertEqual(result["flags"][0]["rule"], "fish_sauce_low_sodium")
        self.assertIn("9,000 mg", result["flags"][0]["message"])

    def test_fish_sauce_7000mg_sodium_is_ok(self):
        result = runNutritionSanityCheck(make_food(name_en="fish sauce", sodium=7000))

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["flags"], [])

    def test_durian_low_sodium_high_potassium_is_ok(self):
        result = runNutritionSanityCheck(
            make_food(name_en="durian", sodium=11, potassium=389)
        )

        self.assertEqual(result["status"], "ok")

    def test_salt_100mg_sodium_is_severe(self):
        result = runNutritionSanityCheck(make_food(name_th="เกลือ", sodium=100))

        self.assertEqual(result["status"], "severe")
        self.assertEqual(result["flags"][0]["rule"], "salty_condiment_low_sodium")

    def test_water_0mg_sodium_is_ok(self):
        result = runNutritionSanityCheck(make_food(name_en="water", sodium=0, water=100))

        self.assertEqual(result["status"], "ok")

    def test_soy_sauce_50mg_sodium_is_severe(self):
        result = runNutritionSanityCheck(make_food(name_en="soy sauce", sodium=50))

        self.assertEqual(result["status"], "severe")
        self.assertEqual(result["flags"][0]["rule"], "salty_condiment_low_sodium")

    def test_water_over_100g_is_invalid_warning(self):
        result = runNutritionSanityCheck(make_food(name_en="test food", water=120))

        self.assertEqual(result["status"], "warning")
        self.assertEqual(result["flags"][0]["rule"], "water_over_100g")

    def test_negative_potassium_is_invalid_warning(self):
        result = runNutritionSanityCheck(make_food(name_en="test food", potassium=-1))

        self.assertEqual(result["status"], "warning")
        self.assertEqual(result["flags"][0]["rule"], "potassium_negative")

    def test_debug_fields_are_admin_only(self):
        food = make_food(name_en="soy sauce", sodium=50)

        public_result = run_nutrition_sanity_check(food, include_debug=False)
        admin_result = run_nutrition_sanity_check(food, include_debug=True)

        self.assertNotIn("debug", public_result["flags"][0])
        self.assertEqual(admin_result["flags"][0]["debug"]["food_id"], 1)
        self.assertEqual(admin_result["flags"][0]["debug"]["food_code"], "T1")
        self.assertEqual(admin_result["flags"][0]["debug"]["matched_rule"], "salty_condiment_low_sodium")


if __name__ == "__main__":
    unittest.main()
