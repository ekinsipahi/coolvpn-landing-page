# landing/urls.py
from django.urls import path, reverse_lazy
from django.contrib.auth import views as auth_views
from . import views
from django.views.generic import TemplateView


urlpatterns = [
    path("", views.home, name="home"),
    path("pricing/", views.pricing, name="pricing"),

    # SEO landing sayfaları
    path("vpn-extension/", views.vpn_extension, name="vpn_extension"),
    path("free-vpn/", views.free_vpn, name="free_vpn"),
    path("features/<slug:slug>/", views.feature_detail, name="feature_detail"),
    path("best-vpn/", views.best_vpn, name="best_vpn"),
    path("best-free-vpn-extension/", views.best_free_vpn_extension, name="best_free_vpn_extension"),
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
    path("api/extension/auth-token/", views.extension_auth_token, name="extension_auth_token"),
    path("api/extension/login/", views.extension_login, name="extension_login"),
    path("extension/link", views.extension_link, name="extension_link"),
    path("api/extension/link/claim", views.extension_link_claim, name="extension_link_claim"),
    path("api/extension/link/refresh", views.extension_link_refresh, name="extension_link_refresh"),
    path("api/extension/link/revoke", views.extension_link_revoke, name="extension_link_revoke"),
    path("api/extension/logout/", views.extension_logout, name="extension_logout"),
    path("account/delete/", views.account_delete, name="account_delete"),
    
    # Şifre sıfırlama (login sayfasındaki "Forgot password?" buraya gelir)
    path("password-reset/", auth_views.PasswordResetView.as_view(
        template_name="registration/password_reset_form.html",
        email_template_name="registration/password_reset_email.txt",
        subject_template_name="registration/password_reset_subject.txt",
        success_url=reverse_lazy("password_reset_done"),
    ), name="password_reset"),
    path("password-reset/done/", auth_views.PasswordResetDoneView.as_view(
        template_name="registration/password_reset_done.html",
    ), name="password_reset_done"),
    path("password-reset/<uidb64>/<token>/", auth_views.PasswordResetConfirmView.as_view(
        template_name="registration/password_reset_confirm.html",
        success_url=reverse_lazy("password_reset_complete"),
    ), name="password_reset_confirm"),
    path("password-reset/complete/", auth_views.PasswordResetCompleteView.as_view(
        template_name="registration/password_reset_complete.html",
    ), name="password_reset_complete"),

    path("privacy-policy/", views.privacy_policy, name="privacy_policy"),
    path("terms/", views.terms_of_service, name="terms_of_service"),
    path("refund-policy/", views.refund_policy, name="refund_policy"),
    path("acceptable-use/", views.acceptable_use, name="acceptable_use"),
    
    # SEO
    path("robots.txt", TemplateView.as_view(template_name="landing/robots.txt", content_type="text/plain")),
]


