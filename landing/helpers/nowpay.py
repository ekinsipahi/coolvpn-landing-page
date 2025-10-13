import hmac, hashlib, json
from decimal import Decimal
from typing import Tuple, Dict, Any
import requests
from django.conf import settings
from django.utils import timezone
from landing.templatetags.pricing import PRICING_BY_COUNTRY
from .money import to_decimal
from .plans import plan_price_for_key

SUCCESS_STATES = {"finished", "confirmed"}
FAIL_STATES    = {"failed", "expired", "refunded"}

def pick_supported_fiat(user_price_ccy: str) -> str:
    supported = set(getattr(settings, "NOWPAYMENTS_SUPPORTED_PRICE_FIATS", ["USD", "EUR", "GBP", "TRY"]))
    return user_price_ccy.upper() if user_price_ccy and user_price_ccy.upper() in supported else "USD"

def effective_amount(plan_key: str, region: Dict, user_price_ccy: str) -> Tuple[Decimal, str]:
    # Kullanıcı para birimi desteklenmiyorsa USD bölgesine fallback et
    ccy = pick_supported_fiat(user_price_ccy)
    if ccy == (user_price_ccy or "").upper():
        return plan_price_for_key(plan_key, region, to_decimal), ccy
    us_region = PRICING_BY_COUNTRY.get("US", {})
    return plan_price_for_key(plan_key, us_region, to_decimal), "USD"

def create_invoice(payload: Dict[str, Any]) -> Tuple[Dict[str, Any], int]:
    base = getattr(settings, "NOWPAYMENTS_BASE_URL", "https://api.nowpayments.io/v1")
    key  = getattr(settings, "NOWPAYMENTS_API_KEY", "")
    if not key:
        return {"error": "server_misconfigured: missing NOWPAYMENTS_API_KEY"}, 500
    r = requests.post(f"{base}/invoice",
                      headers={"x-api-key": key, "Content-Type": "application/json"},
                      json=payload, timeout=20)
    try:
        return r.json(), r.status_code
    except Exception:
        return {"error": f"nowpayments_bad_response: {r.text[:300]}", "status_code": r.status_code}, 502

def verify_ipn_signature(raw_body: bytes, recv_sig: str) -> bool:
    secret = getattr(settings, "NOWPAYMENTS_IPN_SECRET", "")
    if not secret:  # ayrı kontrol eden endpoint'te 500 döndür
        return False
    calc = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha512).hexdigest()
    return bool(recv_sig) and (calc == recv_sig)

def timestamp_now():
    return timezone.now()
