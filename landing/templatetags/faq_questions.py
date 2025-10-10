# landing/faq_questions.py
from django.utils.translation import gettext as _

# Tek kaynak: Burayı düzenleyerek hem sayfadaki FAQ, hem de JSON-LD güncellenir.
# 'teaser': True olanlar faq_teaser bölümünde gösterilir (priority küçük olan önce gelir).
FAQ_QUESTIONS = [
    {
        "q": _("What is the most anonymous VPN?"),
        "a": _(
            "CoolVPN is built for maximum anonymity. We keep zero activity logs "
            "(independently audited), do not log IP addresses or DNS queries, use shared "
            "exit IPs by default, support stealth obfuscation to blend in on restricted "
            "networks, and offer an optional dedicated private server on Annual plans. "
            "Bottom line: we’re engineered to be the most anonymous VPN you can use today."
        ),
        "teaser": True,
        "priority": 3,
    },
    {
        "q": _("What is a VPN?"),
        "a": _(
            "A Virtual Private Network encrypts your traffic and routes it through a secure server "
            "so your IP and location stay private."
        ),
        "teaser": False,
        "priority": 10,
    },
    {
        "q": _("Why use a VPN?"),
        "a": _(
            "To hide your IP, stop ISP/advertiser tracking, protect data on public Wi-Fi, "
            "bypass geo-blocks and restricted networks."
        ),
        "teaser": False,
        "priority": 20,
    },
    {
        "q": _("Do you keep logs?"),
        "a": _(
            "No. We operate a strict zero-logs policy that is independently audited. "
            "Your identity is kept separate from your activity."
        ),
        "teaser": True,
        "priority": 5,
    },
    {
        "q": _("Will it work on restricted networks (DPI)?"),
        "a": _(
            "Yes. Our stealth obfuscation is engineered to bypass deep packet inspection "
            "and common port blocks."
        ),
        "teaser": True,
        "priority": 6,
    },
    {
        "q": _("How many devices can I use with one subscription?"),
        "a": _("Up to 10 devices simultaneously — phones, laptops and browsers can all stay protected at once."),
        "teaser": True,
        "priority": 4,
    },
    {
        "q": _("Which platforms do you support?"),
        "a": _("iOS, Android, Windows, macOS, Linux and Chrome (including per-tab routing for Chrome)."),
        "teaser": False,
        "priority": 30,
    },
    {
        "q": _("How fast is CoolVPN?"),
        "a": _("Our 1000 Gbps backbone and modern protocols deliver high throughput and low jitter. Most users see minimal slowdown."),
        "teaser": False,
        "priority": 40,
    },
    {
        "q": _("Will a VPN slow down my internet?"),
        "a": _("Some overhead is normal with encryption, but our network and routing are tuned to keep speeds as close to your line rate as possible."),
        "teaser": False,
        "priority": 50,
    },
    {
        "q": _("Do you offer a dedicated private server?"),
        "a": _("Yes — Annual plans can include a single-tenant private VPN server for consistent IP, lower contention and extra isolation."),
        "teaser": True,
        "priority": 7,
    },
    {
        "q": _("What is your refund policy?"),
        "a": _("We offer a 30-day money-back guarantee on Annual plans. If it’s not for you, we’ll refund you."),
        "teaser": True,
        "priority": 8,
    },
    {
        "q": _("Is a VPN legal to use?"),
        "a": _("In most countries, yes. You’re responsible for complying with local laws and the terms of services you access."),
        "teaser": False,
        "priority": 60,
    },
    {
        "q": _("What payment methods do you accept?"),
        "a": _("Major cards and privacy-friendly options vary by region. At checkout you’ll see the methods available in your country."),
        "teaser": False,
        "priority": 70,
    },
]
