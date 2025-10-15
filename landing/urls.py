# landing/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("pricing/", views.pricing, name="pricing"),
    path("payment/", views.payment, name="payment"),
    path("login/", views.login_view, name="login"),
    path("dashboard/", views.dashboard, name="dashboard"),

    # device apis
    path("api/devices/register/", views.device_register, name="device_register"),
    path("api/devices/revoke/", views.device_revoke, name="device_revoke"),


    # Auth/API
    path("auth/google/finish/", views.google_finish, name="google_finish"),
    path("auth/check-email/", views.check_email, name="check_email"),

    # ✅ capture-email burada
    path("api/checkout/capture-email/", views.capture_email, name="capture_email"),
    path("auth/email-upsert-login/", views.email_upsert_login, name="email_upsert_login"),


    # demo crypto gateways
    path("api/checkout/price/",  views.checkout_price, name="checkout_price"),
    path("api/checkout/create/", views.checkout_create, name="checkout_create"),
    path("api/payment/crypto-gateways/", views.crypto_gateways, name="crypto_gateways"),
    path("api/payment/nowpay/reconcile/", views.nowpay_reconcile, name="nowpay_reconcile"),
    path("payment/success/", views.payment_success, name="payment_success"),
    path("api/payment/nowpayments/ipn/", views.nowpayments_ipn, name="nowpayments_ipn"),
    
    path("api/extension/handshake/", views.extension_handshake, name="extension_handshake"),
]


