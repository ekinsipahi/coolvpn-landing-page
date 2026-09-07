# landing/views_support.py
"""Destek yüzeyi: ticket sistemi (dashboard) + köşedeki AI asistan chatbox'ı.

Ticket = kayıtlı, e-postayla yürüyen resmi süreç (girişli kullanıcı).
Asistan = anlık sohbet; anonim ziyaretçi de kullanabilir (session'a bağlanır).
Her LLM cevabı paraya mal olduğu için POST tarafı cache tabanlı hız limitine
takılır; GET (widget poll) serbesttir.
"""
from __future__ import annotations

import json
import logging

from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.db import IntegrityError
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_POST

from .helpers import assistant as brain
from .helpers.mailer import (
    send_assistant_escalation,
    send_ticket_opened_emails,
    send_ticket_user_reply_forward,
)
from .models import (
    AssistantConversation,
    AssistantMessage,
    SupportTicket,
    TicketMessage,
)

logger = logging.getLogger(__name__)

# ============================================================
# Ticket sistemi
# ============================================================
MAX_OPEN_TICKETS = 10       # bir kullanıcının aynı anda açık tutabileceği ticket
TICKET_BODY_MAX = 5000


def support_home(request):
    """/support/ — halka açık destek merkezi.

    Üç kanalı da tek sayfada anlatır: köşedeki anlık sohbet (hesap gerekmez),
    dashboard'daki ticket sistemi (takip numaralı, e-postayla yürür) ve son
    çare olarak support@vpnsterr.com. Girişli kullanıcıya kendi ticket'ları
    da burada gösterilir ki "nereden bakacağım" sorusu hiç doğmasın.
    """
    tickets = []
    if request.user.is_authenticated:
        tickets = list(request.user.tickets.all()[:5])
    return render(request, "landing/support.html", {"tickets": tickets})


@login_required
@require_POST
def ticket_create(request):
    subject = (request.POST.get("subject") or "").strip()[:140]
    category = (request.POST.get("category") or "other").strip()
    body = (request.POST.get("body") or "").strip()[:TICKET_BODY_MAX]
    if not subject or not body:
        return JsonResponse({"ok": False, "error": "subject_and_message_required"}, status=400)
    if category not in dict(SupportTicket.CATEGORY_CHOICES):
        category = "other"
    open_count = request.user.tickets.exclude(status=SupportTicket.STATUS_CLOSED).count()
    if open_count >= MAX_OPEN_TICKETS:
        return JsonResponse({"ok": False, "error": "too_many_open_tickets"}, status=429)

    ticket = None
    for _ in range(5):  # ref çakışması (astronomik olasılık) → yeniden dene
        try:
            ticket = SupportTicket.objects.create(
                ref=SupportTicket.new_ref(), user=request.user,
                subject=subject, category=category,
            )
            break
        except IntegrityError:
            continue
    if ticket is None:
        return JsonResponse({"ok": False, "error": "try_again"}, status=500)

    TicketMessage.objects.create(ticket=ticket, role=TicketMessage.ROLE_USER, body=body)
    send_ticket_opened_emails(ticket, body)
    return JsonResponse({"ok": True, "ref": ticket.ref, "url": f"/support/{ticket.ref}/"})


@login_required
def ticket_detail(request, ref: str):
    ticket = get_object_or_404(SupportTicket, ref=ref, user=request.user)
    if request.method == "POST":
        action = request.POST.get("action") or "reply"
        if action == "close":
            ticket.status = SupportTicket.STATUS_CLOSED
            ticket.save(update_fields=["status", "updated_at"])
            return redirect("ticket_detail", ref=ticket.ref)
        body = (request.POST.get("body") or "").strip()[:TICKET_BODY_MAX]
        if body:
            TicketMessage.objects.create(ticket=ticket, role=TicketMessage.ROLE_USER, body=body)
            # Kullanıcı yazınca ticket yeniden "open"a döner ve operatöre mail düşer.
            ticket.status = SupportTicket.STATUS_OPEN
            ticket.save(update_fields=["status", "updated_at"])
            send_ticket_user_reply_forward(ticket, body)
        return redirect("ticket_detail", ref=ticket.ref)
    return render(request, "landing/ticket_detail.html", {
        "ticket": ticket,
        "thread": ticket.messages.all(),
    })


# ============================================================
# AI asistan chatbox API'si
# ============================================================
_MSG_MAX = 2000
_RATE_PER_HOUR = 30          # oturum başına LLM cevabı
_RATE_PER_HOUR_IP = 90       # aynı IP'den (birden çok sekme/oturum) toplam

_FALLBACK_REPLY = (
    "I couldn't reach the assistant just now — the team has been notified. "
    "If it's urgent, please open a support ticket from your dashboard and "
    "we'll reply by email."
)


def _client_key(request) -> str:
    """Konuşmanın sahibi: girişli kullanıcı id'si ya da anonim session key."""
    if request.user.is_authenticated:
        return f"u{request.user.id}"
    if not request.session.session_key:
        request.session.create()
    return f"s{request.session.session_key}"


def _active_conv(request, create: bool = False):
    qs = AssistantConversation.objects.exclude(status=AssistantConversation.STATUS_CLOSED)
    if request.user.is_authenticated:
        conv = qs.filter(user=request.user).order_by("-updated_at").first()
    else:
        key = request.session.session_key or ""
        conv = qs.filter(session_key=key, user__isnull=True).order_by("-updated_at").first() if key else None
    if conv is None and create:
        if request.user.is_authenticated:
            conv = AssistantConversation.objects.create(user=request.user)
        else:
            if not request.session.session_key:
                request.session.create()
            conv = AssistantConversation.objects.create(session_key=request.session.session_key)
    return conv


def _serialize(conv, mark_seen: bool = False) -> dict:
    if conv is None:
        return {"id": None, "status": "open", "owner_joined": False, "messages": [], "unread": 0}
    unread = conv.user_unread or 0
    # Rozet poll'u unread'i SİLMEZ; sadece widget açıkken (seen=1) temizlenir.
    if mark_seen and unread:
        conv.user_unread = 0
        conv.save(update_fields=["user_unread"])
        unread = 0
    msgs = [
        {"role": m.role, "content": m.content, "created_at": m.created_at.isoformat()}
        for m in conv.messages.all()
    ]
    return {"id": str(conv.id), "status": conv.status,
            "owner_joined": conv.owner_joined, "messages": msgs, "unread": unread}


def _rate_limited(request) -> bool:
    """LLM POST'u için kaba ama etkili saatlik sayaç (cache tabanlı)."""
    who = _client_key(request)
    ip = (request.META.get("HTTP_X_FORWARDED_FOR", "").split(",")[0].strip()
          or request.META.get("REMOTE_ADDR", "") or "?")
    now_h = timezone.now().strftime("%Y%m%d%H")
    k1, k2 = f"asst:{who}:{now_h}", f"asstip:{ip}:{now_h}"
    try:
        c1 = cache.get_or_set(k1, 0, 3700)
        c2 = cache.get_or_set(k2, 0, 3700)
        if c1 >= _RATE_PER_HOUR or c2 >= _RATE_PER_HOUR_IP:
            return True
        cache.incr(k1)
        cache.incr(k2)
    except Exception:  # noqa: BLE001 - cache yoksa limit uygulanamaz, akış sürer
        pass
    return False


@ensure_csrf_cookie
def assistant_api(request):
    """GET → aktif konuşma (?seen=1 widget açık demek). POST → mesaj + AI cevabı.
    @ensure_csrf_cookie: widget'ın ilk GET'i csrftoken çerezini garanti eder,
    POST'lar X-CSRFToken başlığıyla korunur."""
    if request.method == "GET":
        conv = _active_conv(request)
        return JsonResponse(_serialize(conv, mark_seen=request.GET.get("seen") == "1"))
    if request.method != "POST":
        return JsonResponse({"error": "method"}, status=405)

    try:
        data = json.loads(request.body.decode() or "{}")
    except ValueError:
        data = request.POST
    text = (data.get("message") or "").strip()[:_MSG_MAX]
    if not text:
        return JsonResponse({"error": "empty"}, status=400)
    if _rate_limited(request):
        return JsonResponse({"error": "rate_limited",
                             "detail": "Too many messages — please slow down a little."},
                            status=429)

    conv = _active_conv(request, create=True)

    flags = brain.detect_intent(text)
    AssistantMessage.objects.create(
        conversation=conv, role=AssistantMessage.ROLE_USER,
        content=text, intent=",".join(sorted(flags)),
    )

    newly_escalated = False
    if flags:
        conv.add_flags(flags)
        if (flags & brain.ESCALATE_FLAGS) and conv.status != AssistantConversation.STATUS_ESCALATED:
            conv.status = AssistantConversation.STATUS_ESCALATED
            conv.escalated_at = timezone.now()
            newly_escalated = True
    conv.save()
    if newly_escalated:
        who = request.user.email if request.user.is_authenticated else f"anonymous ({conv.session_key[:8]}…)"
        send_assistant_escalation(str(conv.id), who, text, flags & brain.ESCALATE_FLAGS)

    # Operatör devraldıysa AI susar — cevabı insan yazacak.
    if conv.owner_joined:
        return JsonResponse(_serialize(conv, mark_seen=True))

    history = [
        {"role": ("user" if m.role == AssistantMessage.ROLE_USER else "assistant"),
         "content": m.content}
        for m in conv.messages.all()
    ]
    reply = brain.generate_reply(history, brain.build_user_context(request.user)) or _FALLBACK_REPLY
    AssistantMessage.objects.create(
        conversation=conv, role=AssistantMessage.ROLE_ASSISTANT, content=reply,
    )
    conv.save()  # updated_at tazele
    return JsonResponse(_serialize(conv, mark_seen=True))
