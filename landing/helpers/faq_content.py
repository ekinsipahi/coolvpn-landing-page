"""FAQ içeriği — /faq/ sayfası ve FAQPage JSON-LD tek kaynaktan beslenir.

Marka kuralları burada da geçerli: DPI/obfuscation iddiası yok, iade yalnız
KULLANILMAMIŞ abonelik için, "bağımsız denetimden geçtik" denmiyor, ücretsiz
uzantı gerçekten sınırsız ve hesapsız, özel premium sunucular henüz yok.

Cevaplar düz metin (JSON-LD'ye de aynen giriyor); vurgulamak için <b> ve
<a> kullanılabilir, şablon `|safe` ile basıyor.
"""

FAQ_GROUPS = [
    ("Free plan", "emerald", [
        ("Is the VPNsterr extension really free?",
         "Yes. The browser extension is 100% free with no time limit, no data cap "
         "and no credit card. It's funded by non-intrusive ads, which is how we can "
         "keep it genuinely unlimited instead of giving you 500 MB and calling it free."),
        ("Do I need an account to use the free plan?",
         "No. Install it, click connect, and you're browsing. There's no sign-up, no "
         "email and no profile — which also means there is no account for anyone to "
         "link your traffic to."),
        ("What does \"unlimited\" actually mean here?",
         "No data cap, no daily time limit, no connection count limit and no speed "
         "cliff after a hidden threshold. The honest limits of the free plan are: you "
         "share the standard server pool and you don't choose your exit location."),
        ("What's the catch?",
         "Ads, and only ads. We don't sell browsing data, we don't resell your "
         "bandwidth, and we don't turn your device into an exit node for other people. "
         "If you'd rather not see ads, Premium removes them."),
        ("Will the free plan stay free?",
         "That's the plan. The free tier is how most people meet VPNsterr, and the "
         "ad revenue covers its server cost. If that ever changes we'll say so here "
         "rather than quietly adding a cap."),
    ]),

    ("Privacy & logs", "indigo", [
        ("Do you keep logs of what I do?",
         "No. We store no activity logs and no source-IP connection logs — on the free "
         "plan and on Premium. We can't hand over, sell or lose what was never written down."),
        ("What information do you store at all?",
         "For free users: nothing that identifies you — there's no account. For Premium: "
         "your email, your subscription status and payment records our payment providers "
         "require. Never your browsing."),
        ("Are you independently audited?",
         "Not yet, and we won't pretend otherwise. When we commission an audit we'll "
         "publish the actual report here instead of putting a badge on the homepage."),
        ("Where is the company based?",
         "VPNsterr is operated by Sterr Technologies. Legal and abuse requests go to "
         "support@vpnsterr.com — and the answer to \"hand over the browsing logs\" is "
         "that they don't exist."),
        ("Does the extension protect me from WebRTC leaks?",
         "Yes. WebRTC can expose your real IP to any page that asks, straight past the "
         "proxy. We block that by default — see the WebRTC protection page for the detail."),
        ("Does it stop DNS leaks?",
         "Yes. DNS lookups go through the tunnel, so your ISP's resolver doesn't get a "
         "list of every domain you visit."),
        ("Can my ISP see what I'm browsing?",
         "Not the contents. Your ISP sees an encrypted connection to our server; the "
         "sites and pages inside it aren't visible to them."),
        ("Do you sell data to advertisers?",
         "No. The ads on the free plan are served without your browsing history — they "
         "pay for servers, not for a profile of you."),
    ]),

    ("Premium & billing", "fuchsia", [
        ("What do I get with Premium?",
         "Maximum speed with no standard-tier pacing, free choice of server location, "
         "and a completely ad-free experience. The zero-logs rule is identical on both tiers "
         "— privacy is never the upsell."),
        ("How much does Premium cost?",
         "$4.99 per month, $24.99 for six months, or $39.99 for a year. The annual plan "
         "works out at about $3.33 a month."),
        ("Do you have dedicated premium servers yet?",
         "Not yet. We're adding dedicated premium exits and the extension says so plainly "
         "until they're live — we'd rather tell you than dress the shared pool up as "
         "premium infrastructure. Premium's speed, location choice and ad-free experience "
         "are live today."),
        ("How do I pay?",
         "Card via Stripe, or cryptocurrency via NOWPayments. Both activate your plan "
         "within seconds of the payment confirming."),
        ("Can I get a refund?",
         "Yes, on any Premium subscription you haven't used — if you bought it and never "
         "connected, we refund it in full. Once the service has been used, the term runs "
         "to its end. Open a ticket with your order ID and we'll sort it out."),
        ("How do I cancel?",
         "Card subscriptions: \"Manage / cancel subscription\" in your dashboard opens the "
         "secure Stripe portal. Access continues to the end of the period you already paid for."),
        ("I paid with crypto — can I switch to card?",
         "Yes, and you won't lose the days you've already paid for. The card subscription "
         "starts billing only when your crypto period ends. You can also just extend with "
         "more crypto; the time stacks."),
        ("Will my subscription renew automatically?",
         "Card subscriptions renew automatically until you cancel. Crypto payments never "
         "auto-renew — they simply run out, and you top up when you want to."),
        ("Do you offer a free trial of Premium?",
         "The free plan is the trial, and it doesn't expire. If you buy Premium and don't "
         "use it, the unused-subscription refund covers you."),
    ]),

    ("Setup & devices", "sky", [
        ("Which browsers are supported?",
         "Chrome and Chromium-based browsers — Edge, Brave, Opera and Vivaldi included. "
         "The extension installs from the Chrome Web Store."),
        ("How do I turn on Premium in the extension?",
         "Open the extension, hit <b>Sign in</b> and use the same email as your VPNsterr "
         "account. Premium unlocks immediately and the device appears in your dashboard."),
        ("Why does the extension ask me to sign in on the website?",
         "So you never type a password into a browser extension. The extension opens a "
         "sign-in tab on vpnsterr.com and links the device with a one-time code — the same "
         "pattern TV apps use."),
        ("How many devices can I use?",
         "Up to 20 on the annual plan and 10 on monthly and six-month plans. You can see "
         "every linked device in your dashboard and remove any of them with one click."),
        ("Can I remove a device I no longer use?",
         "Yes. Dashboard → Your devices → Revoke. That device drops to the free tier "
         "immediately."),
        ("Is there a desktop or mobile app?",
         "Not yet — the browser extension is what's shipping today. Desktop and mobile "
         "clients are on the roadmap."),
        ("Does the extension protect my whole computer?",
         "No, and no honest browser extension does. It secures your browser's traffic. "
         "Apps outside the browser keep using your normal connection until our desktop "
         "client ships."),
        ("Can I use a different country in each tab?",
         "Yes — that's per-tab routing, and it's something a system-wide VPN structurally "
         "can't do. One tab can exit in Germany while another stays local."),
    ]),

    ("Troubleshooting", "amber", [
        ("A website isn't loading while I'm connected",
         "Try a different location first, then reload the page. Some sites block known "
         "VPN ranges outright. If it keeps happening, open a ticket and tell us the site "
         "and the location you picked."),
        ("I bought Premium but the extension still shows Free",
         "Open the extension and sign in again — the entitlement is re-checked with the "
         "server on every popup open. If it still shows Free after that, open a ticket "
         "with your account email and we'll look at it directly."),
        ("My connection feels slow",
         "On the free plan you share the standard pool, so speed varies with load. "
         "Switching locations usually helps. Premium removes the standard-tier pacing "
         "and lets you pick a nearer exit."),
        ("The extension icon is grey / won't connect",
         "Reload the extension from your browser's extensions page, then reconnect. If "
         "it persists, reinstall it — no account means nothing is lost."),
        ("I forgot my password",
         "Use the password reset link on the sign-in page. If you can't access the email "
         "on the account, write to support@vpnsterr.com from any address and tell us what "
         "happened."),
    ]),

    ("Account & support", "teal", [
        ("How do I contact you?",
         "Three ways: the chat in your dashboard, a support ticket (also in the dashboard, "
         "tracked and answered by email), or support@vpnsterr.com. See the support page for "
         "which one fits."),
        ("How fast do you reply?",
         "The chat answers immediately. Tickets and emails are usually answered within a "
         "few hours, by a person."),
        ("How do I delete my account?",
         "Dashboard → Delete account. We ask you to confirm twice because it's permanent: "
         "your account, devices and subscription record are removed."),
        ("Do you have an affiliate or referral program?",
         "Not yet. If you're interested, write to us — we're gauging demand before "
         "building it."),
    ]),
]


def faq_flat():
    """(question, answer) düzleştirilmiş liste — JSON-LD için."""
    return [(q, a) for _group, _accent, items in FAQ_GROUPS for q, a in items]


def faq_count() -> int:
    return sum(len(items) for _g, _a, items in FAQ_GROUPS)
