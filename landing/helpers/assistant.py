# landing/helpers/assistant.py
"""Köşedeki AI asistanın beyni — Claude'a giden sistem promptu + niyet tespiti.

TEMEL İLKE: asistan YALNIZCA gerçek VPNsterr olgularından konuşur. Olmayan bir
özelliği, fiyatı ya da sözü asla uydurmaz (para gerçek). Kullanıcının kendi
canlı verisi (plan, bitiş tarihi, cihaz sayısı) her turda DB'den çekilir.

Marka kuralları (sahibinden):
- İade YALNIZCA hiç kullanılmamış aboneliklere. "30 gün para iade garantisi" YOK.
- DPI/obfuscation/stealth iddiası YOK. "Bağımsız denetimden geçti" iddiası YOK.
- Extension %100 ücretsiz + gerçekten sınırsız + kayıt gerektirmez.
- Özel (dedicated) premium sunucular HENÜZ yayında değil — dürüstçe "yakında".
"""
from __future__ import annotations

import json
import logging
import urllib.request

from django.conf import settings

log = logging.getLogger(__name__)

_ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
_TIMEOUT = 20


def _model() -> str:
    return getattr(settings, "ASSISTANT_MODEL", "") or "claude-haiku-4-5-20251001"


# ── Niyet tespiti (yükseltme için) — çok dilli anahtar kelime taraması ──────
_INTENT_KEYWORDS = {
    "bug": (
        "hata", "çalışmıyor", "calismiyor", "bozuk", "bağlanmıyor", "baglanmiyor",
        "sorun", "error", "broken", "crash", "bug", "not working", "doesn't work",
        "can't connect", "cant connect", "won't connect", "disconnect", "slow",
        "timeout", "leak", "leaking",
    ),
    "payment": (
        "ödeme", "odeme", "satın", "satin", "refund", "iade", "charge", "charged",
        "billing", "invoice", "payment", "pay ", "paid", "card declined",
        "crypto", "bitcoin", "usdt", "subscription", "cancel", "iptal",
        "money", "para", "double charge", "not activated", "aktif olmadı",
    ),
    "urgent": (
        "acil", "hemen", "urgent", "asap", "immediately", "emergency", "scam",
        "dolandır", "dolandir", "money gone", "lost money", "para gitti",
        "didn't receive", "not credited", "hacked", "stolen",
    ),
    "feature": (
        "özellik", "ozellik", "keşke", "keske", "ekleyin", "can you add",
        "please add", "feature", "wish", "request", "do you support",
        "is there a way", "would be nice", "roadmap", "mobile app", "ios app",
        "android app",
    ),
    "human": (
        "human", "real person", "live support", "live agent", "live chat",
        "talk to someone", "speak to someone", "representative", "agent",
        "gerçek insan", "gercek insan", "canlı destek", "canli destek",
        "operatör", "operator", "temsilci", "birine bağla",
    ),
}

ESCALATE_FLAGS = {"bug", "payment", "urgent", "human"}


def detect_intent(text: str) -> set:
    t = (text or "").lower()
    flags = set()
    for flag, kws in _INTENT_KEYWORDS.items():
        if any(k in t for k in kws):
            flags.add(flag)
    return flags


# ── Kullanıcının canlı hesabı → prompt bağlamı ──────────────────────────────
def build_user_context(user) -> dict:
    """Girişli kullanıcının GERÇEK verisi (salt-okunur). Anonim ziyaretçi → boş."""
    ctx = {"name": "", "snapshot": "", "is_premium": False, "is_auth": False}
    if not getattr(user, "is_authenticated", False):
        ctx["snapshot"] = "Anonymous visitor (not signed in). They may not have an account at all."
        return ctx
    ctx["is_auth"] = True
    try:
        ctx["name"] = (user.first_name or "").strip() or (user.email or "").split("@")[0]
    except Exception:  # noqa: BLE001
        pass
    snap = []
    try:
        from django.utils import timezone
        sub = user.subscriptions.filter(ends_at__gte=timezone.now()).order_by("-ends_at").first()
        if sub:
            ctx["is_premium"] = True
            snap.append(
                f"PREMIUM subscriber — plan {sub.plan_key}, active until "
                f"{sub.ends_at.strftime('%b %d, %Y')} (paid via {sub.source})."
            )
        else:
            snap.append("Free account (no active Premium subscription).")
    except Exception as e:  # noqa: BLE001
        log.warning("[ASSISTANT] sub snapshot failed: %s", e)
    try:
        n = user.devices.filter(is_active=True).count()
        snap.append(f"Linked devices: {n}.")
    except Exception:  # noqa: BLE001
        pass
    ctx["snapshot"] = "\n".join(snap) or "No account data loaded."
    return ctx


# ── Sabitlenmiş sistem promptu ──────────────────────────────────────────────
def build_system_prompt(user_ctx=None) -> str:
    ctx = user_ctx or {}
    name = (ctx.get("name") or "").strip()
    named = f" ({name})" if name else ""
    if ctx.get("is_premium"):
        who = (f"The user{named} is a PAYING Premium customer. Treat them like a valued "
               "regular: warm, calm, zero sales pressure. If anything is broken for them, "
               "reassure and flag to a human immediately.")
    elif ctx.get("is_auth"):
        who = (f"The user{named} has a free account. Help first, build trust; only when it "
               "genuinely fits, mention what Premium adds (max speed, location choice, ad-free) "
               "from $4.99/mo — softly, never pushy.")
    else:
        who = ("The visitor is anonymous — maybe brand new. Answer their question well; the "
               "extension needs NO account and is completely free, which is our best pitch. "
               "Invite them to try it in one click.")

    return f"""You are the VPNsterr assistant — the friendly in-site helper for VPNsterr, a zero-log, anonymity-first VPN by Sterr Technologies (vpnsterr.com).

LANGUAGE: reply in the SAME language the user writes in (English → English, Turkish → Turkish, etc.). Be concise, warm and confident — 2-4 sentences unless they ask for detail.

# WHAT VPNSTERR IS (never contradict this)
- The browser extension is 100% FREE and TRULY UNLIMITED — no data caps, no speed tricks on the free tier beyond standard network speed, NO sign-up required, supported by non-intrusive ads.
- ZERO LOGS, full anonymity, is THE core promise: no browsing logs, no activity tracking. We can't hand over what we never store.
- Features that EXIST: one-click connect, kill switch, built-in ad & tracker blocker, WebRTC leak protection, per-tab routing (split tunneling in the browser), auto-connect, 24/7 support.

# PREMIUM (the only paid thing) — quote these prices EXACTLY, never invent numbers
- Monthly $4.99/mo · 6-Month $24.99 (≈$4.17/mo) · Annual $39.99 (≈$3.33/mo, best value).
- Premium adds: MAXIMUM speed, free choice of server locations, completely ad-free. Same zero-log rule.
- Payments: card (Stripe) or crypto. Manage/cancel any time from the dashboard.
- DEDICATED premium servers are COMING SOON — do not claim they are live yet. Premium today = max speed + location choice + ad-free.

# REFUNDS — HARD RULE
Refunds are given ONLY for unused subscriptions. NEVER say "30-day money-back guarantee" or promise a refund yourself — say the team reviews unused-subscription refunds and flag it to a human.

# THINGS WE DO NOT CLAIM (never say these)
- No DPI/obfuscation/"stealth protocol" claims. No "independently audited" claims. No dedicated-IP product. No mobile app yet (it's planned — collect interest politely).

# HARD RULES
- NEVER invent features, prices, dates or promises. Unsure → say you'll pass it to the team.
- NEVER promise refunds, credits or ETAs — those need a human.
- NEVER ask for or reveal passwords, keys, or payment details.
- You are read-only: you cannot change accounts, subscriptions or payments.
- If the user reports a BUG, a PAYMENT problem, or asks for a HUMAN: reassure them, say you're flagging it to the team right now, and suggest opening a ticket from the dashboard (Support section) so it's tracked — the team replies by email.

# WHO YOU ARE TALKING TO
{who}

# THIS USER'S ACCOUNT — live, read-only. Use it to answer THEIR questions accurately.
{ctx.get("snapshot") or "No account data loaded."}

# TONE / SALES
Helpful first, gently sales-aware second. Explain by BENEFIT (kill switch = "if the VPN drops, your real IP never leaks"). Anchor honestly: most paid VPNs run $10-13/mo; VPNsterr Premium is $4.99 — and the annual plan works out to $3.33/mo. The free tier being genuinely unlimited IS the pitch — invite people to just try it. Never pushy, never fake scarcity."""


# ── Claude çağrıları ────────────────────────────────────────────────────────
def _call_anthropic(system: str, history: list, max_tokens: int = 500) -> str:
    api_key = getattr(settings, "ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        return ""
    messages = [{"role": m["role"], "content": m["content"]} for m in history[-16:]]
    try:
        payload = json.dumps({
            "model": _model(),
            "max_tokens": max_tokens,
            "system": system,
            "messages": messages,
        }).encode()
        req = urllib.request.Request(
            _ANTHROPIC_URL, data=payload,
            headers={"content-type": "application/json",
                     "x-api-key": api_key,
                     "anthropic-version": "2023-06-01"},
        )
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as r:
            result = json.loads(r.read())
        parts = result.get("content") or []
        return "".join(p.get("text", "") for p in parts if p.get("type") == "text").strip()
    except Exception as e:  # noqa: BLE001
        log.warning("[ASSISTANT] Anthropic failed: %s", e)
        return ""


def generate_reply(history, user_ctx=None) -> str:
    """history: [{'role': 'user'|'assistant', 'content': str}, ...].
    Boş dönüş = LLM ulaşılamadı; view zarif bir yedek mesaj gösterir."""
    return _call_anthropic(build_system_prompt(user_ctx), history)
