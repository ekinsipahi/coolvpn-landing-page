"""Changelog içeriği — /changelog/ ve JSON-LD tek kaynaktan.

Yeni sürüm eklerken listenin BAŞINA ekle (en yeni üstte). `kind` rozeti
belirler: new | improved | fixed | security.

Kural: burada yalnızca gerçekten sevk edilmiş şeyler yazar. Yol haritası
maddeleri "Coming next" bölümünde ve tarihsiz durur — kullanıcı ikisini
karıştırmasın.
"""

RELEASES = [
    {
        "version": "1.1",
        "date": "2026-09-12",
        "title": "Faster Premium activation, honest server status",
        "entries": [
            ("fixed", "Premium now activates the moment you sign in. The extension "
                      "was caching a free session for up to six hours, so people who "
                      "upgraded kept seeing “Plan active, but this device could not be "
                      "verified” until the cache expired."),
            ("new", "Dedicated premium exits can now be added by our team, and the "
                    "extension tells you honestly when there aren't any yet instead of "
                    "presenting the shared pool as premium infrastructure."),
            ("security", "Premium server addresses are never sent to clients. The "
                         "extension only ever sees the gateway; the real exit is resolved "
                         "server-side, so a paying subscriber cannot extract the IPs."),
            ("new", "Support centre at /support/ — chat, tracked tickets and email, "
                    "with answers to the questions we get most."),
            ("improved", "A 39-question FAQ replaced the placeholder page."),
        ],
    },
    {
        "version": "1.0",
        "date": "2026-09-08",
        "title": "VPNsterr is live on the Chrome Web Store",
        "entries": [
            ("new", "The VPNsterr extension is published: 100% free, genuinely "
                    "unlimited, no sign-up required."),
            ("new", "Premium plans — maximum speed, location choice and an ad-free "
                    "experience — payable by card or cryptocurrency."),
            ("new", "Device management in the dashboard: see every linked device and "
                    "revoke any of them instantly."),
            ("new", "Built-in ad and tracker blocking, kill switch, and WebRTC leak "
                    "protection, all on by default."),
            ("new", "Per-tab routing: a different exit location in each tab, which a "
                    "system-wide VPN can't do."),
        ],
    },
]

# Tarihsiz — söz değil, niyet.
COMING_NEXT = [
    "Dedicated premium server locations",
    "Desktop apps for Windows and macOS",
    "Android and iOS apps",
    "Independent security audit, published in full",
]

KIND_LABELS = {
    "new": ("New", "emerald"),
    "improved": ("Improved", "sky"),
    "fixed": ("Fixed", "amber"),
    "security": ("Security", "fuchsia"),
}


def latest_version() -> str:
    return RELEASES[0]["version"] if RELEASES else ""
