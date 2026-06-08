import unittest

from web.household_measures import get_household_measures


class HouseholdMeasureTests(unittest.TestCase):
    def test_density_creates_teaspoon_and_tablespoon_grams(self):
        result = get_household_measures(
            {"name_th": "น้ำปลา, เกรด1, ต่อ 100 มล.", "name_en": "Sauce, fish, grade 1, per 100 ml"},
            [{"nutrient_name": "Density", "per_100g": "1.223", "unit": "g/mL"}],
        )

        self.assertTrue(result["available"])
        self.assertEqual(result["source"], "density")
        self.assertEqual(result["measures"][1]["grams"], 6.12)
        self.assertEqual(result["measures"][2]["grams"], 18.35)

    def test_granulated_sugar_fallback(self):
        result = get_household_measures(
            {"name_th": "น้ำตาลทรายแดง", "name_en": "Sugar cane, brown"},
            [{"nutrient_name": "Density", "per_100g": "-", "unit": "g/mL"}],
        )

        self.assertTrue(result["available"])
        self.assertEqual(result["source"], "granulated_sugar")
        self.assertEqual(result["measures"][1]["grams"], 4)
        self.assertEqual(result["measures"][2]["grams"], 12)

    def test_salted_food_does_not_match_table_salt_fallback(self):
        result = get_household_measures(
            {"name_th": "ถั่วลิสง, อบเกลือ", "name_en": "Peanut, roasted, salted"},
            [{"nutrient_name": "Density", "per_100g": "-", "unit": "g/mL"}],
        )

        self.assertFalse(result["available"])

    def test_food_without_density_or_match_is_unavailable(self):
        result = get_household_measures(
            {"name_th": "มะละกอ, ดิบ", "name_en": "Papaya, raw"},
            [{"nutrient_name": "Density", "per_100g": "-", "unit": "g/mL"}],
        )

        self.assertFalse(result["available"])


if __name__ == "__main__":
    unittest.main()
