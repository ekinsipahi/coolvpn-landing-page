from typing import Dict

NORMALIZE_TABLE = {
    "m": "monthly", "month": "monthly", "monthly": "monthly",
    "s": "semi", "semi": "semi", "6": "semi", "6m": "semi",
    "6-month": "semi", "6months": "semi", "semiannual": "semi", "semi-annual": "semi",
    "a": "annual", "y": "annual", "year": "annual", "annual": "annual",
}

def normalize_plan_slug(raw: str) -> str:
    if not raw:
        return "monthly"
    return NORMALIZE_TABLE.get(raw.strip().lower(), "monthly")

def plan_price_for_key(plan_key: str, region: Dict, to_decimal):
    """region içinden doğru fiyatı Decimal'e çevirerek döndürür."""
    if plan_key == "annual":
        return to_decimal(region["annual"])
    if plan_key == "semi":
        return to_decimal(region.get("semiannual", 0))
    return to_decimal(region["monthly"])
