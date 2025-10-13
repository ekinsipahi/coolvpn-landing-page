from django.templatetags.static import static

def list_gateways():
    return [
        {
            "key": "nowpay_any",
            "name": "Crypto — NOWPayments",
            "note": "Coin seçimini ödeme sayfasında yapın (150+ coin)",
            "icon": static("img/nowpayments.svg"),
            "pay_currency": "",  # any
        },
    ]
