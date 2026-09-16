"""/admin/assistant/ — canlı operatör konsolu.

Bu sayfanın tek işi, müşteri beklerken operatörün onu GÖRMESİ ve
cevaplayabilmesi. Testler o zincirin her halkasını tutuyor: yetki,
listede görünme, cevabın kullanıcıya bildirim olarak düşmesi, ve
AI'nın devralma sırasında susması.
"""
import json

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from landing.models import AssistantConversation, AssistantMessage

User = get_user_model()
_C, _M = AssistantConversation, AssistantMessage


class InboxBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.staff = User.objects.create_superuser(
            username="op", email="op@t.test", password="Pa55!operator")
        cls.customer = User.objects.create_user(
            username="musteri", email="musteri@t.test", password="x")
        cls.conv = _C.objects.create(user=cls.customer, intent_flags="bug,payment")
        _M.objects.create(conversation=cls.conv, role=_M.ROLE_USER,
                          content="VPN bağlanmıyor, param da çekildi")
        cls.closed = _C.objects.create(user=cls.customer, status=_C.STATUS_CLOSED)
        cls.anon = _C.objects.create(user=None, session_key="abc123session")
        _M.objects.create(conversation=cls.anon, role=_M.ROLE_USER, content="selam")

    def setUp(self):
        self.client.force_login(self.staff)

    def data(self, **params):
        return self.client.get(reverse("assistant_inbox_data"), params).json()

    def post(self, payload):
        return self.client.post(reverse("assistant_inbox_reply"),
                                data=json.dumps(payload),
                                content_type="application/json")


class AccessTests(InboxBase):
    def test_page_opens_for_staff(self):
        r = self.client.get(reverse("assistant_inbox"))
        self.assertEqual(r.status_code, 200)
        self.assertIn("Canlı Gelen Kutusu", r.content.decode())

    def test_anonymous_is_redirected(self):
        self.client.logout()
        for name in ("assistant_inbox", "assistant_inbox_data"):
            with self.subTest(name=name):
                self.assertEqual(self.client.get(reverse(name)).status_code, 302)

    def test_a_normal_user_cannot_read_conversations(self):
        """Sohbetler başka müşterilerin özel yazışması: staff olmayan giremez."""
        self.client.force_login(self.customer)
        r = self.client.get(reverse("assistant_inbox_data"))
        self.assertEqual(r.status_code, 302)
        self.assertNotIn("bağlanmıyor", r.content.decode("utf-8", "replace"))

    def test_reply_endpoint_rejects_non_staff(self):
        self.client.force_login(self.customer)
        r = self.post({"conv": str(self.conv.id), "message": "sahte"})
        self.assertEqual(r.status_code, 302)
        self.assertFalse(_M.objects.filter(role=_M.ROLE_OWNER).exists())


class ListTests(InboxBase):
    def test_open_conversations_are_listed_with_waiting_count(self):
        j = self.data()
        ids = [c["id"] for c in j["conversations"]]
        self.assertIn(str(self.conv.id), ids)
        self.assertNotIn(str(self.closed.id), ids, "kapatılmış konuşma listede")
        self.assertEqual(j["waiting"], 2)  # conv + anon, ikisinde de son söz kullanıcıda

    def test_row_carries_what_the_operator_needs(self):
        row = next(c for c in self.data()["conversations"] if c["id"] == str(self.conv.id))
        self.assertEqual(row["user"], "musteri@t.test")
        self.assertEqual(row["flags"], "bug,payment")
        self.assertTrue(row["needs_reply"])
        self.assertEqual(row["last_role"], "user")
        self.assertIn("bağlanmıyor", row["last"])

    def test_anonymous_conversation_does_not_crash_the_list(self):
        row = next(c for c in self.data()["conversations"] if c["id"] == str(self.anon.id))
        self.assertTrue(row["user"].startswith("anon:"))

    def test_thread_returns_the_messages(self):
        j = self.data(conv=str(self.conv.id))
        self.assertEqual(j["user"], "musteri@t.test")
        self.assertEqual([m["role"] for m in j["messages"]], ["user"])

    def test_unknown_conversation_is_404(self):
        r = self.client.get(reverse("assistant_inbox_data"),
                            {"conv": "00000000-0000-0000-0000-000000000000"})
        self.assertEqual(r.status_code, 404)


class ReplyTests(InboxBase):
    def test_operator_reply_takes_over_and_notifies_the_user(self):
        r = self.post({"conv": str(self.conv.id), "message": "Merhaba, bakıyorum."})
        self.assertEqual(r.status_code, 200)
        self.conv.refresh_from_db()
        # AI susmalı ve kullanıcıda rozet/zil için okunmamış sayacı artmalı.
        self.assertTrue(self.conv.owner_joined)
        self.assertEqual(self.conv.user_unread, 1)
        last = self.conv.messages.order_by("created_at").last()
        self.assertEqual(last.role, _M.ROLE_OWNER)
        self.assertEqual(last.content, "Merhaba, bakıyorum.")
        self.assertEqual(r.json()["messages"][-1]["role"], "owner")

    def test_empty_reply_is_rejected(self):
        r = self.post({"conv": str(self.conv.id), "message": "   "})
        self.assertEqual(r.status_code, 400)
        self.assertFalse(_M.objects.filter(role=_M.ROLE_OWNER).exists())

    def test_release_hands_it_back_to_the_ai(self):
        self.post({"conv": str(self.conv.id), "message": "devraldım"})
        r = self.post({"conv": str(self.conv.id), "action": "release"})
        self.assertEqual(r.status_code, 200)
        self.conv.refresh_from_db()
        self.assertFalse(self.conv.owner_joined)
        self.assertEqual(self.conv.status, _C.STATUS_OPEN)
        last = self.conv.messages.order_by("created_at").last()
        self.assertEqual(last.role, _M.ROLE_ASSISTANT)
        # Kullanıcı "kimse yok" sanmasın diye açıklayıcı bir not düşer.
        self.assertIn("assistant is back", last.content)

    def test_close_removes_it_from_the_inbox(self):
        self.post({"conv": str(self.conv.id), "action": "close"})
        self.conv.refresh_from_db()
        self.assertEqual(self.conv.status, _C.STATUS_CLOSED)
        self.assertNotIn(str(self.conv.id),
                         [c["id"] for c in self.data()["conversations"]])

    def test_bad_json_is_handled(self):
        r = self.client.post(reverse("assistant_inbox_reply"), data="{bozuk",
                             content_type="application/json")
        self.assertEqual(r.status_code, 400)

    def test_reply_to_unknown_conversation_is_404(self):
        r = self.post({"conv": "00000000-0000-0000-0000-000000000000", "message": "x"})
        self.assertEqual(r.status_code, 404)


class AdminEntryPointTests(InboxBase):
    def test_dashboard_links_to_the_console(self):
        # Adresi ezbere bilmek zorunda kalmayalım.
        body = self.client.get(reverse("admin:index")).content.decode()
        self.assertIn(reverse("assistant_inbox"), body)
