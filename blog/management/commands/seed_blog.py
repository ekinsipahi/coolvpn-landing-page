"""Blogu kullanılabilir hâle getiren tohum verisi.

    python manage.py seed_blog                # kategoriler + keyword havuzu
    python manage.py seed_blog --with-posts   # + 3 başlangıç yazısı

Idempotent: tekrar çalıştırmak kopya üretmez, mevcut yazıları ezmez.
Keyword'ler docs/seo/raw-keywords.txt'ten okunur; niyet sınıflandırması
docs/seo/keyword-map.md'deki kurallarla aynı basit desenlerle yapılır.
"""
from __future__ import annotations

import re
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from blog.models import BlogCategory, BlogKeyword, BlogPost

CATEGORIES = [
    ("Privacy guides", "privacy-guides", "indigo", 10,
     "How online tracking actually works, and what genuinely stops it."),
    ("VPN basics", "vpn-basics", "sky", 20,
     "Plain-English explanations of VPNs, proxies, encryption and DNS."),
    ("Browser security", "browser-security", "emerald", 30,
     "Chrome, Edge and Firefox: leaks, extensions and hardening that matters."),
    ("Comparisons", "comparisons", "fuchsia", 40,
     "Honest head-to-heads between VPN services, free and paid."),
    ("Product updates", "product-updates", "amber", 50,
     "What we shipped, what broke, and what's next for VPNsterr."),
]

# Niyet sınıflandırması: ilk eşleşen kazanır (sıra önemli).
INTENT_RULES = [
    ("competitor", r"\b(nord|express|surfshark|proton|cyberghost|windscribe|hola|"
                   r"tunnelbear|hotspot ?shield|urban ?vpn|browsec|zenmate|touch ?vpn|"
                   r"betternet|psiphon|setup ?vpn|1 ?click ?vpn)\b"),
    ("buy",        r"\b(buy|price|pricing|cost|cheap|subscription|deal|coupon|discount|"
                   r"purchase|plan)\b"),
    ("free",       r"\bfree\b|\bgratis\b|\bunlimited\b"),
    ("geo",        r"\b(usa?|uk|india|turkey|germany|japan|canada|brazil|russia|china|"
                   r"iran|france|netherlands|australia|korea|indonesia|pakistan|"
                   r"united states|united kingdom)\b"),
    ("commercial", r"\b(best|top|review|vs|compare|comparison|alternative)\b"),
]


def classify(term: str) -> str:
    low = term.lower()
    for intent, pattern in INTENT_RULES:
        if re.search(pattern, low):
            return intent
    return "info"


POSTS = [
    {
        "title": "What “no-logs” actually means (and how to check a VPN isn't lying)",
        "category": "privacy-guides",
        "focus_keyword": "no logs vpn",
        "seo_title": "What “No-Logs VPN” Really Means — And How to Verify It",
        "meta_description": (
            "Most VPNs claim no-logs. Few explain what they still store. Here's exactly "
            "which logs exist, which ones deanonymise you, and how to check the claim."),
        "excerpt": (
            "Almost every VPN says “no logs.” The phrase is unregulated, so it can mean "
            "anything from “we store nothing” to “we keep your IP for 30 days.” Here's how to tell."),
        "keywords": ["no logs vpn", "anonymous vpn", "private vpn", "vpn privacy",
                     "does vpn hide my ip"],
        "body": """
<p>“No-logs” is the most repeated phrase in the VPN industry and one of the least
defined. There is no standards body policing it. A provider can keep your source IP
address, your session timestamps and your bandwidth totals and still print “strict
no-logs policy” on the homepage, because they have quietly decided that only
<em>browsing history</em> counts as a log.</p>

<p>So the useful question is never “do you keep logs?” — everyone answers no. The
useful question is <strong>which specific fields do you store, and for how long?</strong></p>

<h2>The four kinds of logs, ranked by how badly they hurt</h2>

<p>Not all logs are equal. These are the categories that matter, from most to least
dangerous for you:</p>

<ul>
  <li><strong>Activity logs</strong> — the sites and pages you visited. Catastrophic.
      A provider holding these can reconstruct your browsing outright.</li>
  <li><strong>Connection logs with source IP</strong> — your real IP, the exit IP you
      were given, and the timestamps. This is the one that quietly deanonymises people.
      It doesn't record what you read, but combined with a timestamp from any other
      source, it links you to a session.</li>
  <li><strong>Aggregate connection data</strong> — total bytes, session counts, no IPs.
      Mostly harmless; used for capacity planning.</li>
  <li><strong>Account data</strong> — your email and payment record. Unavoidable if you
      pay for something, which is exactly why an anonymous free tier matters.</li>
</ul>

<p>A provider that stores only the third and fourth categories is telling the truth
when it says no-logs. One that stores the second and says no-logs is technically
lying, and it happens constantly.</p>

<h2>Why free VPNs are usually the worst offenders</h2>

<p>Running exit servers costs real money. If a service is free and shows you no ads,
the revenue comes from somewhere, and historically that somewhere has been selling
traffic data or reselling users' bandwidth. Several popular free browser VPNs have
been caught doing precisely that.</p>

<p>This is why <a href="/vpn-extension/">the VPNsterr extension is ad-supported</a>
rather than free-with-an-asterisk. Non-intrusive ads pay for the servers, so we never
need to touch what you browse. It's a boring business model, and boring is the point.</p>

<h2>How to actually check the claim</h2>

<ol>
  <li><strong>Read the privacy policy, not the homepage.</strong> The marketing page
      says no-logs; the policy says what is stored. If they disagree, the policy wins.</li>
  <li><strong>Look for the word “IP.”</strong> Search the policy for it. If your source
      IP is retained for any period, that is a connection log regardless of what the
      banner says.</li>
  <li><strong>Check the retention period.</strong> “We delete logs regularly” is not a
      period. “We do not write them to disk” is.</li>
  <li><strong>Ask what happens under legal request.</strong> A provider cannot hand over
      what was never recorded. That is the entire value of the design.</li>
</ol>

<h2>Our position, stated plainly</h2>

<p>VPNsterr stores no activity logs and no source-IP connection logs — on the free tier
and on Premium alike. The free extension does not even require an account, so there is
no identity to attach a session to in the first place. You can read the specifics on
our <a href="/features/no-logs/">no-logs page</a> and in the
<a href="/privacy-policy/">privacy policy</a>, which is written to be read rather than
to survive a lawsuit.</p>

<p>We do not claim an independent audit, because we have not had one. When we do, we
will link the report here rather than putting a badge on the homepage.</p>
""",
    },
    {
        "title": "VPN vs proxy: which one you actually need in your browser",
        "category": "vpn-basics",
        "focus_keyword": "vpn vs proxy",
        "seo_title": "VPN vs Proxy: Which One Do You Actually Need? (2026)",
        "meta_description": (
            "A proxy moves your traffic. A VPN moves and encrypts it. Here's the real "
            "difference, when a browser proxy is enough, and when it quietly isn't."),
        "excerpt": (
            "People use “proxy” and “VPN” interchangeably. They're not the same thing, "
            "and the difference decides whether your ISP can still see what you're doing."),
        "keywords": ["vpn vs proxy", "proxy extension", "what is a vpn",
                     "browser vpn", "vpn extension"],
        "body": """
<p>Both a proxy and a VPN put a server between you and the site you're visiting. That
shared idea is why the words get mixed up. The difference is what happens to your data
on the way there — and it changes who can read it.</p>

<h2>The short version</h2>

<ul>
  <li>A <strong>proxy</strong> forwards your requests. The destination site sees the
      proxy's IP instead of yours.</li>
  <li>A <strong>VPN</strong> forwards <em>and encrypts</em> your traffic inside a tunnel.
      The destination sees the VPN's IP, and your network — the café Wi-Fi, your ISP,
      your employer — can't read what's inside.</li>
</ul>

<p>So a plain proxy hides you from the website. A VPN hides you from the website
<em>and</em> from everyone standing between you and it.</p>

<h2>Where browser extensions fit</h2>

<p>Here's the part that trips people up. Most “VPN extensions” for Chrome are
technically encrypted proxies: they secure traffic from your browser, over HTTPS, to
the exit server. That's genuinely useful — it's what protects you on public Wi-Fi and
it's what changes the IP a site sees.</p>

<p>What a browser extension does <strong>not</strong> do is cover the rest of your
machine. Your email client, your torrent app, your system updater — those keep using
your normal connection. A full desktop VPN covers everything; an extension covers the
browser. Neither is dishonest, but only one of them is usually being sold as if it were
the other.</p>

<h2>When the browser is genuinely enough</h2>

<p>For most people, most of the time, it is:</p>

<ul>
  <li>You want a different region for a site you're reading.</li>
  <li>You're on hotel or airport Wi-Fi and want your browsing unreadable to the network.</li>
  <li>You want to stop a site tying your visit to your home IP.</li>
  <li>You want <a href="/features/per-tab-routing/">a different exit per tab</a> — which
      a system-wide VPN structurally cannot do.</li>
</ul>

<p>That last one is underrated. A system VPN has exactly one exit at a time. An
extension can route one tab through Germany while another stays local.</p>

<h2>When you need more than the browser</h2>

<p>If you're protecting non-browser traffic, or you need every app on the machine
covered, an extension isn't the right tool and no honest vendor should tell you it is.
That's a desktop or mobile client's job.</p>

<h2>What about DNS and WebRTC?</h2>

<p>Two classic leaks make a "working" proxy useless:</p>

<ul>
  <li><strong>DNS leaks</strong> — your browser asks your ISP's resolver which IP a
      domain maps to. The request itself reveals the domain even if the traffic is
      encrypted.</li>
  <li><strong>WebRTC leaks</strong> — a browser API designed for video calls can expose
      your real local and public IP to any page that asks. It bypasses the proxy entirely.</li>
</ul>

<p>Anything worth installing blocks both. Ours does, and you can read exactly how on the
<a href="/features/webrtc/">WebRTC protection page</a>.</p>

<h2>Practical answer</h2>

<p>If your question is “can the website tell it's me, and can the café see what I'm
reading?” — a good browser VPN extension answers both, free.
<a href="/vpn-extension/">Ours is free and unlimited</a>, with no sign-up. If your
question involves traffic outside the browser, wait for the desktop client.</p>
""",
    },
    {
        "title": "Free VPN extensions: how they make money, and which trade-offs are acceptable",
        "category": "comparisons",
        "focus_keyword": "free vpn extension",
        "seo_title": "Free VPN Extensions: How They Make Money (And Which To Trust)",
        "meta_description": (
            "Servers cost money, so a free VPN is monetised somehow. Here are the five "
            "business models behind free VPN extensions — and which ones cost you privacy."),
        "excerpt": (
            "Every free VPN pays for its servers somehow. There are only five ways to do "
            "it, and three of them are paid for with your data."),
        "keywords": ["free vpn extension", "free vpn for chrome", "unlimited free vpn",
                     "best free vpn extension", "free vpn chrome"],
        "body": """
<p>Bandwidth is not free. A VPN provider pays for servers, transit and abuse handling
every month, per user. So when something is offered free and unlimited, the honest
question isn't “what's the catch?” — it's “which catch?” There are only five answers,
and you can tell a lot about a service by which one it picks.</p>

<h2>1. Selling your browsing data</h2>

<p>The oldest model and the worst. Traffic is logged, packaged and sold to data brokers
or analytics firms. It's directly opposed to the point of a VPN, and it has been
documented repeatedly in popular free extensions. Warning sign: a privacy policy that
mentions "trusted partners" or "aggregated insights."</p>

<h2>2. Reselling your bandwidth</h2>

<p>Your device silently becomes an exit node for someone else's traffic. You are the
proxy. Beyond the bandwidth theft, this is legally dangerous: activity you know nothing
about leaves from your IP address. Warning sign: a "peer-to-peer network" or "community"
clause buried in the terms.</p>

<h2>3. Crippled free tier as a sales funnel</h2>

<p>Perfectly honest, and very common: 500 MB a month, two locations, throttled speed.
The free tier is a demo. Nothing wrong with it — just don't confuse it with a free VPN.
Warning sign: none needed, they tell you the cap upfront.</p>

<h2>4. Advertising</h2>

<p>The service shows ads and uses the revenue to pay for servers. Your traffic isn't the
product; your attention is. It's the same deal as free email or free maps, and it's the
only model on this list that funds genuinely unlimited free usage without touching your
data.</p>

<p>This is <a href="/vpn-extension/">the model we chose</a>. The free tier is unlimited
with no account, funded by non-intrusive ads. <a href="/pricing/">Premium</a> removes
them, adds maximum speed and unlocks location choice. If you never upgrade, that's fine
— the ads already paid for you.</p>

<h2>5. Nothing, because it's abandoned</h2>

<p>An unmaintained extension with an expired certificate and no server budget. It either
doesn't connect or, worse, gets sold to a new owner who applies model 1 or 2 to an
existing install base. Warning sign: last updated two years ago.</p>

<h2>How to check which one you're looking at, in two minutes</h2>

<ol>
  <li><strong>Find the money.</strong> If there's no paid tier and no ads, models 1, 2 or
      5 are the only options left.</li>
  <li><strong>Read the permissions.</strong> A browser VPN needs proxy and host access.
      It does not need your bookmarks, your browsing history API, or your clipboard.</li>
  <li><strong>Search the policy for "third part".</strong> It catches "third party" and
      "third parties" both.</li>
  <li><strong>Check the last update date</strong> on the store listing.</li>
</ol>

<h2>What "unlimited" should mean</h2>

<p>It should mean no data cap, no speed cliff after some hidden threshold, and no
daily connection limit. If a service says unlimited and then throttles you to dial-up
after 2 GB, that's a cap with better marketing.</p>

<p>We publish where our free tier is limited, because it is honest and because you'd
find out anyway: free users share the standard server pool and don't pick their exit
location. Everything else — data, time, connections — is genuinely uncapped. See the
full comparison on our <a href="/best-free-vpn-extension/">best free VPN extensions</a>
roundup, where we put ourselves alongside the alternatives rather than pretending they
don't exist.</p>
""",
    },
]


class Command(BaseCommand):
    help = "Blog kategorilerini, keyword havuzunu ve başlangıç yazılarını oluşturur."

    def add_arguments(self, parser):
        parser.add_argument("--with-posts", action="store_true",
                            help="Başlangıç yazılarını da oluştur")
        parser.add_argument("--keyword-file",
                            default="docs/seo/raw-keywords.txt")

    def handle(self, *args, **opts):
        ok = self.style.SUCCESS

        # 1) Kategoriler
        made = 0
        for name, slug, accent, order, desc in CATEGORIES:
            _, created = BlogCategory.objects.get_or_create(
                slug=slug,
                defaults={"name": name, "accent": accent,
                          "sort_order": order, "description": desc})
            made += created
        self.stdout.write(ok(f"kategoriler: {made} yeni, {BlogCategory.objects.count()} toplam"))

        # 2) Keyword havuzu
        path = Path(settings.BASE_DIR) / opts["keyword_file"]
        if path.exists():
            terms = {t.strip() for t in path.read_text(encoding="utf-8").splitlines()
                     if t.strip() and len(t.strip()) <= 200}
            existing = set(BlogKeyword.objects.values_list("keyword", flat=True))
            new = [BlogKeyword(keyword=t, intent=classify(t))
                   for t in sorted(terms - existing)]
            BlogKeyword.objects.bulk_create(new, batch_size=500)
            self.stdout.write(ok(f"keyword: {len(new)} yeni, "
                                 f"{BlogKeyword.objects.count()} toplam"))
        else:
            self.stdout.write(self.style.WARNING(f"keyword dosyası yok: {path}"))

        # 3) Başlangıç yazıları
        if not opts["with_posts"]:
            self.stdout.write("yazılar atlandı (--with-posts ile ekle)")
            return

        for spec in POSTS:
            if BlogPost.objects.filter(title=spec["title"]).exists():
                self.stdout.write(f"  atlandı (zaten var): {spec['title'][:50]}…")
                continue
            category = BlogCategory.objects.get(slug=spec["category"])
            post = BlogPost.objects.create(
                title=spec["title"], category=category,
                body=spec["body"].strip(), excerpt=spec["excerpt"],
                seo_title=spec["seo_title"], meta_description=spec["meta_description"],
                focus_keyword=spec["focus_keyword"],
                status=BlogPost.STATUS_PUBLISHED, published_at=timezone.now(),
                featured=(spec is POSTS[0]),
            )
            for term in spec["keywords"]:
                kw, _ = BlogKeyword.objects.get_or_create(
                    keyword=term, defaults={"intent": classify(term)})
                post.keywords.add(kw)
            post.save()  # keyword'ler bağlandıktan sonra SEO puanı yeniden hesaplansın
            self.stdout.write(ok(f"  yazı: {post.title[:50]}… (SEO {post.seo_score_cache})"))
