# CoolVPN Landing

**Django + TailwindCSS + i18n (20 Dil) + SEO (hreflang/canonical/JSON-LD) + Sitemap/Robots + Prod-ready (WhiteNoise/Gunicorn/Nginx)**

Bu proje; çok dilli, SEO odaklı ve hızlı dağıtılabilir bir **landing** iskeletidir. Aşağıdaki rehber sıfırdan kurulumu, geliştirme akışını, çeviri (i18n) süreçlerini ve prod dağıtımı tek dokümanda anlatır.

---

## Özellikler
- **20 dil** desteği (RTL: `ar`, `fa`, `he`, `ur`)
- **SSR SEO**: canonical, hreflang, OpenGraph/Twitter, JSON-LD (Organization + sayfa bazlı Product/FAQ)
- **TailwindCSS** ile modern UI (tek CSS çıktısı)
- **Sitemap** ve **robots.txt**
- **WhiteNoise** ile statik servis; **Gunicorn/Nginx** ile prod dağıtım
- **Cihaz-adaptif CTA** (JS ile “Get it on Android/Chrome/iOS/Firefox”)

---

## Önkoşullar
- **Linux/WSL (Ubuntu önerilir)**
- **Python 3.10+**
- **Node.js 18+** ve **npm**
- **gettext** (i18n derleme için)
- (Prod) **systemd** + **nginx** (önerilir)

> Windows kullanıyorsanız WSL (Ubuntu) ile devam edin.

---

## Hızlı Kurulum (TL;DR)
```bash
# Sistem paketleri
sudo apt update
sudo apt install -y python3-venv python3-dev build-essential nodejs npm gettext

# Proje kökü
cd ~/projects/coolvpn-landing-page

# Python sanal ortam
python3 -m venv .venv
source .venv/bin/activate

# Python bağımlılıkları
pip install -r requirements.txt

# Node bağımlılıkları
npm install

# 404 olmaması için boş JS
mkdir -p static/js
[ -f static/js/app.js ] || echo "// app" > static/js/app.js

# CSS watcher (Terminal 1'de açık kalsın)
npm run dev   # Tailwind: static_src/tw.css -> static/css/app.css (watch)

# Django (Terminal 2)
python manage.py migrate
python manage.py runserver 0.0.0.0:8000
