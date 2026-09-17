# landing/helpers/play_billing.py
"""
Verification of Google Play subscription purchases.

WHY THIS RUNS ON THE SERVER:
Trusting the client's "I bought it" would make anyone who patches the APK
premium for free. The only valid evidence is the subscription state Google's
own API returns for the token.

WHY NO NEW DEPENDENCY:
Instead of google-api-python-client this calls the Android Publisher REST API
directly. Authentication needs only `google-auth`, which is already installed
(it is there for Google sign-in), so requirements.txt gains not a single line.

SETUP (what has to be done on the server):
  1. Create a service account in Google Cloud.
  2. Play Console > Users and permissions > invite that service account and
     grant "View financial data" + "Manage orders and subscriptions".
     (Play Console can take a few hours to apply the permission.)
  3. Put the service account JSON key on the server and point settings at it:
       GOOGLE_PLAY_SERVICE_ACCOUNT_FILE = "/etc/secrets/play-sa.json"
       GOOGLE_PLAY_PACKAGE_NAME = "com.vpnsterr.app"
     Alternative: pass the JSON itself as a string in
     GOOGLE_PLAY_SERVICE_ACCOUNT_JSON (for 12-factor / container setups).

DELIBERATELY NOT DONE:
Real-time Developer Notifications (Pub/Sub) are not wired up. Without them a
cancellation or renewal is only learned the next time the app asks for
verification. That is good enough in practice: the subscription end date is
Google's own `expiryTime`, so an expired subscription lapses on its own; what
is missing is an INSTANT reflection of a cancellation or refund made before
that date.
"""

import json
import os
from datetime import datetime, timezone as dt_timezone

from django.conf import settings

_SCOPE = "https://www.googleapis.com/auth/androidpublisher"
_API = "https://androidpublisher.googleapis.com/androidpublisher/v3"

# Play product id -> the site's plan key.
# These must match the subscription ids defined in Play Console exactly.
PRODUCT_TO_PLAN = {
    "premium_monthly": "monthly",
    "premium_semiannual": "semi",
    "premium_yearly": "annual",
}


class PlayConfigError(RuntimeError):
    """Server-side setup is incomplete - the caller answers 503."""


class PlayVerifyError(RuntimeError):
    """The token could not be verified; `code` is the short reason sent to the client."""

    def __init__(self, code: str, detail: str = ""):
        super().__init__(detail or code)
        self.code = code


def _credentials():
    from google.oauth2 import service_account

    raw = getattr(settings, "GOOGLE_PLAY_SERVICE_ACCOUNT_JSON", "") or ""
    if raw:
        try:
            info = json.loads(raw)
        except Exception as exc:  # noqa: BLE001
            raise PlayConfigError("service account JSON could not be parsed") from exc
        return service_account.Credentials.from_service_account_info(info, scopes=[_SCOPE])

    path = getattr(settings, "GOOGLE_PLAY_SERVICE_ACCOUNT_FILE", "") or ""
    if path and os.path.exists(path):
        return service_account.Credentials.from_service_account_file(path, scopes=[_SCOPE])

    raise PlayConfigError("GOOGLE_PLAY_SERVICE_ACCOUNT_FILE/JSON is not set")


def _package_name() -> str:
    pkg = getattr(settings, "GOOGLE_PLAY_PACKAGE_NAME", "") or ""
    if not pkg:
        raise PlayConfigError("GOOGLE_PLAY_PACKAGE_NAME is not set")
    return pkg


def _parse_rfc3339(value: str):
    """Google returns '2026-01-02T03:04:05.678Z'; turn it into a datetime."""
    if not value:
        return None
    try:
        text = value.replace("Z", "+00:00")
        dt = datetime.fromisoformat(text)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=dt_timezone.utc)
        return dt
    except Exception:  # noqa: BLE001
        return None


# The states Google considers "the user is still entitled". IN_GRACE_PERIOD and
# CANCELED are included on purpose: Google does not cut access while a payment
# problem is being resolved, or before a cancelled period ends, and neither
# should we - otherwise a declined card kills the VPN instantly and the support
# ticket lands on us.
_ACTIVE_STATES = {
    "SUBSCRIPTION_STATE_ACTIVE",
    "SUBSCRIPTION_STATE_IN_GRACE_PERIOD",
    "SUBSCRIPTION_STATE_CANCELED",  # cancelled, but valid until the period ends
}


def verify_subscription(purchase_token: str, expected_product_id: str = "") -> dict:
    """
    Asks Play about the token.

    @return {product_id, plan_key, active, expires_at, state, raw}
    @raise PlayConfigError  server setup is incomplete
    @raise PlayVerifyError  token invalid / product unknown
    """
    from google.auth.transport.requests import AuthorizedSession

    token = (purchase_token or "").strip()
    if not token:
        raise PlayVerifyError("missing_token")

    session = AuthorizedSession(_credentials())
    url = f"{_API}/applications/{_package_name()}/purchases/subscriptionsv2/tokens/{token}"

    try:
        res = session.get(url, timeout=15)
    except Exception as exc:  # noqa: BLE001
        raise PlayVerifyError("play_unreachable", str(exc)) from exc

    if res.status_code == 404:
        raise PlayVerifyError("purchase_not_found")
    if res.status_code in (401, 403):
        # A setup problem: the service account lacks permission, or the key is
        # wrong. Treating that as "invalid purchase" would wrongly reject a
        # user who actually paid.
        raise PlayConfigError(f"Play API authorisation error: HTTP {res.status_code} {res.text[:200]}")
    if res.status_code >= 400:
        raise PlayVerifyError("play_error", f"HTTP {res.status_code}")

    data = res.json()
    state = str(data.get("subscriptionState") or "")

    line_items = data.get("lineItems") or []
    if not line_items:
        raise PlayVerifyError("purchase_not_found", "lineItems is empty")

    # There can be more than one line (a plan change); take the one that ends
    # latest. Lines whose expiry cannot be read sort last, and if none can be
    # read the first is used.
    _EPOCH = datetime(1970, 1, 1, tzinfo=dt_timezone.utc)
    scored = [(_parse_rfc3339(i.get("expiryTime") or ""), i) for i in line_items]
    best_exp, best = max(scored, key=lambda pair: pair[0] or _EPOCH)

    # Google's product id is authoritative, whatever the client sends.
    # `expected_product_id` is only recorded so a mismatch stays visible.
    product_id = str(best.get("productId") or "")
    plan_key = PRODUCT_TO_PLAN.get(product_id)
    if not plan_key:
        raise PlayVerifyError("unknown_product", product_id)

    return {
        "product_id": product_id,
        "client_product_id": expected_product_id,
        "plan_key": plan_key,
        "state": state,
        # If the end date is in the past it is not active whatever the state
        # says: Google sometimes updates the state late, the date never lies.
        "active": (
            state in _ACTIVE_STATES
            and best_exp is not None
            and best_exp > datetime.now(dt_timezone.utc)
        ),
        "expires_at": best_exp,
        "raw": data,
    }
