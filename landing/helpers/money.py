from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

def to_decimal(val) -> Decimal:
    if val is None:
        return Decimal("0")
    if isinstance(val, (int, float, Decimal)):
        return Decimal(str(val))
    s = str(val).replace(",", ".").strip()
    try:
        return Decimal(s)
    except InvalidOperation:
        return Decimal("0")

def quantize_2(val: Decimal) -> Decimal:
    return val.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

def fmt_two(val) -> str:
    """UI'da 2 hane string gösterimi; val int/float/Decimal olabilir."""
    d = to_decimal(val)
    return f"{quantize_2(d):.2f}"

def plan_price_for_key(plan_key, region):
    if plan_key == "annual":
        return to_decimal(region["annual"])
    if plan_key == "semi":
        return to_decimal(region.get("semiannual", 0))
    return to_decimal(region["monthly"])