# stdlib
import hashlib
import hmac
import json
import time
import uuid
from datetime import timedelta
from decimal import Decimal, ROUND_HALF_UP

# third-party
import requests
from google.oauth2 import id_token
from google.auth.transport import requests as g_requests

# django
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, get_user_model, login as auth_login
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db.models import Q
from django.http import HttpResponse, HttpResponseBadRequest, JsonResponse
from django.shortcuts import redirect, render
from django.templatetags.static import static
from django.db.models import DateTimeField
from django.utils import timezone
from django.utils.timezone import now
from django.utils.translation import gettext as _
from django.views.decorators.csrf import csrf_exempt, csrf_protect
from django.views.decorators.http import require_GET, require_POST

# local (helpers & models)
from landing.helpers.auth import pick_backend
from landing.helpers.nowpay import effective_amount
from landing.helpers.plans import normalize_plan_slug, plan_price_for_key
from landing.helpers.ui import build_ui_context, build_plan_map
from landing.helpers.features_content import FEATURES
from landing.helpers.subscription import grant_subscription, plan_device_limit
from landing.templatetags.faq_questions import FAQ_QUESTIONS
from landing.templatetags.pricing import (
    PRICING_BY_COUNTRY,
    build_all_offers_json,
    detect_country,
    get_pricing_for_request
)
from .models import Device, ExtensionLink, Order, Subscription


# -----------------------------
# Public pages
# -----------------------------
def home(request):
    ctx_ui, region = build_ui_context(request)
    faq_sorted = sorted(FAQ_QUESTIONS, key=lambda x: x.get("priority", 999))
    faq_teaser = [q for q in faq_sorted if q.get("teaser", False)][:6]

    # pricing + offers
    offers_json = build_all_offers_json(PRICING_BY_COUNTRY, request)  # string JSON list
    # mutlak logo url (image)
    logo_url = request.build_absolute_uri(static('img/VPNSTERR-LOGO.png'))
    
    # audience object (PeopleAudience) — burada önerdiğin suggested age aralığını koy
    audience_obj = {
        "@type": "PeopleAudience",
        "audienceType": "Consumers",
        "suggestedMinAge": 18,
        "suggestedMaxAge": 60,
        "suggestedGender": "Unisex"
    }
    
    # temel ctx
    ctx = {
        "seo_title": _("VPNsterr — Free Unlimited No-Logs & Anonymous VPN"),
        "seo_description": _(
            "Browse with zero logs and full anonymity. VPNsterr's free VPN extension is truly unlimited — upgrade to Premium from $4.99/mo for faster, ad-free servers."
        ),
        **ctx_ui,
        "faq_all": faq_sorted,
        "faq_teaser": faq_teaser,
        "offers_json": offers_json,
        "logo_url": logo_url,
        "audience_json": json.dumps(audience_obj, ensure_ascii=False),

    }

    # --- pricing / json-ld oluşturma ---
    try:
        # logo (mutlak url)
        logo_abs = request.build_absolute_uri(static('img/VPNSTERR-LOGO.png'))

        # request için bölge ve o bölgeye özel fiyat
        pricing_for_req = get_pricing_for_request(request)
        region_code = pricing_for_req.get("country_code")
        currency_code = pricing_for_req.get("currency_code")
        monthly_price = pricing_for_req.get("monthly")

        # bütün ülkeler için offers listesi (JSON string). JSON-yığını template'e vermek için parse ediyoruz
        offers_json_str = build_all_offers_json(PRICING_BY_COUNTRY, request)
        offers_list = json.loads(offers_json_str)

        # Ayrıca kullanıcının bölgesi için tek bir offer (kısa gösterim / fallback)
        regional_offer = {
            "@type": "Offer",
            "name": _("Monthly Plan"),
            "priceCurrency": currency_code,
            "price": f"{monthly_price:.2f}" if isinstance(monthly_price, float) else str(monthly_price),
            "availability": "https://schema.org/InStock",
            "eligibleRegion": region_code,
            "url": request.build_absolute_uri('/pricing/')
        }

        # product JSON-LD objesi
        product_obj = {
            "@context": "https://schema.org",
            "@type": ["Product", "SoftwareApplication"],
            "name": ctx.get("site_name", "VPNsterr"),
            "inLanguage": getattr(request, "LANGUAGE_CODE", getattr(settings, "LANGUAGE_CODE", "en")),
            "url": request.build_absolute_uri(),
            "image": [logo_abs],
            "category": "VPN",
            "applicationCategory": "SecurityApplication",
            "operatingSystem": "iOS, Android, Windows, macOS, Linux, Chrome",
            "brand": {"@type": "Brand", "name": "VPNsterr"},
            "description": ctx.get("seo_description"),
            "slogan": ctx.get("seo_title"),
            "isAccessibleForFree": True,
            "audience": {
                "@type": "PeopleAudience",
                "audienceType": "Consumers",
                "suggestedMinAge": 18,
                "suggestedMaxAge": 60,
                "suggestedGender": "Unisex",
                "geographicArea": {"@type": "Country", "name": region_code or "Global"}
            },
            # offers: hem bölgeye özel kısa offer, hem Google için "offers" listesi -> tüm offers_list'i de koyabiliriz.
            # Burada iki yaklaşım var: (a) sadece bölgesel tek offer (b) tüm offers (ör: offers_list)
            # Google bazen birden fazla offer kabul eder. biz hem kısa hem de full koyuyoruz:
            "offers": [regional_offer] + offers_list
        }

        ctx["product_jsonld"] = json.dumps(product_obj, ensure_ascii=False)
    except Exception as e:
        # hata olursa boş bırak
        ctx["product_jsonld"] = None

    return render(request, "landing/home.html", ctx)

def pricing(request):
    ctx_ui, region = build_ui_context(request)
    ctx = {
        "seo_title": _("Cheap VPN from $4.99/mo — Plans & Deals | VPNsterr"),
        "seo_description": _(
            "Looking for a cheap VPN that doesn't cut corners? VPNsterr Premium starts at $4.99/mo "
            "($39.99/yr) with zero logs, unlimited speed and 24/7 support — or use our free unlimited extension."
        ),
        **ctx_ui,
    }
    return render(request, "landing/pricing.html", ctx)


def vpn_extension(request):
    """/vpn-extension/ — ücretsiz uzantı landing sayfası (ana SEO sayfası)."""
    ctx_ui, region = build_ui_context(request)
    faq_sorted = sorted(FAQ_QUESTIONS, key=lambda x: x.get("priority", 999))
    ctx = {
        "seo_title": _("Free VPN Extension for Chrome — Unlimited | VPNsterr"),
        "seo_description": _(
            "Add the free VPN extension to Chrome — unlimited bandwidth, no sign-up, zero logs. "
            "Works on Edge and Brave too. Go Premium for faster, ad-free browsing."
        ),
        "chrome_store_url": getattr(settings, "CHROME_STORE_URL", ""),
        "faq_teaser": [q for q in faq_sorted if q.get("teaser", False)][:4],
        **ctx_ui,
    }
    return render(request, "landing/vpn_extension.html", ctx)


def best_vpn(request):
    """/best-vpn/ — top 10 VPN karşılaştırma sayfası."""
    ctx_ui, region = build_ui_context(request)
    ctx = {
        "seo_title": _("Best VPN 2026 — Top 10 Free & Paid Picks | VPNsterr"),
        "seo_description": _(
            "Looking for a good VPN? Our top 10 of 2026 puts VPNsterr first — a 100% free, "
            "unlimited, zero-logs extension. Go faster and ad-free from $4.99/mo."
        ),
        **ctx_ui,
    }
    return render(request, "landing/best_vpn.html", ctx)


def feature_detail(request, slug):
    """/features/<slug>/ — her feature'ın kendi içerik sayfası."""
    from django.http import Http404
    f = FEATURES.get(slug)
    if not f:
        raise Http404
    ctx_ui, region = build_ui_context(request)
    ctx = {
        "seo_title": f["meta_title"],
        "seo_description": f["meta_description"],
        "f": f,
        "slug": slug,
        "features_nav": [(k, v["name"]) for k, v in FEATURES.items()],
        **ctx_ui,
    }
    return render(request, "landing/feature_detail.html", ctx)


def free_vpn(request):
    """/free-vpn/ — ücretsiz katman hub sayfası."""
    ctx_ui, region = build_ui_context(request)
    ctx = {
        "seo_title": "Free VPN — Truly Unlimited, No Sign-Up | VPNsterr",
        "seo_description": (
            "Looking for a good free VPN? VPNsterr's free tier is genuinely unlimited — "
            "no data caps, no account, zero logs. See how it's funded and what Premium adds."
        ),
        **ctx_ui,
    }
    return render(request, "landing/free_vpn.html", ctx)


def refund_policy(request):
    return render(request, "landing/refund_policy.html")


def acceptable_use(request):
    return render(request, "landing/acceptable_use.html")


def best_free_vpn_extension(request):
    """/best-free-vpn-extension/ — ücretsiz uzantı listicle sayfası."""
    ctx_ui, region = build_ui_context(request)
    ctx = {
        "seo_title": _("Best Free VPN Extension for Chrome: Top 10 (2026) | VPNsterr"),
        "seo_description": _(
            "We ranked the top 10 free VPN Chrome extensions for speed and privacy. Only VPNsterr "
            "stays truly unlimited — zero logs, no sign-up needed. See why it wins."
        ),
        **ctx_ui,
    }
    return render(request, "landing/best_free_vpn_extension.html", ctx)


def payment(request):
    ctx_ui, region = build_ui_context(request)

    # URL param: ?plan=monthly|semi|semi-annual|annual|...
    initial_plan = normalize_plan_slug(request.GET.get("plan") or "monthly")

    # Tüm planlar + seçili plan
    plan_map = build_plan_map(region, ctx_ui["ui_currency_symbol"])
    plan = plan_map.get(initial_plan, plan_map["monthly"])

    checkout_config = {
        "initial_plan": initial_plan,
        "is_auth": bool(request.user.is_authenticated),
        "ui_currency": ctx_ui["ui_currency"],
        "messages": {
            "enter_email": _("Please enter a valid email address."),
            "email_saved": _("Email saved."),
            "enter_coupon": _("Please enter a coupon."),
            "coupon_ok": _("Coupon applied."),
            "coupon_bad": _("Coupon not valid."),
            "generic_err": _("Something went wrong. Please try again."),
            "must_signin": _("Please sign in first."),
            "must_choose_gw": _("Please select a payment method."),
            "pay_fail": _("Unable to start the payment. Try again."),
            "email_exists": _("Account found. Continue to sign in or pay."),
            "create_password": _("Account not found. Please create a password."),
            "must_login_with_password": _(
                "We found an account. Please log in with your password."
            ),
        },
    }

    ctx = {
        "seo_title": _("Checkout — VPNsterr"),
        "seo_description": _(
            "Secure checkout for VPNsterr plans. Choose sign-in and payment method."
        ),
        **ctx_ui,
        "plan_map": plan_map,
        "plan": plan,  # ← template doğrudan buradan okuyor
        "checkout_config": checkout_config,
        "GOOGLE_CLIENT_ID": getattr(settings, "GOOGLE_CLIENT_ID", ""),
        "offers_json": build_all_offers_json(PRICING_BY_COUNTRY, request),
    }
    return render(request, "landing/payment.html", ctx)


# -----------------------------
# Price (coupon/fee) — FE uses /api/checkout/price/
# -----------------------------
@require_POST
@csrf_protect
def checkout_price(request):
    try:
        data = json.loads(request.body.decode("utf-8"))
    except Exception:
        return HttpResponseBadRequest("bad_json")

    plan_key = normalize_plan_slug(data.get("plan") or "monthly")
    coupon = (data.get("coupon") or "").strip()

    # Bölge/para birimi al
    user_cc = detect_country(request)
    region = PRICING_BY_COUNTRY.get(user_cc, PRICING_BY_COUNTRY["US"])
    base = plan_price_for_key(plan_key, region).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )

    # Basit kupon örneği
    discount = Decimal("0.00")
    if coupon and coupon.upper() == "OFF20":
        discount = (base * Decimal("0.20")).quantize(Decimal("0.01"))

    fee = Decimal("0.00")
    total = base - discount + fee
    if total < 0:
        total = Decimal("0.00")

    return JsonResponse(
        {
            "ok": True,
            "currency": region["currency"],
            "subtotal": f"{base:.2f}",
            "discount": f"{discount:.2f}",
            "fee": f"{fee:.2f}",
            "total": f"{total:.2f}",
        }
    )


# -----------------------------
# Google One Tap / Popup finish
# -----------------------------
User = get_user_model()


def _pick_backend():
    """
    Birden fazla AUTHENTICATION_BACKENDS varsa login() için birini seç.
    Önce allauth backend'i, sonra ModelBackend; bulamazsa ilkini döndürür.
    """
    backends = getattr(settings, "AUTHENTICATION_BACKENDS", [])
    for b in backends:
        if b.endswith("allauth.account.auth_backends.AuthenticationBackend"):
            return b
    for b in backends:
        if b.endswith("django.contrib.auth.backends.ModelBackend"):
            return b
    return backends[0] if backends else "django.contrib.auth.backends.ModelBackend"


@require_POST
@csrf_protect
def google_finish(request):
    token = request.POST.get("credential") or request.headers.get("X-Google-Credential")
    if not token:
        return HttpResponseBadRequest("missing token")

    client_id = getattr(settings, "GOOGLE_CLIENT_ID", None)
    if not client_id:
        return JsonResponse({"ok": False, "error": "server_misconfigured"}, status=500)

    try:
        info = id_token.verify_oauth2_token(token, g_requests.Request(), client_id)
        email = (info.get("email") or "").strip().lower()
        if not email:
            return HttpResponseBadRequest("no email in token")

        base_username = email.split("@")[0][:150]
        username = base_username
        i = 1
        while User.objects.filter(username=username).exists():
            suffix = f"-{i}"
            username = f"{base_username[:150-len(suffix)]}{suffix}"
            i += 1

        user, created = User.objects.get_or_create(
            email=email,
            defaults={
                "username": username,
                "first_name": (info.get("given_name") or "")[:150],
                "last_name": (info.get("family_name") or "")[:150],
            },
        )
        if created:
            user.set_unusable_password()
            user.save(update_fields=["password"])

        backend_path = _pick_backend()
        auth_login(request, user, backend=backend_path)

        return JsonResponse({"ok": True})
    except Exception as e:
        return JsonResponse({"ok": False, "error": str(e)}, status=400)


# -----------------------------
# Basit e-posta yakalama (session)
# -----------------------------
@require_POST
@csrf_protect
def capture_email(request):
    email = (request.POST.get("email") or "").strip()
    if not email or "@" not in email:
        return JsonResponse({"ok": False, "error": "invalid_email"}, status=400)
    request.session["checkout_email"] = email
    return JsonResponse({"ok": True})


@require_POST
@csrf_protect
def email_upsert_login(request):
    """
    Body (x-www-form-urlencoded):
      email, password

    Davranış:
      - email kayıtlıysa: parola doğruysa login
      - email yoksa: user oluştur, parola ata, login
    """
    email = (request.POST.get("email") or "").strip().lower()
    password = request.POST.get("password") or ""

    if not email:
        return JsonResponse({"ok": False, "error": "missing_email"}, status=400)
    try:
        validate_email(email)
    except ValidationError:
        return JsonResponse({"ok": False, "error": "invalid_email"}, status=400)
    if len(password) < 6:
        return JsonResponse({"ok": False, "error": "weak_password"}, status=400)

    # username üret
    base_username = email.split("@")[0][:150]
    username = base_username
    i = 1
    while User.objects.filter(username=username).exclude(email__iexact=email).exists():
        suffix = f"-{i}"
        username = f"{base_username[:150-len(suffix)]}{suffix}"
        i += 1

    user = User.objects.filter(email__iexact=email).first()
    backend_path = pick_backend()

    if user:
        # parolası varsa authenticate et
        if user.has_usable_password():
            u = authenticate(request, username=user.username, password=password)
            if not u:
                return JsonResponse(
                    {"ok": False, "error": "invalid_credentials"}, status=400
                )
            auth_login(request, u, backend=backend_path)
            return JsonResponse({"ok": True})
        else:
            # daha önce Google vb. ile kaydolmuş olabilir; parola set edip login
            user.set_password(password)
            user.save(update_fields=["password"])
            auth_login(request, user, backend=backend_path)
            return JsonResponse({"ok": True})
    else:
        # yeni kullanıcı oluştur
        user = User.objects.create(username=username, email=email)
        user.set_password(password)
        user.save()
        auth_login(request, user, backend=backend_path)
        return JsonResponse({"ok": True})


# -----------------------------
# Dinamik e-posta kontrolü
# -----------------------------
@require_POST
@csrf_protect
def check_email(request):
    email = (request.POST.get("email") or "").strip().lower()
    if not email:
        return JsonResponse({"ok": False, "error": "missing_email"}, status=400)
    try:
        validate_email(email)
    except ValidationError:
        return JsonResponse({"ok": False, "error": "invalid_email"}, status=400)
    exists = User.objects.filter(email__iexact=email).exists()
    return JsonResponse({"ok": True, "exists": exists})


# -----------------------------
# Crypto Gateways (ikonlu liste)
# -----------------------------
def crypto_gateways(request):
    """
    UI'da tek buton: 'Crypto — NOWPayments'.
    Coin seçimini invoice sayfasında kullanıcı yapacak.
    """
    return JsonResponse(
        {
            "gateways": [
                {
                    "key": "nowpay_any",
                    "name": "Crypto — NOWPayments",
                    "note": "Coin seçimini ödeme sayfasında yapın (150+ coin)",
                    "icon": static("img/nowpayments.svg"),
                    "pay_currency": "",  # boş => any (invoice ekranında seçim)
                },
            ]
        }
    )


# -----------------------------
# Checkout Create (NOWPayments)
# -----------------------------
@require_POST
@csrf_protect
def checkout_create(request):
    if not request.user.is_authenticated:
        return JsonResponse({"error": _("Please sign in first.")}, status=401)

    try:
        data = json.loads(request.body.decode("utf-8"))
    except Exception:
        return JsonResponse({"error": "bad_json"}, status=400)

    plan_key = normalize_plan_slug((data.get("plan") or "").strip().lower())
    gateway = (data.get("gateway") or "").strip().lower()
    if gateway not in {"nowpay_any", "nowpay"}:
        return JsonResponse({"error": _("Unsupported gateway.")}, status=400)

    # fiyat/para birimi
    ctx_ui, region = build_ui_context(request)
    user_price_ccy = (ctx_ui.get("ui_currency") or "USD").upper()

    # supported fiat kontrolü + USD fallback hesaplaması tek yerde
    total_amount, user_price_ccy = effective_amount(plan_key, region, user_price_ccy)

    if total_amount <= 0:
        return JsonResponse({"error": "bad_price"}, status=400)

    np_base = getattr(settings, "NOWPAYMENTS_BASE_URL", "https://api.nowpayments.io/v1")
    np_key = getattr(settings, "NOWPAYMENTS_API_KEY", "")
    if not np_key:
        return JsonResponse(
            {"error": "server_misconfigured: missing NOWPAYMENTS_API_KEY"}, status=500
        )

    pay_ccy = getattr(settings, "NOWPAYMENTS_PAY_CURRENCY", "").upper().strip()
    if pay_ccy == "ANY":
        pay_ccy = ""

    ipn_url = getattr(
        settings,
        "NOWPAYMENTS_IPN_URL",
        request.build_absolute_uri("/api/payment/nowpayments/ipn/"),
    )
    success_u = getattr(
        settings,
        "NOWPAYMENTS_SUCCESS_URL",
        request.build_absolute_uri("/payment/success/"),
    )
    cancel_u = getattr(
        settings, "NOWPAYMENTS_CANCEL_URL", request.build_absolute_uri("/payment/")
    )

    order_id = f"{uuid.uuid4().hex[:8]}-{request.user.id}-{int(time.time())}"

    order = Order.objects.create(
        order_id=order_id,
        user=request.user,
        plan_key=plan_key,
        price_amount=total_amount,
        price_currency=user_price_ccy,
        pay_currency=pay_ccy or "",
        gateway="nowpayments",
        status="pending",
    )

    payload = {
        "price_amount": float(total_amount),
        "price_currency": user_price_ccy,
        "order_id": order.order_id,
        "order_description": f"VPNsterr {plan_key} plan",
        "success_url": f"{success_u}?order_id={order.order_id}",
        "cancel_url": f"{cancel_u}?order_id={order.order_id}",
        "ipn_callback_url": ipn_url,
    }
    if pay_ccy:
        payload["pay_currency"] = pay_ccy

    try:
        r = requests.post(
            f"{np_base}/invoice",
            headers={"x-api-key": np_key, "Content-Type": "application/json"},
            json=payload,
            timeout=20,
        )
        try:
            jr = r.json()
        except Exception:
            return JsonResponse(
                {
                    "error": f"nowpayments_bad_response: {r.text[:300]}",
                    "status_code": r.status_code,
                },
                status=502,
            )
    except Exception as e:
        return JsonResponse({"error": f"nowpayments_conn_error: {e}"}, status=502)

    if r.status_code >= 400:
        order.status = "failed"
        order.np_raw = jr
        order.save(update_fields=["status", "np_raw"])
        return JsonResponse(
            {
                "error": jr.get("message") or jr,
                "np_code": jr.get("code"),
                "status_code": r.status_code,
            },
            status=400,
        )

    invoice_url = jr.get("invoice_url")
    invoice_id = jr.get("id") or jr.get("invoice_id")
    order.np_invoice_id = str(invoice_id or "")
    order.np_raw = jr
    order.save(update_fields=["np_invoice_id", "np_raw"])

    return JsonResponse({"redirect_url": invoice_url})


# -----------------------------
# NOWPayments IPN (Webhook)
# -----------------------------
@csrf_exempt
@require_POST
def nowpayments_ipn(request):
    raw = request.body
    sig = request.META.get("HTTP_X_NOWPAYMENTS_SIG", "")
    secret = getattr(settings, "NOWPAYMENTS_IPN_SECRET", "")
    if not secret:
        return JsonResponse({"error": "ipn_not_configured"}, status=500)

    # HMAC doğrulama
    try:
        calc = hmac.new(secret.encode("utf-8"), raw, hashlib.sha512).hexdigest()
    except Exception:
        return JsonResponse({"error": "hmac_fail"}, status=400)
    if not sig or calc != sig:
        return JsonResponse({"error": "bad_signature"}, status=400)

    try:
        data = json.loads(raw.decode("utf-8"))
    except Exception:
        return JsonResponse({"error": "bad_json"}, status=400)

    # Önemli alanlar
    status = (data.get("payment_status") or "").lower()
    order_id = (data.get("order_id") or "").strip()
    invoice_id = str(data.get("invoice_id") or data.get("id") or "")

    # Order’ı bul
    try:
        order = Order.objects.select_related("user").get(order_id=order_id)
    except Order.DoesNotExist:
        return JsonResponse({"error": "order_not_found"}, status=404)

    # idempotency: zaten 'paid' ise tekrar premium vermeyelim
    success_status = {"finished", "confirmed"}
    fail_status = {"failed", "expired", "refunded"}

    # Bazı doğrulamalar (opsiyonel ama faydalı):
    # - data["price_amount"] == order.price_amount vb. (Decimal karşılaştırma dikkat)

    # Kaydı güncelle (ham payload ve invoice_id)
    update_fields = ["np_raw"]
    order.np_raw = data
    if invoice_id and not order.np_invoice_id:
        order.np_invoice_id = invoice_id
        update_fields.append("np_invoice_id")

    if status in success_status:
        if order.status != "paid":
            order.status = "paid"
            order.paid_at = timezone.now()
            update_fields += ["status", "paid_at"]
            order.save(update_fields=update_fields)
            # premium ver (idempotent)
            grant_subscription(order.user, order.plan_key, order=order)
        else:
            order.save(update_fields=update_fields)  # sadece np_raw güncellendi
    elif status in fail_status:
        if order.status != "paid":  # zaten paid ise düşürme
            order.status = "failed" if status == "failed" else status
            update_fields.append("status")
        order.save(update_fields=update_fields)
    else:
        # pending/partially_paid gibi ara durumlar
        order.save(update_fields=update_fields)

    return HttpResponse("OK", content_type="text/plain")


@require_GET
def order_status(request):
    """
    GET /api/order/status/?order_id=xxxx
    Döner: { ok, status, paid, paid_at, plan_key }
    """
    order_id = (request.GET.get("order_id") or "").strip()
    if not order_id:
        return JsonResponse({"ok": False, "error": "missing_order_id"}, status=400)

    try:
        o = Order.objects.get(order_id=order_id)
    except Order.DoesNotExist:
        return JsonResponse({"ok": False, "error": "not_found"}, status=404)

    return JsonResponse(
        {
            "ok": True,
            "status": o.status,  # pending | paid | failed | expired | refunded
            "paid": (o.status == "paid"),
            "paid_at": o.paid_at.isoformat() if o.paid_at else None,
            "plan_key": o.plan_key,
        }
    )


@require_POST
@csrf_protect
def nowpay_reconcile(request):
    """
    POST /api/payment/nowpay/reconcile/
    body: order_id=...
    NOWPayments invoice status -> DB state machine (IPN ile aynı mantık)
    """
    order_id = (request.POST.get("order_id") or "").strip()
    if not order_id:
        return JsonResponse({"ok": False, "error": "missing_order_id"}, status=400)

    try:
        order = Order.objects.select_related("user").get(order_id=order_id)
    except Order.DoesNotExist:
        return JsonResponse({"ok": False, "error": "not_found"}, status=404)

    if not order.np_invoice_id:
        return JsonResponse({"ok": False, "error": "no_invoice_id"}, status=400)

    np_base = getattr(settings, "NOWPAYMENTS_BASE_URL", "https://api.nowpayments.io/v1")
    np_key = getattr(settings, "NOWPAYMENTS_API_KEY", "")
    if not np_key:
        return JsonResponse({"ok": False, "error": "server_misconfigured"}, status=500)

    try:
        r = requests.get(
            f"{np_base}/invoice/{order.np_invoice_id}",
            headers={"x-api-key": np_key},
            timeout=15,
        )
        jr = r.json()
    except Exception as e:
        return JsonResponse({"ok": False, "error": f"fetch_error:{e}"}, status=502)

    # NOWPayments dönen objede "payment_status" benzeri alanlar bulunur.
    status = (jr.get("payment_status") or jr.get("status") or "").lower()
    update_fields = ["np_raw"]
    order.np_raw = jr

    success_status = {"finished", "confirmed"}
    fail_status = {"failed", "expired", "refunded"}

    if status in success_status and order.status != "paid":
        order.status = "paid"
        order.paid_at = timezone.now()
        update_fields += ["status", "paid_at"]
        order.save(update_fields=update_fields)
        grant_subscription(order.user, order.plan_key, order=order)
    elif status in fail_status:
        if order.status != "paid":  # paid’i düşürme
            order.status = "failed" if status == "failed" else status
            update_fields.append("status")
        order.save(update_fields=update_fields)
    else:
        order.save(update_fields=update_fields)

    return JsonResponse(
        {"ok": True, "status": order.status, "paid": order.status == "paid"}
    )


def payment_success(request):
    order_id = (request.GET.get("order_id") or "").strip()
    ctx = {"order_id": order_id}
    return render(request, "landing/payment_success.html", ctx)

@require_GET
def login_view(request):
    """
    GET /login/
    """
    ctx_ui, _region = build_ui_context(request)
    ctx = {
        **ctx_ui,
        "GOOGLE_CLIENT_ID": getattr(settings, "GOOGLE_CLIENT_ID", ""),
        "next": request.GET.get("next") or "/",
        "seo_title": _("Sign in — VPNsterr"),
        "seo_description": _("Sign in to manage your VPNsterr subscription."),
    }
    return render(request, "landing/login.html", ctx)

@login_required
def dashboard(request):
    """
    /dashboard/ — Kullanıcının durumu + cihazları
    Ayrıca: POST ile 'add_device_uuid' alır -> client_uuid olarak kaydeder.
    Destekler hem normal POST (redirect + messages) hem de AJAX (JSON).
    """
    # --- Eğer POST ise yeni cihaz ekleme denemesi ---
    if request.method == "POST" and "add_device_uuid" in request.POST:
        uuid_raw = (request.POST.get("add_device_uuid") or "").strip()
        is_ajax = request.headers.get("x-requested-with") == "XMLHttpRequest"

        if not uuid_raw:
            msg = "UUID boş olamaz."
            if is_ajax:
                return JsonResponse({"ok": False, "error": msg}, status=400)
            messages.error(request, msg)
            return redirect("dashboard")

        if len(uuid_raw) > 64:
            msg = "UUID çok uzun."
            if is_ajax:
                return JsonResponse({"ok": False, "error": msg}, status=400)
            messages.error(request, msg)
            return redirect("dashboard")

        # --- capacity check ---
        _now = now()
        active_sub = (
            Subscription.objects
            .filter(user=request.user, ends_at__gte=_now)
            .order_by("-ends_at")
            .first()
        )
        plan_key = active_sub.plan_key if active_sub else None
        device_cap = plan_device_limit(plan_key)
        used_count = Device.objects.filter(user=request.user, is_active=True).count()
        remaining = max(0, device_cap - used_count)
        if remaining <= 0:
            msg = "Cihaz limiti dolu. Bir cihaz iptal edin veya yükseltme yapın."
            if is_ajax:
                return JsonResponse({"ok": False, "error": msg}, status=400)
            messages.error(request, msg)
            return redirect("dashboard")

        # --- check for existing device with this client_uuid ---
        try:
            existing = Device.objects.get(user=request.user, client_uuid=uuid_raw)
        except Device.DoesNotExist:
            existing = None

        if existing:
            if existing.is_active:
                msg = "Bu cihaz zaten hesabınıza ekli ve aktif."
                if is_ajax:
                    return JsonResponse({"ok": False, "error": msg}, status=409)
                messages.info(request, msg)
                return redirect("dashboard")

            # Eğer daha önce eklenmiş ama revoked ise -> re-activate
            existing.is_active = True
            existing.last_seen = now()
            existing.name = existing.name or "Added from web"
            existing.last_subscription = active_sub if active_sub else existing.last_subscription
            existing.save(update_fields=["is_active", "last_seen", "name", "last_subscription"])
            msg = "Cihaz yeniden aktifleştirildi."
            if is_ajax:
                return JsonResponse({"ok": True, "reactivated": True, "device": {"id": existing.id, "client_uuid": existing.client_uuid}})
            messages.success(request, msg)
            return redirect("dashboard")

        # create device
        try:
            d = Device.objects.create(
                user = request.user,
                client_uuid = uuid_raw,
                platform = "other",
                name = "Added from web",
                is_active = True,
                last_subscription = active_sub if active_sub else None,
            )
        except Exception as e:
            msg = "Cihaz eklenemedi. Hata: %s" % (str(e),)
            if is_ajax:
                return JsonResponse({"ok": False, "error": msg}, status=500)
            messages.error(request, msg)
            return redirect("dashboard")

        # başarı
        msg = "Cihaz eklendi."
        if is_ajax:
            return JsonResponse({"ok": True, "device": {"id": d.id, "client_uuid": d.client_uuid, "name": d.name}})
        messages.success(request, msg)
        return redirect("dashboard")

    # --- GET: render eski dashboard (senin mevcut kodların) ---
    ctx_ui, _region = build_ui_context(request)

    _now = now()
    active_sub = (
        Subscription.objects
        .filter(user=request.user, ends_at__gte=_now)
        .order_by("-ends_at")
        .first()
    )

    if active_sub:
        plan_key = active_sub.plan_key
        ends_at = active_sub.ends_at
        starts_at = active_sub.starts_at
        total_seconds = max(1, int((ends_at - starts_at).total_seconds()))
        left_seconds = max(0, int((ends_at - _now).total_seconds()))
        pct = int(left_seconds * 100 / total_seconds)
        days_left = left_seconds // 86400
        hours_left = (left_seconds % 8640000) // 3600
        status_label = "Premium"
    else:
        plan_key = None
        ends_at = None
        starts_at = None
        pct = 0
        days_left = 0
        hours_left = 0
        status_label = "Free"

    device_cap = plan_device_limit(plan_key)

    devices = (
        Device.objects
        .filter(user=request.user)
        .order_by("-is_active", "-last_seen", "-created_at")
    )

    used_count = devices.filter(is_active=True).count()
    remaining = max(0, device_cap - used_count)

    ctx = {
        **ctx_ui,
        "status_label": status_label,
        "active_sub": active_sub,
        "plan_key": plan_key,
        "ends_at": ends_at,
        "starts_at": starts_at,
        "progress_pct": pct,
        "days_left": days_left,
        "hours_left": hours_left,
        "device_cap": device_cap,
        "devices": devices,
        "used_count": used_count,
        "remaining": remaining,
    }
    return render(request, "landing/dashboard.html", ctx)

# ---- Basit cihaz API’leri ----
@login_required
@require_POST
def device_register(request):
    """
    POST /api/devices/register/
    Body: uuid=<uuid>&platform=<str>&label=<str>&platform_version=&browser=&app_version=
    Eğer limit doluysa 409 döner.
    """
    uuid_str = (request.POST.get("uuid") or "").strip()
    platform = (request.POST.get("platform") or "other").lower()
    label = (request.POST.get("label") or "").strip()[:80]
    platform_version = (request.POST.get("platform_version") or "").strip()[:40]
    browser = (request.POST.get("browser") or "").strip()[:40]
    app_version = (request.POST.get("app_version") or "").strip()[:40]

    # Aktif plan cihaz limiti
    _now = now()
    active_sub = (
        Subscription.objects
        .filter(user=request.user, ends_at__gte=_now)
        .order_by("-ends_at")
        .first()
    )
    device_cap = plan_device_limit(active_sub.plan_key if active_sub else None)

    current_active = Device.objects.filter(user=request.user, is_revoked=False).count()
    # Eğer cihaz daha önce eklenmişse ve revoked değilse double-count yapma:
    existing = None
    if uuid_str:
        existing = Device.objects.filter(user=request.user, uuid=uuid_str).first()

    if existing and not existing.is_revoked:
        # zaten kayıtlı → sadece alanları güncelle/last_seen tazele
        existing.platform = platform or existing.platform
        existing.label = label or existing.label
        if platform_version: existing.platform_version = platform_version
        if browser: existing.browser = browser
        if app_version: existing.app_version = app_version
        existing.last_seen = now()
        existing.save()
        return JsonResponse({"ok": True, "id": existing.id})

    if not existing and current_active >= device_cap:
        return JsonResponse({"ok": False, "error": "device_limit_reached"}, status=409)

    if existing:
        # revoked ise geri aç
        existing.is_active = False
        existing.platform = platform or existing.platform
        if label: existing.label = label
        if platform_version: existing.platform_version = platform_version
        if browser: existing.browser = browser
        if app_version: existing.app_version = app_version
        existing.last_seen = now()
        existing.save()
        return JsonResponse({"ok": True, "id": existing.id})

    # yepyeni kayıt
    obj = Device.objects.create(
        user=request.user,
        label=label,
        platform=platform,
        platform_version=platform_version,
        browser=browser,
        app_version=app_version,
        last_seen=now(),
        # uuid boş ise default üretilecek; istemci uuid gönderiyorsa parser eklemek istersen:
    )
    # İstemci uuid yolladıysa zorla set et (try/except):
    if uuid_str:
        try:
            import uuid as _uuid
            u = _uuid.UUID(uuid_str)
            obj.uuid = u
            obj.save(update_fields=["uuid"])
        except Exception:
            pass

    return JsonResponse({"ok": True, "id": obj.id, "uuid": str(obj.uuid)})


@login_required
@require_POST
def device_revoke(request):
    """
    POST /api/devices/revoke/
    Body: uuid=<uuid>   (client_uuid veya Device.uuid kabul edilir)
    """
    is_ajax = request.headers.get("x-requested-with") == "XMLHttpRequest"
    uuid_str = (request.POST.get("uuid") or request.POST.get("client_uuid") or "").strip()
    if not uuid_str:
        if is_ajax:
            return JsonResponse({"ok": False, "error": "missing_uuid"}, status=400)
        messages.error(request, "UUID eksik.")
        return redirect("dashboard")

    device = None
    try:
        device = Device.objects.get(user=request.user, client_uuid=uuid_str)
    except Device.DoesNotExist:
        try:
            device = Device.objects.get(user=request.user, uuid=uuid_str)
        except Device.DoesNotExist:
            device = None

    if not device:
        if is_ajax:
            return JsonResponse({"ok": False, "error": "not_found"}, status=404)
        messages.error(request, "Cihaz bulunamadı.")
        return redirect("dashboard")

    # Eğer zaten pasifse idempotent cevap ver
    if not device.is_active:
        if is_ajax:
            return JsonResponse({"ok": True, "revoked": False})
        messages.info(request, "Cihaz zaten iptal edilmiş.")
        return redirect("dashboard")

    device.is_active = False
    device.save(update_fields=["is_active"])

    if is_ajax:
        return JsonResponse({"ok": True, "revoked": True, "client_uuid": device.client_uuid, "uuid": str(device.uuid)})
    messages.success(request, "Cihaz iptal edildi.")
    return redirect("dashboard")



def _best_active_sub_among_users(user_ids):
    """ Aday user_id’ler içinde aktif aboneliklerden ends_at en geç olanı seç. """
    if not user_ids:
        return None

    now = timezone.now()
    today = timezone.localdate()
    ends_field = Subscription._meta.get_field('ends_at')

    qs = Subscription.objects.filter(user_id__in=user_ids)
    if isinstance(ends_field, DateTimeField):
        qs = qs.filter(Q(ends_at__isnull=True) | Q(ends_at__gte=now) | Q(ends_at__date__gte=today))
    else:
        qs = qs.filter(Q(ends_at__isnull=True) | Q(ends_at__gte=today))

    row = qs.order_by('-ends_at').values('user_id', 'id', 'ends_at').first()
    print(f"[_best_active_sub_among_users] candidates={user_ids} result={row}")
    return row


def _resolve_premium_by_client_uuid(client_uuid: str):
    """
    1) client_uuid + is_active=True cihazları bul → distinct user_id listesi
    2) bu user’lar içinde aktif subscription’ı olanlar → ends_at max olanı seç
    3) seçilen user altında, aynı client_uuid + is_active=True cihazlardan last_seen en yenisinin uuid’si
    """
    if not client_uuid:
        return (False, None, None)

    dev_qs = (
        Device.objects
        .filter(client_uuid=client_uuid, is_active=True)
        .only('user_id', 'uuid', 'last_seen')
        .order_by('-last_seen')
    )
    user_ids = list(dev_qs.values_list('user_id', flat=True).distinct())
    print(f"[_resolve_premium_by_client_uuid] client_uuid={client_uuid} active_devices={dev_qs.count()} users={user_ids}")

    if not user_ids:
        return (False, None, None)

    best = _best_active_sub_among_users(user_ids)
    if not best:
        print("[_resolve_premium_by_client_uuid] no active subs among users")
        return (False, None, None)

    resolved_user_id = best['user_id']

    # aynı client_uuid + aktif cihazlardan en yeni last_seen
    device_uuid = (
        Device.objects
        .filter(user_id=resolved_user_id, client_uuid=client_uuid, is_active=True)
        .order_by('-last_seen')
        .values_list('uuid', flat=True)
        .first()
    )
    device_uuid = str(device_uuid) if device_uuid else None

    print(f"[_resolve_premium_by_client_uuid] RESOLVED user_id={resolved_user_id} device_uuid={device_uuid} sub_id={best['id']} ends_at={best['ends_at']}")
    return (True, resolved_user_id, device_uuid)


@csrf_exempt
# ---- Eklenti: nonce ile cihaz bağlama (account.js sözleşmesi) ----

def _mint_account_token(user, device_id: str, tier: str, exp_ts: int):
    """İmzalı hesap token'ı: base64url(payload).base64url(HMAC_SHA256(secret, payload_b64))"""
    import base64

    secret = (getattr(settings, "EXTENSION_SHARED_SECRET", "") or "").encode()
    payload = {
        "v": 1,
        "user_id": user.id,
        "device_id": device_id or "",
        "tier": tier,
        "iat": int(time.time()),
        "exp": int(exp_ts),
        "iss": "vpnsterr.com",
    }
    payload_b64 = base64.urlsafe_b64encode(
        json.dumps(payload, separators=(",", ":")).encode()
    ).rstrip(b"=")
    sig = base64.urlsafe_b64encode(
        hmac.new(secret, payload_b64, hashlib.sha256).digest()
    ).rstrip(b"=")
    return (payload_b64 + b"." + sig).decode()


def _verify_account_token(token: str):
    """Payload dict döner; imza/format bozuksa None. exp kontrolü çağırana ait."""
    import base64

    try:
        secret = (getattr(settings, "EXTENSION_SHARED_SECRET", "") or "").encode()
        payload_b64, sig_b64 = token.encode().split(b".", 1)
        want = base64.urlsafe_b64encode(
            hmac.new(secret, payload_b64, hashlib.sha256).digest()
        ).rstrip(b"=")
        if not hmac.compare_digest(want, sig_b64.rstrip(b"=")):
            return None
        pad = b"=" * (-len(payload_b64) % 4)
        return json.loads(base64.urlsafe_b64decode(payload_b64 + pad))
    except Exception:
        return None


def _user_tier_and_exp(user):
    """(tier, exp_ts): premium ise exp = abonelik bitişi; free ise 365 gün."""
    sub = (
        Subscription.objects
        .filter(user=user, ends_at__gte=now())
        .order_by("-ends_at")
        .first()
    )
    if sub:
        return "premium", int(sub.ends_at.timestamp()), sub
    return "free", int(time.time()) + 365 * 86400, None


@login_required
def extension_link(request):
    """
    GET  /extension/link?nonce=..&device_id=..  -> onay sayfası (login zorunlu)
    POST                                        -> nonce'u hesaba bağlar
    """
    nonce = (request.GET.get("nonce") or request.POST.get("nonce") or "").strip()
    device_id = (request.GET.get("device_id") or request.POST.get("device_id") or "").strip()[:64]

    if not (16 <= len(nonce) <= 64):
        return render(request, "landing/extension_link.html", {"error": "bad_nonce"})

    if request.method == "POST":
        link, _created = ExtensionLink.objects.get_or_create(nonce=nonce)
        if link.claimed:
            return render(request, "landing/extension_link.html", {"error": "already_used"})
        link.user = request.user
        link.device_id = device_id or link.device_id
        link.linked_at = now()
        link.save(update_fields=["user", "device_id", "linked_at"])

        # Cihazı hesapta göster (kapasite dolgunsa cihaz kaydını atla; token yine verilir)
        dev_id = link.device_id
        if dev_id:
            device = Device.objects.filter(user=request.user, client_uuid=dev_id).first()
            tier, _exp, sub = _user_tier_and_exp(request.user)
            if device is None:
                cap = plan_device_limit(sub.plan_key if sub else None)
                used = Device.objects.filter(user=request.user, is_active=True).count()
                if used < cap:
                    Device.objects.create(
                        user=request.user, client_uuid=dev_id, platform="browser",
                        name="Browser extension", is_active=True, last_subscription=sub,
                    )
            else:
                device.is_active = True
                device.last_seen = now()
                device.last_subscription = sub or device.last_subscription
                device.save(update_fields=["is_active", "last_seen", "last_subscription"])

        return render(request, "landing/extension_link.html", {"linked": True})

    return render(request, "landing/extension_link.html", {"nonce": nonce, "device_id": device_id})


@csrf_exempt
@require_POST
def extension_link_claim(request):
    """
    POST /api/extension/link/claim  {nonce}
      - bağlanmadıysa 425 (eklenti yoklamaya devam eder)
      - bağlandıysa TEK SEFERLİK imzalı hesap token'ı: {token, email, plan}
    """
    if not getattr(settings, "EXTENSION_SHARED_SECRET", ""):
        return JsonResponse({"ok": False, "error": "server_not_configured"}, status=500)
    try:
        data = json.loads(request.body.decode("utf-8") or "{}")
    except Exception:
        data = {}
    nonce = (data.get("nonce") or "").strip()
    link = ExtensionLink.objects.filter(nonce=nonce).select_related("user").first()
    if not link or not link.user_id:
        return JsonResponse({"ok": False, "error": "pending"}, status=425)
    if link.claimed:
        return JsonResponse({"ok": False, "error": "already_claimed"}, status=409)

    tier, exp_ts, _sub = _user_tier_and_exp(link.user)
    token = _mint_account_token(link.user, link.device_id, tier, exp_ts)
    link.claimed = True
    link.save(update_fields=["claimed"])
    return JsonResponse({
        "ok": True,
        "token": token,
        "email": link.user.email or "",
        "plan": tier,
    })


@csrf_exempt
@require_POST
def extension_link_refresh(request):
    """
    POST /api/extension/link/refresh   (Authorization: Bearer <eski token>)
    Süresi geçmiş olsa bile imzası geçerli token'ı alır, tier'ı DB'den yeniden
    çözer ve TAZE token döner. Abonelik yenilenince premium'a dönüş yolu budur.
    """
    auth = request.headers.get("Authorization", "")
    token = auth[7:].strip() if auth.startswith("Bearer ") else ""
    payload = _verify_account_token(token)
    if not payload:
        return JsonResponse({"ok": False, "error": "invalid_token"}, status=401)
    user = User.objects.filter(id=payload.get("user_id")).first()
    if not user:
        return JsonResponse({"ok": False, "error": "no_user"}, status=401)
    tier, exp_ts, _sub = _user_tier_and_exp(user)
    fresh = _mint_account_token(user, payload.get("device_id") or "", tier, exp_ts)
    return JsonResponse({"ok": True, "token": fresh, "email": user.email or "", "plan": tier})


@csrf_exempt
@require_POST
def extension_link_revoke(request):
    """POST /api/extension/link/revoke (Bearer token) — cihazı pasifleştirir."""
    auth = request.headers.get("Authorization", "")
    token = auth[7:].strip() if auth.startswith("Bearer ") else ""
    payload = _verify_account_token(token)
    if not payload:
        return JsonResponse({"ok": True})  # best-effort: eklenti zaten yerelde sildi
    Device.objects.filter(
        user_id=payload.get("user_id"),
        client_uuid=payload.get("device_id") or "__none__",
    ).update(is_active=False)
    return JsonResponse({"ok": True})


# ---- Eklenti: JSON login/logout (CSRF-muaf; popup'taki Login/Register ekranı için) ----

@csrf_exempt
@require_POST
def extension_login(request):
    """
    POST /api/extension/login/   Body (JSON): {email, password, mode?}
      mode: "login"    -> hesap yoksa hata (no_account)
            "register" -> hesap varsa ve parola yanlışsa hata; yoksa oluştur
            "auto"     -> (varsayılan) varsa giriş, yoksa kayıt (upsert)
    Başarıda Django session cookie set edilir; eklenti sonrasında
    /api/extension/auth-token/ çağırarak imzalı premium token'ını alır.
    """
    try:
        data = json.loads(request.body.decode("utf-8") or "{}")
    except Exception:
        data = {}

    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    mode = (data.get("mode") or "auto").strip().lower()

    if not email:
        return JsonResponse({"ok": False, "error": "missing_email"}, status=400)
    try:
        validate_email(email)
    except ValidationError:
        return JsonResponse({"ok": False, "error": "invalid_email"}, status=400)
    if len(password) < 6:
        return JsonResponse({"ok": False, "error": "weak_password"}, status=400)

    user = User.objects.filter(email__iexact=email).first()
    backend_path = pick_backend()

    if user:
        if user.has_usable_password():
            u = authenticate(request, username=user.username, password=password)
            if not u:
                return JsonResponse({"ok": False, "error": "invalid_credentials"}, status=400)
            auth_login(request, u, backend=backend_path)
            return JsonResponse({"ok": True, "email": email, "created": False})
        # Google ile açılmış hesap: parola belirle + login
        user.set_password(password)
        user.save(update_fields=["password"])
        auth_login(request, user, backend=backend_path)
        return JsonResponse({"ok": True, "email": email, "created": False})

    if mode == "login":
        return JsonResponse({"ok": False, "error": "no_account"}, status=404)

    base_username = email.split("@")[0][:150]
    username = base_username
    i = 1
    while User.objects.filter(username=username).exclude(email__iexact=email).exists():
        suffix = f"-{i}"
        username = f"{base_username[:150-len(suffix)]}{suffix}"
        i += 1
    user = User.objects.create(username=username, email=email)
    user.set_password(password)
    user.save()
    auth_login(request, user, backend=backend_path)
    return JsonResponse({"ok": True, "email": email, "created": True})


@csrf_exempt
@require_POST
def extension_logout(request):
    from django.contrib.auth import logout as _logout
    _logout(request)
    return JsonResponse({"ok": True})


# ---- Eklenti: imzalı yetki token'ı (site = imza otoritesi, havuz = doğrulayıcı) ----

def _mint_extension_token(device_id: str, tier: str, user_id):
    """
    Kompakt HMAC token: base64url(payload_json) + "." + base64url(HMAC_SHA256(secret, payload_b64))
    Havuz aynı EXTENSION_SHARED_SECRET ile doğrular; payload.tier'a güvenir.
    """
    import base64

    secret = (getattr(settings, "EXTENSION_SHARED_SECRET", "") or "").encode()
    ttl = int(getattr(settings, "EXTENSION_TOKEN_TTL_SECONDS", 3600))
    iat = int(time.time())
    payload = {
        "device_id": device_id,
        "tier": tier,
        "user_id": user_id,
        "iat": iat,
        "exp": iat + ttl,
        "iss": "vpnsterr.com",
    }
    payload_b64 = base64.urlsafe_b64encode(
        json.dumps(payload, separators=(",", ":")).encode()
    ).rstrip(b"=")
    sig = hmac.new(secret, payload_b64, hashlib.sha256).digest()
    sig_b64 = base64.urlsafe_b64encode(sig).rstrip(b"=")
    return (payload_b64 + b"." + sig_b64).decode(), ttl


@csrf_exempt
def extension_auth_token(request):
    """
    POST /api/extension/auth-token/   (eklenti, credentials: 'include' ile çağırır)
    Body: {"device_id": "<uuid>", "device_name": "...", "platform": "..."}

    Kullanıcı bu tarayıcıda vpnsterr.com'a giriş yaptıysa session cookie gelir:
      - cihaz hesaba bağlanır/aktifleştirilir (kapasite kontrollü)
      - aktif abonelik varsa tier=premium, yoksa free
      - siteden İMZALI token döner; eklenti bunu havuzun session ucuna verir.
    Giriş yoksa 401 {error:"login_required"} → eklenti Login/Register ekranını gösterir.
    """
    if request.method != "POST":
        return HttpResponseBadRequest("POST only")

    if not request.user.is_authenticated:
        return JsonResponse({"ok": False, "error": "login_required"}, status=401)

    if not getattr(settings, "EXTENSION_SHARED_SECRET", ""):
        return JsonResponse({"ok": False, "error": "server_not_configured"}, status=500)

    try:
        data = json.loads(request.body.decode("utf-8") or "{}")
    except Exception:
        data = {}

    device_id = (data.get("device_id") or "").strip()
    if not (8 <= len(device_id) <= 64):
        return JsonResponse({"ok": False, "error": "bad_device_id"}, status=400)

    device_name = (data.get("device_name") or "").strip()[:80] or "Browser extension"
    platform = (data.get("platform") or "browser").strip()[:24] or "browser"

    _now = now()
    active_sub = (
        Subscription.objects
        .filter(user=request.user, ends_at__gte=_now)
        .order_by("-ends_at")
        .first()
    )

    # Cihazı bağla / aktifleştir (kapasite kontrolü yeni cihaz için)
    device = Device.objects.filter(user=request.user, client_uuid=device_id).first()
    if device is None:
        cap = plan_device_limit(active_sub.plan_key if active_sub else None)
        used = Device.objects.filter(user=request.user, is_active=True).count()
        if used >= cap:
            return JsonResponse({"ok": False, "error": "device_limit",
                                 "used": used, "cap": cap}, status=409)
        device = Device.objects.create(
            user=request.user, client_uuid=device_id,
            platform=platform, name=device_name,
            is_active=True, last_subscription=active_sub,
        )
    else:
        device.is_active = True
        device.last_seen = _now
        device.name = device_name or device.name
        device.platform = platform or device.platform
        device.last_subscription = active_sub or device.last_subscription
        device.save(update_fields=["is_active", "last_seen", "name", "platform", "last_subscription"])

    tier = "premium" if active_sub else "free"
    token, ttl = _mint_extension_token(device_id, tier, request.user.id)

    return JsonResponse({
        "ok": True,
        "token": token,
        "tier": tier,
        "premium": tier == "premium",
        "expires_in": ttl,
        "device_uuid": str(device.uuid),
        "email": request.user.email or "",
    })


@login_required
@require_POST
def account_delete(request):
    """Hesabı kalıcı sil (mağaza zorunluluğu + GDPR). Cascade: cihazlar/abonelikler."""
    if request.POST.get("confirm") != "yes":
        messages.error(request, "Please confirm account deletion.")
        return redirect("dashboard")
    user = request.user
    from django.contrib.auth import logout as auth_logout
    auth_logout(request)
    user.delete()
    return redirect("home")


def extension_handshake(request):
    """
    POST JSON: {"client_uuid": "<required>"}
    Response:
      {
        "premium": bool,              # client_uuid tarafında aktif abonelik varsa True
        "device_uuid": "<uuid>|null", # resolved user altında aynı client_uuid’ye sahip aktif cihazın uuid’si
        "existing": bool              # bu client_uuid ile aktif cihaz var mı (global)
      }
    NOT: request.user KULLANILMAZ. Login gerekmez.
    """
    if request.method != "POST":
        return HttpResponseBadRequest("POST only")

    try:
        data = json.loads(request.body.decode("utf-8") or "{}")
    except Exception:
        data = {}

    client_uuid = (data.get("client_uuid") or "").strip()
    print(f"[handshake] client_uuid={client_uuid!r}")

    if not client_uuid:
        return JsonResponse({"premium": False, "device_uuid": None, "existing": False}, status=200)

    premium, resolved_user_id, device_uuid = _resolve_premium_by_client_uuid(client_uuid)

    # global existing: bu client_uuid’ye sahip aktif cihaz var mı (herhangi bir user’da)
    existing = Device.objects.filter(client_uuid=client_uuid, is_active=True).exists()

    resp = {
        "premium": bool(premium),
        "device_uuid": device_uuid,
        "existing": bool(existing),
    }
    print(f"[handshake] RESP {resp}")
    return JsonResponse(resp)

    """
    POST JSON: {"client_uuid": "<optional>"}
    Response:
      {
        "premium": bool,                # client_uuid tarafında aktif abonelik varsa True
        "device_uuid": "<uuid>|null",   # resolved user altındaki aynı client_uuid’ye sahip aktif device’ın uuid’si
        "existing": bool,               # (sadece login ise) current user altında bu client_uuid’ye ait aktif device var mı?
        "linked_client_uuids": [..]     # (debug/ops amaçlı) resolved user’ın aktif cihazlarındaki tüm client_uuid’ler
      }

    Notlar:
    - Yeni Device OLUŞTURMAZ.
    - Login gerekmez. Anonymous istekler çalışır.
    - Bir client_uuid birden fazla hesaba bağlıysa, **aktif aboneliği olan** ve **ends_at en geç olan**
      kullanıcı seçilir. “En doğru olanı” = “subscription’ı kesin ve en uzun kalan”.
    """
    if request.method != "POST":
        return HttpResponseBadRequest("POST only")

    try:
        data = json.loads(request.body.decode("utf-8") or "{}")
    except Exception:
        data = {}

    client_uuid = (data.get("client_uuid") or "").strip()
    print(f"[handshake] client_uuid={client_uuid!r}")

    premium = False
    device_uuid = None
    linked_client_uuids = []

    if client_uuid:
        premium_by_uuid, resolved_user_id, resolved_device_uuid, user_client_uuids = _resolve_premium_by_client_uuid(client_uuid)
        premium = premium_by_uuid
        device_uuid = resolved_device_uuid
        linked_client_uuids = user_client_uuids
    else:
        # UUID gelmediyse premium = False kabul ediyoruz (isteğine göre 400 da yapabilirsin)
        premium = False
        device_uuid = None

    # existing: sadece login ise kontrol et (Anonymous ise False)
    existing = False
    if client_uuid and getattr(request.user, 'is_authenticated', False):
        existing = Device.objects.filter(
            user_id=getattr(request.user, 'id', None),
            client_uuid=client_uuid,
            is_active=True
        ).exists()

    resp = {
        "premium": bool(premium),
        "device_uuid": device_uuid,
        "existing": bool(existing),
        # ops/debug için faydalı; UI’da göstermek zorunda değilsin.
        "linked_client_uuids": linked_client_uuids,
    }
    print(f"[handshake] RESP {resp}")
    return JsonResponse(resp)



def privacy_policy(request):
    today_iso = timezone.localdate().isoformat()
    return render(request, "landing/privacy_policy.html", {"today_iso": today_iso})

def terms_of_service(request):
    today_iso = timezone.localdate().isoformat()
    return render(request, "landing/terms.html", {"today_iso": today_iso})