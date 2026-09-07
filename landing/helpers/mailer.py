# landing/helpers/mailer.py
"""VPNsterr'in işlem + pazarlama mailleri — Resend üzerinden, noreply@ imzalı.

Tasarım kararları:
- Gönderim HER ZAMAN arka plan thread'inde: bir mail servisi yavaşladı diye
  ödeme/kayıt isteği bekletilmez; hata sadece loglanır.
- RESEND_API_KEY boşsa Django'nun EMAIL_BACKEND'ine düşer (dev'de console) —
  yani geliştirmede mailler terminale basılır, akış hiç değişmez.
- Şablonlar İngilizce ve markalı: mavi→fuşya degrade başlık, .vs paletine
  uyumlu. Tek `_shell` iskeleti; içerikler kısa fonksiyonlarla üretilir.
- Ticket bildirimlerinde operatör mailinin Reply-To'su KULLANICIYA gider:
  operatör gelen kutusundan doğrudan cevap yazabilir.
"""
from __future__ import annotations

import json
import logging
import threading
import urllib.request

from django.conf import settings

log = logging.getLogger(__name__)

_RESEND_URL = "https://api.resend.com/emails"
_TIMEOUT = 15


# ------------------------------------------------------------------ #
# Gönderim çekirdeği
# ------------------------------------------------------------------ #
def _send_now(to: str, subject: str, html: str, text: str = "",
              reply_to: str = "") -> None:
    api_key = getattr(settings, "RESEND_API_KEY", "")
    sender = getattr(settings, "NOREPLY_EMAIL", "VPNsterr <noreply@vpnsterr.com>")
    if api_key:
        payload = {
            "from": sender,
            "to": [to],
            "subject": subject,
            "html": html,
        }
        if text:
            payload["text"] = text
        if reply_to:
            payload["reply_to"] = [reply_to]
        req = urllib.request.Request(
            _RESEND_URL,
            data=json.dumps(payload).encode(),
            # User-Agent ŞART: Resend'in önündeki Cloudflare, urllib'in
            # varsayılan "Python-urllib" imzasını 403 (error 1010) ile kesiyor.
            headers={"Content-Type": "application/json",
                     "Authorization": f"Bearer {api_key}",
                     "User-Agent": "vpnsterr-mailer/1.0 (+https://vpnsterr.com)"},
        )
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as r:
            r.read()
        return
    # Resend yoksa (dev): Django backend'i — console'a düşer, akış görünür kalır.
    from django.core.mail import EmailMultiAlternatives
    msg = EmailMultiAlternatives(subject, text or "(html email)", sender, [to],
                                 reply_to=[reply_to] if reply_to else None)
    msg.attach_alternative(html, "text/html")
    msg.send(fail_silently=True)


def send_email_bg(to: str, subject: str, html: str, text: str = "",
                  reply_to: str = "") -> None:
    """Arka planda gönder; istek yolunu asla bloklama, hatayı logla."""
    if not (to or "").strip():
        return

    def _run():
        from django.db import connections
        try:
            _send_now(to, subject, html, text, reply_to)
        except Exception as e:  # noqa: BLE001 - mail hatası uygulamayı düşürmez
            log.warning("[MAIL] send failed to=%s subject=%r: %s", to, subject, e)
        finally:
            connections.close_all()

    threading.Thread(target=_run, daemon=True).start()


# ------------------------------------------------------------------ #
# Markalı iskelet
# ------------------------------------------------------------------ #
def _shell(preheader: str, body_html: str, footer_note: str = "") -> str:
    site = getattr(settings, "SITE_URL", "https://vpnsterr.com").rstrip("/")
    year_note = footer_note or (
        "You're receiving this because you have a VPNsterr account. "
        "This mailbox isn't monitored — need help? Visit "
        f'<a href="{site}/support/" style="color:#1090c0">vpnsterr.com/support</a> '
        "to chat with us, open a ticket or email the team."
    )
    return f"""<!doctype html>
<html><body style="margin:0;padding:0;background:#f2f6fa;font-family:Inter,-apple-system,Segoe UI,Roboto,Arial,sans-serif">
<span style="display:none!important;visibility:hidden;opacity:0;height:0;width:0;overflow:hidden">{preheader}</span>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f2f6fa;padding:28px 12px">
<tr><td align="center">
  <table role="presentation" width="560" cellpadding="0" cellspacing="0"
         style="max-width:560px;width:100%;background:#ffffff;border-radius:16px;overflow:hidden;border:1px solid #e4ecf3">
    <tr><td style="background:linear-gradient(100deg,#1090c0 0%,#6366f1 55%,#d946ef 100%);padding:22px 28px">
      <a href="{site}" style="text-decoration:none">
        <span style="font-size:20px;font-weight:800;color:#ffffff;letter-spacing:.3px">VPNsterr</span>
      </a>
    </td></tr>
    <tr><td style="padding:30px 28px 8px 28px;color:#0c2233">{body_html}</td></tr>
    <tr><td style="padding:22px 28px 26px 28px">
      <p style="margin:0;font-size:11px;line-height:1.6;color:#7b8ba0">
        {year_note}<br>
        © Sterr Technologies · <a href="{site}/privacy-policy/" style="color:#7b8ba0">Privacy</a> ·
        <a href="{site}/terms/" style="color:#7b8ba0">Terms</a> ·
        <a href="{site}/refund-policy/" style="color:#7b8ba0">Refund policy</a>
      </p>
    </td></tr>
  </table>
</td></tr></table>
</body></html>"""


def _btn(url: str, label: str) -> str:
    return (f'<a href="{url}" style="display:inline-block;padding:12px 26px;border-radius:12px;'
            f'background:linear-gradient(100deg,#1090c0,#6366f1 55%,#d946ef);color:#ffffff;'
            f'font-weight:700;font-size:14px;text-decoration:none">{label}</a>')


def _first_name(user) -> str:
    name = (getattr(user, "first_name", "") or "").strip()
    if name:
        return name
    email = (getattr(user, "email", "") or getattr(user, "username", "") or "")
    return email.split("@")[0] or "there"


# ------------------------------------------------------------------ #
# 1) Hoş geldin — hesap açılınca
# ------------------------------------------------------------------ #
def send_welcome_email(user) -> None:
    site = getattr(settings, "SITE_URL", "https://vpnsterr.com").rstrip("/")
    name = _first_name(user)
    body = f"""
      <h1 style="margin:0 0 6px;font-size:22px;line-height:1.3">Welcome to VPNsterr, {name} 👋</h1>
      <p style="margin:0 0 18px;font-size:14px;line-height:1.7;color:#3b4f63">
        You just joined a VPN that keeps things refreshingly simple:
        <b>zero logs, full anonymity</b> — and a browser extension that's
        <b>100% free and truly unlimited</b>. No caps, no tricks.</p>
      <table role="presentation" cellpadding="0" cellspacing="0" style="margin:0 0 18px">
        <tr><td style="font-size:14px;line-height:2;color:#0c2233">
          🛡️ &nbsp;Zero-log, anonymous browsing — we can't sell what we never store<br>
          ⚡ &nbsp;One-click connect right from your browser<br>
          🚫 &nbsp;Built-in ad &amp; tracker blocking<br>
          🔒 &nbsp;Kill switch + WebRTC leak protection
        </td></tr>
      </table>
      <p style="margin:0 0 22px">{_btn(site + "/vpn-extension/", "Get the free extension")}</p>
      <p style="margin:0 0 8px;font-size:13px;line-height:1.7;color:#3b4f63">
        Want more? <b>Premium</b> unlocks maximum speed, location choice and an
        ad-free experience from <b>$4.99/mo</b> — and if you never use it, we refund it.</p>
      <p style="margin:0;font-size:13px"><a href="{site}/pricing/" style="color:#1090c0;font-weight:600">See Premium plans →</a></p>
    """
    text = (f"Welcome to VPNsterr, {name}!\n\n"
            "Zero logs, full anonymity, and a 100% free unlimited browser extension.\n"
            f"Get the extension: {site}/vpn-extension/\n"
            f"Premium from $4.99/mo: {site}/pricing/\n")
    send_email_bg(user.email, "Welcome to VPNsterr — you're in 🎉",
                  _shell("Zero logs. Free unlimited VPN extension. Welcome aboard.", body), text)


# ------------------------------------------------------------------ #
# 2) Premium aktif — Stripe VEYA kripto ödemesi düşünce
# ------------------------------------------------------------------ #
_PLAN_LABELS = {"monthly": "Monthly", "semiannual": "6-Month", "semi": "6-Month",
                "annual": "Annual", "yearly": "Annual"}


def send_premium_activated_email(user, sub) -> None:
    site = getattr(settings, "SITE_URL", "https://vpnsterr.com").rstrip("/")
    name = _first_name(user)
    plan = _PLAN_LABELS.get((getattr(sub, "plan_key", "") or "").lower(),
                            (getattr(sub, "plan_key", "") or "Premium").title())
    ends = getattr(sub, "ends_at", None)
    ends_txt = ends.strftime("%b %d, %Y") if ends else ""
    body = f"""
      <p style="margin:0 0 4px;font-size:13px;font-weight:700;letter-spacing:1.5px;color:#d946ef;text-transform:uppercase">
        Premium unlocked</p>
      <h1 style="margin:0 0 6px;font-size:22px;line-height:1.3">You're Premium now, {name} ⚡</h1>
      <p style="margin:0 0 18px;font-size:14px;line-height:1.7;color:#3b4f63">
        Your <b>VPNsterr Premium — {plan}</b> plan is live{f" and runs until <b>{ends_txt}</b>" if ends_txt else ""}.
        Everything is already unlocked on your account:</p>
      <table role="presentation" cellpadding="0" cellspacing="0" style="margin:0 0 18px">
        <tr><td style="font-size:14px;line-height:2;color:#0c2233">
          🚀 &nbsp;Maximum speed — no standard-tier pacing<br>
          🌍 &nbsp;Free choice of server locations<br>
          ✨ &nbsp;Completely ad-free<br>
          🛡️ &nbsp;Same iron rule as always: zero logs
        </td></tr>
      </table>
      <p style="margin:0 0 10px;font-size:14px;line-height:1.7;color:#3b4f63">
        <b>Activate it in your browser:</b> open the VPNsterr extension, hit
        <i>Sign in</i>, and Premium switches on instantly.</p>
      <p style="margin:0 0 22px">{_btn(site + "/dashboard/", "Open your dashboard")}</p>
      <p style="margin:0;font-size:12px;color:#7b8ba0">Manage or extend your plan any time from the dashboard.</p>
    """
    text = (f"Your VPNsterr Premium ({plan}) is active"
            + (f" until {ends_txt}" if ends_txt else "") + ".\n"
            "Max speed, free location choice, ad-free, zero logs.\n"
            f"Dashboard: {site}/dashboard/\n")
    send_email_bg(user.email, f"⚡ VPNsterr Premium is ACTIVE — welcome to the fast lane",
                  _shell("Your Premium plan just went live. Max speed, ad-free, zero logs.", body), text)


# ------------------------------------------------------------------ #
# 3) Ticket mailleri
# ------------------------------------------------------------------ #
def send_ticket_opened_emails(ticket, first_message: str) -> None:
    """Kullanıcıya alındı onayı + operatöre (SUPPORT_FORWARD_EMAIL) kopya.
    Operatör mailinin Reply-To'su kullanıcı: gelen kutusundan direkt cevap."""
    site = getattr(settings, "SITE_URL", "https://vpnsterr.com").rstrip("/")
    user = ticket.user
    name = _first_name(user)
    snippet = (first_message or "").strip()[:600]

    body_user = f"""
      <h1 style="margin:0 0 6px;font-size:20px;line-height:1.3">We got your ticket, {name} ✅</h1>
      <p style="margin:0 0 14px;font-size:14px;line-height:1.7;color:#3b4f63">
        Your request <b>{ticket.ref}</b> — “{ticket.subject}” — is in the queue.
        We usually reply within a few hours; you'll get an email the moment we do.</p>
      <div style="border:1px solid #e4ecf3;border-radius:12px;padding:14px 16px;margin:0 0 18px;
                  font-size:13px;line-height:1.7;color:#3b4f63;background:#f8fbfd;white-space:pre-wrap">{snippet}</div>
      <p style="margin:0 0 22px">{_btn(site + "/support/" + str(ticket.ref) + "/", "View your ticket")}</p>
    """
    send_email_bg(user.email, f"[{ticket.ref}] We received your support request",
                  _shell(f"Ticket {ticket.ref} is open — we'll reply by email.", body_user))

    admin_to = getattr(settings, "SUPPORT_FORWARD_EMAIL", "")
    if admin_to:
        body_admin = f"""
          <h1 style="margin:0 0 6px;font-size:18px">🎫 New ticket {ticket.ref}</h1>
          <p style="margin:0 0 10px;font-size:13px;color:#3b4f63">
            <b>{user.email}</b> · {ticket.get_category_display()} · {ticket.subject}</p>
          <div style="border:1px solid #e4ecf3;border-radius:12px;padding:14px 16px;margin:0 0 16px;
                      font-size:13px;line-height:1.7;color:#0c2233;background:#f8fbfd;white-space:pre-wrap">{snippet}</div>
          <p style="margin:0 0 6px;font-size:12px;color:#7b8ba0">Reply to THIS email to answer the user directly
            (Reply-To is set), or manage it in the admin.</p>
          <p style="margin:0">{_btn(site + "/admin/landing/supportticket/", "Open in admin")}</p>
        """
        send_email_bg(admin_to, f"🎫 [{ticket.ref}] {ticket.subject} — {user.email}",
                      _shell("New support ticket", body_admin,
                             footer_note="Internal notification."),
                      reply_to=user.email)


def send_ticket_replied_email(ticket, reply_body: str) -> None:
    """Ekip cevap yazınca kullanıcıya bildirim."""
    site = getattr(settings, "SITE_URL", "https://vpnsterr.com").rstrip("/")
    name = _first_name(ticket.user)
    snippet = (reply_body or "").strip()[:800]
    body = f"""
      <h1 style="margin:0 0 6px;font-size:20px;line-height:1.3">You've got a reply, {name} 💬</h1>
      <p style="margin:0 0 14px;font-size:14px;line-height:1.7;color:#3b4f63">
        Our team answered your ticket <b>{ticket.ref}</b> — “{ticket.subject}”:</p>
      <div style="border-left:3px solid #1090c0;border-radius:8px;padding:12px 16px;margin:0 0 18px;
                  font-size:13px;line-height:1.7;color:#0c2233;background:#f4f9fc;white-space:pre-wrap">{snippet}</div>
      <p style="margin:0 0 22px">{_btn(site + "/support/" + str(ticket.ref) + "/", "Reply on your ticket")}</p>
    """
    send_email_bg(ticket.user.email, f"[{ticket.ref}] New reply to your support request",
                  _shell("Our team replied to your ticket.", body))


def send_ticket_user_reply_forward(ticket, body_text: str) -> None:
    """Kullanıcı ticket'a yeni mesaj yazınca operatöre haber."""
    site = getattr(settings, "SITE_URL", "https://vpnsterr.com").rstrip("/")
    admin_to = getattr(settings, "SUPPORT_FORWARD_EMAIL", "")
    if not admin_to:
        return
    snippet = (body_text or "").strip()[:800]
    body = f"""
      <h1 style="margin:0 0 6px;font-size:18px">💬 {ticket.user.email} replied on {ticket.ref}</h1>
      <div style="border:1px solid #e4ecf3;border-radius:12px;padding:14px 16px;margin:12px 0 16px;
                  font-size:13px;line-height:1.7;color:#0c2233;background:#f8fbfd;white-space:pre-wrap">{snippet}</div>
      <p style="margin:0">{_btn(site + "/admin/landing/supportticket/", "Open in admin")}</p>
    """
    send_email_bg(admin_to, f"💬 [{ticket.ref}] user replied — {ticket.subject}",
                  _shell("User replied on a ticket", body, footer_note="Internal notification."),
                  reply_to=ticket.user.email)


# ------------------------------------------------------------------ #
# 4) Asistan yükseltmesi — operatöre anlık haber
# ------------------------------------------------------------------ #
def send_assistant_escalation(conv_id: str, who: str, last_text: str, flags) -> None:
    site = getattr(settings, "SITE_URL", "https://vpnsterr.com").rstrip("/")
    admin_to = getattr(settings, "SUPPORT_FORWARD_EMAIL", "")
    if not admin_to:
        return
    tag = ", ".join(sorted(flags)).upper() if flags else "ESCALATED"
    body = f"""
      <h1 style="margin:0 0 6px;font-size:18px">🤖 Assistant escalation · {tag}</h1>
      <p style="margin:0 0 10px;font-size:13px;color:#3b4f63">From: <b>{who}</b></p>
      <div style="border:1px solid #e4ecf3;border-radius:12px;padding:14px 16px;margin:0 0 16px;
                  font-size:13px;line-height:1.7;color:#0c2233;background:#f8fbfd;white-space:pre-wrap">{(last_text or '')[:600]}</div>
      <p style="margin:0;font-size:12px;color:#7b8ba0">Conversation: {conv_id}</p>
      <p style="margin:10px 0 0">{_btn(site + "/admin/landing/assistantconversation/", "Open live inbox")}</p>
    """
    send_email_bg(admin_to, f"🤖 Assistant escalation [{tag}] — {who}",
                  _shell("A chat needs a human.", body, footer_note="Internal notification."))
