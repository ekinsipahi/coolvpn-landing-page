"""/admin/assistant/ — AI asistanın CANLI operatör gelen kutusu.

Django admin'in satır içi (inline) formu bu iş için yanlış araç: sohbete
cevap yazmak için sayfayı kaydetmek, yeni mesajı görmek için F5'lemek
gerekiyordu. Müşteri beklerken bu yeterince hızlı değil.

Burası iki panelli, kendi kendini tazeleyen bir konsol: solda konuşma
listesi, sağda konuşma ve cevap kutusu. Operatör konuşmayı devralır
(owner_joined → AI susar), AI'ya geri bırakabilir ya da kapatabilir.

Yeni bir müşteri beklemeye başladığında zil çalar ve başlıkta kırmızı
rozet çıkar — sekme arkada dururken kaçırmamak için.
"""
import json

from django.contrib.admin.views.decorators import staff_member_required
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_POST

from .models import AssistantConversation, AssistantMessage

_C = AssistantConversation
_M = AssistantMessage

# Operatör çekildiğinde kullanıcıya düşen not. "Kimse yok" demiyoruz —
# AI geri döndü ve yardıma devam ediyor.
_RESUME_MSG = ("👋 The team member has stepped out — your AI assistant is back "
               "and ready to help. Ask me anything!")


def _who(conv) -> str:
    """Konuşmanın sahibi. Kullanıcı NULL olabilir (anonim oturum)."""
    if conv.user_id and conv.user:
        return conv.user.email or conv.user.get_username()
    return f"anon:{(conv.session_key or '')[:10]}"


def _thread(conv) -> dict:
    return {
        "id": str(conv.id), "user": _who(conv), "status": conv.status,
        "flags": conv.intent_flags, "owner_joined": conv.owner_joined,
        "messages": [{"role": m.role, "content": m.content,
                      "created_at": m.created_at.isoformat()}
                     for m in conv.messages.all()],
    }


@staff_member_required
def assistant_inbox(request):
    return render(request, "admin/assistant_inbox.html",
                  {"title": "AI Asistan — Canlı Gelen Kutusu"})


@staff_member_required
def assistant_inbox_data(request):
    """?conv=<id> → o konuşmanın akışı; parametresiz → AÇIK konuşma listesi."""
    conv_id = (request.GET.get("conv") or "").strip()
    if conv_id:
        conv = (_C.objects.filter(id=conv_id)
                .select_related("user").prefetch_related("messages").first())
        if not conv:
            return JsonResponse({"error": "not_found"}, status=404)
        return JsonResponse(_thread(conv))

    qs = (_C.objects.exclude(status=_C.STATUS_CLOSED)
          .select_related("user").prefetch_related("messages")
          .order_by("-updated_at")[:100])
    convs = []
    for c in qs:
        msgs = list(c.messages.all())
        last = msgs[-1] if msgs else None
        convs.append({
            "id": str(c.id), "user": _who(c), "status": c.status,
            "flags": c.intent_flags, "owner_joined": c.owner_joined,
            "last": (last.content[:90] if last else ""),
            "last_role": (last.role if last else ""),
            # Son yazan kullanıcıysa cevap bekliyor demektir.
            "needs_reply": bool(last and last.role == _M.ROLE_USER),
            "updated_at": c.updated_at.isoformat(),
        })
    return JsonResponse({"conversations": convs,
                         "waiting": sum(1 for c in convs if c["needs_reply"])})


@staff_member_required
@require_POST
def assistant_reply(request):
    """POST {conv, message} → operatör cevabı (devralma).
    POST {conv, action: 'release'|'close'} → AI'ya bırak / kapat."""
    try:
        data = json.loads(request.body or b"{}")
    except Exception:  # noqa: BLE001
        return JsonResponse({"error": "bad_json"}, status=400)

    conv = _C.objects.filter(id=(data.get("conv") or "")).first()
    if not conv:
        return JsonResponse({"error": "not_found"}, status=404)

    action = data.get("action")
    if action == "release":
        conv.owner_joined = False
        conv.status = _C.STATUS_OPEN
        _M.objects.create(conversation=conv, role=_M.ROLE_ASSISTANT,
                          content=_RESUME_MSG)
        conv.user_unread = (conv.user_unread or 0) + 1
        conv.save(update_fields=["owner_joined", "status", "user_unread",
                                 "updated_at"])
        return JsonResponse({"ok": True, "owner_joined": False})

    if action == "close":
        conv.status = _C.STATUS_CLOSED
        conv.save(update_fields=["status", "updated_at"])
        return JsonResponse({"ok": True, "closed": True})

    text = (data.get("message") or "").strip()[:4000]
    if not text:
        return JsonResponse({"error": "empty"}, status=400)
    _M.objects.create(conversation=conv, role=_M.ROLE_OWNER, content=text)
    # İnsan devraldı → AI susar; kullanıcı tarafında rozet + zil için unread.
    conv.owner_joined = True
    conv.user_unread = (conv.user_unread or 0) + 1
    conv.save(update_fields=["owner_joined", "user_unread", "updated_at"])
    conv.refresh_from_db()
    return JsonResponse({"ok": True, **_thread(conv)})
