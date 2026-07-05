// Shared client-side helpers for converting between serving units.
// Mirrors web/unit_conversion.py — the API always sends the authoritative
// grams_per_unit values; this file just reads/writes that shape.
window.FoodCheckUnits = (function () {
  const SHORT_LABEL = {
    g: "ก.",
    kg: "กก.",
    oz: "ออนซ์",
    ml: "มล.",
    l: "ล.",
    tsp: "ช้อนชา",
    tbsp: "ช้อนโต๊ะ",
    cup: "ถ้วยตวง",
  };

  const STEP = {
    g: 10,
    kg: 0.1,
    oz: 1,
    ml: 10,
    l: 0.1,
    tsp: 1,
    tbsp: 1,
    cup: 0.25,
  };

  // ค่าเริ่มต้นก่อนข้อมูลจาก API มาถึง — มีแค่หน่วยมวล (g/kg/oz) เท่านั้นที่ใช้ได้
  function defaultConversions() {
    return {
      density_available: false,
      density_source: null,
      note: "",
      units: [
        { code: "g", label: "กรัม (g)", grams_per_unit: 1, available: true },
        { code: "kg", label: "กิโลกรัม (kg)", grams_per_unit: 1000, available: true },
        { code: "oz", label: "ออนซ์ (oz)", grams_per_unit: 28.3495, available: true },
        { code: "ml", label: "มิลลิลิตร (mL)", grams_per_unit: null, available: false },
        { code: "l", label: "ลิตร (L)", grams_per_unit: null, available: false },
        { code: "tsp", label: "ช้อนชา (tsp)", grams_per_unit: null, available: false },
        { code: "tbsp", label: "ช้อนโต๊ะ (tbsp)", grams_per_unit: null, available: false },
        { code: "cup", label: "ถ้วยตวง (cup, 240 mL)", grams_per_unit: null, available: false },
      ],
    };
  }

  function findUnit(conversions, unitCode) {
    return (conversions && conversions.units || []).find((u) => u.code === unitCode) || null;
  }

  function gramsPerUnit(conversions, unitCode) {
    const unit = findUnit(conversions, unitCode);
    return unit && unit.available ? unit.grams_per_unit : null;
  }

  function gramsFor(amount, unitCode, conversions) {
    const factor = gramsPerUnit(conversions, unitCode);
    if (factor === null || amount === null || amount === undefined || isNaN(amount)) return null;
    return amount * factor;
  }

  function amountFor(grams, unitCode, conversions) {
    const factor = gramsPerUnit(conversions, unitCode);
    if (factor === null || grams === null || grams === undefined || isNaN(grams)) return null;
    return grams / factor;
  }

  function shortLabel(unitCode) {
    return SHORT_LABEL[unitCode] || unitCode;
  }

  function stepFor(unitCode) {
    return STEP[unitCode] || 1;
  }

  function round(value, decimals) {
    const factor = Math.pow(10, decimals);
    return Math.round(value * factor) / factor;
  }

  return { defaultConversions, gramsFor, amountFor, gramsPerUnit, shortLabel, stepFor, round };
})();
