import unittest

from web.unit_conversion import get_unit_conversions


def units_by_code(result):
    return {u["code"]: u for u in result["units"]}


class UnitConversionTests(unittest.TestCase):
    def test_mass_units_always_available(self):
        result = get_unit_conversions(
            {"name_th": "มะละกอ, ดิบ", "name_en": "Papaya, raw"},
            [{"nutrient_name": "Density", "per_100g": "-", "unit": "g/mL"}],
        )
        units = units_by_code(result)

        self.assertFalse(result["density_available"])
        self.assertTrue(units["g"]["available"])
        self.assertEqual(units["g"]["grams_per_unit"], 1)
        self.assertTrue(units["kg"]["available"])
        self.assertEqual(units["kg"]["grams_per_unit"], 1000)
        self.assertTrue(units["oz"]["available"])
        self.assertAlmostEqual(units["oz"]["grams_per_unit"], 28.3495)

        for code in ("ml", "l", "tsp", "tbsp", "cup"):
            self.assertFalse(units[code]["available"])
            self.assertIsNone(units[code]["grams_per_unit"])

    def test_density_drives_all_volume_units(self):
        result = get_unit_conversions(
            {"name_th": "น้ำปลา, เกรด1, ต่อ 100 มล.", "name_en": "Sauce, fish, grade 1, per 100 ml"},
            [{"nutrient_name": "Density", "per_100g": "1.223", "unit": "g/mL"}],
        )
        units = units_by_code(result)

        self.assertTrue(result["density_available"])
        self.assertEqual(result["density_source"], "density")
        self.assertEqual(units["ml"]["grams_per_unit"], 1.223)
        self.assertEqual(units["l"]["grams_per_unit"], 1223)
        self.assertEqual(units["tsp"]["grams_per_unit"], 6.115)
        self.assertEqual(units["tbsp"]["grams_per_unit"], 18.345)
        self.assertEqual(units["cup"]["grams_per_unit"], 293.52)

    def test_granulated_sugar_fallback(self):
        result = get_unit_conversions(
            {"name_th": "น้ำตาลทรายแดง", "name_en": "Sugar cane, brown"},
            [{"nutrient_name": "Density", "per_100g": "-", "unit": "g/mL"}],
        )
        units = units_by_code(result)

        self.assertTrue(result["density_available"])
        self.assertEqual(result["density_source"], "granulated_sugar")
        self.assertEqual(units["tsp"]["grams_per_unit"], 4)
        self.assertEqual(units["tbsp"]["grams_per_unit"], 12)
        self.assertEqual(units["cup"]["grams_per_unit"], 192)

    def test_salted_food_does_not_match_table_salt_fallback(self):
        result = get_unit_conversions(
            {"name_th": "ถั่วลิสง, อบเกลือ", "name_en": "Peanut, roasted, salted"},
            [{"nutrient_name": "Density", "per_100g": "-", "unit": "g/mL"}],
        )

        self.assertFalse(result["density_available"])
        self.assertFalse(units_by_code(result)["tsp"]["available"])


if __name__ == "__main__":
    unittest.main()
