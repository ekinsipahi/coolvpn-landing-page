(function () {
  const html = document.documentElement;

  function applyTheme(next) {
    if (next === 'dark') {
      html.classList.add('dark');
      html.setAttribute('data-theme', 'dark');
    } else {
      html.classList.remove('dark');
      html.setAttribute('data-theme', 'light');
    }
    try { localStorage.setItem('theme', next); } catch (e) { }
  }
  function toggleTheme() {
    const isDark = html.classList.contains('dark');
    applyTheme(isDark ? 'light' : 'dark');
  }

  // Theme buttons
  const btnDesk = document.getElementById('themeToggle');
  const btnMob = document.getElementById('themeToggleMobile');
  if (btnDesk) btnDesk.addEventListener('click', toggleTheme);
  if (btnMob) btnMob.addEventListener('click', toggleTheme);

  // Generic dropdown toggle
  function bindMenuToggle(btnId, menuId) {
    const btn = document.getElementById(btnId);
    const menu = document.getElementById(menuId);
    if (!btn || !menu) return;

    btn.addEventListener('click', (e) => {
      e.stopPropagation();
      const isHidden = menu.classList.contains('hidden');

      document.querySelectorAll('[id$="Menu"]:not(#mobileMenu)').forEach(m => {
        if (m !== menu) {
          m.classList.add('hidden');
          m.classList.add('opacity-0', 'scale-95');
        }
      });

      if (isHidden) {
        menu.classList.remove('hidden');
        requestAnimationFrame(() => menu.classList.remove('opacity-0', 'scale-95'));
      } else {
        menu.classList.add('opacity-0', 'scale-95');
        setTimeout(() => menu.classList.add('hidden'), 80);
      }
    });
  }

  bindMenuToggle('featBtn', 'featMenu');
  bindMenuToggle('advBtn', 'advMenu');
  bindMenuToggle('prdBtn', 'prdMenu');
  bindMenuToggle('langBtn', 'langMenu');
  bindMenuToggle('userBtn', 'userMenu'); // opsiyonel
  bindMenuToggle('userBtnM', 'userMenuM');


  // Click outside => sadece dropdownları kapat
  document.addEventListener('click', () => {
    document.querySelectorAll('[id$="Menu"]:not(#mobileMenu)').forEach(m => {
      m.classList.add('opacity-0', 'scale-95');
      setTimeout(() => m.classList.add('hidden'), 80);
    });
  });

  // Mobile menu toggle (mobileMenu’yu dış tık kapatmasın)
  const navToggle = document.getElementById('navToggle');
  const mobileMenu = document.getElementById('mobileMenu');
  if (navToggle && mobileMenu) {
    navToggle.addEventListener('click', (e) => {
      e.stopPropagation();
      mobileMenu.classList.toggle('hidden');
    });
    mobileMenu.addEventListener('click', (e) => e.stopPropagation());
  }

  // ---- Language handling ----
  // Default language = 'en' (prefixsiz). Diğer diller prefixli.
  const DEFAULT_LANG = 'en';

  function rewritePathWithLang(currentPath, code) {
    // ^/(xx) veya ^/(xx-YY) prefixini yakala
    const re = /^\/([a-z]{2})(?:-[A-Z]{2})?(?=\/|$)/;

    if (code === DEFAULT_LANG) {
      // en: varsa dil prefixini kaldır
      if (re.test(currentPath)) {
        const cleaned = currentPath.replace(re, '');
        return cleaned || '/';
      }
      return currentPath || '/';
    }

    // en dışı: prefix ekle/değiştir
    if (re.test(currentPath)) {
      // mevcut prefixi yeni dille değiştir
      return currentPath.replace(re, `/${code}`);
    }
    // prefix yoksa başa ekle (SLASH'ı unutma!):
    return `/${code}${currentPath.startsWith('/') ? '' : '/'}${currentPath.replace(/^\//, '') ? '/' + currentPath.replace(/^\//, '') : '/'}`.replace(/\/+$/, '/').replace(/\/{2,}/g, '/');
  }

  // set_language integration + URL rewrite
  const langForm = document.getElementById('langForm');
  const langInput = document.getElementById('langInput');

  async function handleLangClick(e) {
    const a = e.target.closest('a[data-lang]');
    if (!a) return;
    e.preventDefault();

    const code = a.getAttribute('data-lang') || DEFAULT_LANG;
    const loc = window.location;
    const newPath = rewritePathWithLang(loc.pathname, code);
    const nextUrl = newPath + loc.search + loc.hash;

    // Django'ya bildir (cookie/session): next olarak zaten hedef URL'i veriyoruz
    try {
      if (langForm && langInput) {
        const formData = new FormData(langForm);
        formData.set('language', code);
        formData.set('next', nextUrl);
        await fetch(langForm.action, {
          method: 'POST',
          body: formData,
          credentials: 'same-origin',
          headers: { 'X-Requested-With': 'XMLHttpRequest' }
        });
      }
    } catch (err) {
      // sessiz geç
    }

    // URL'i anında değiştir
    window.location.href = nextUrl;
  }

  const langMenu = document.getElementById('langMenu');
  const langMenuMobile = document.getElementById('langMenuMobile');
  if (langMenu) langMenu.addEventListener('click', handleLangClick);
  if (langMenuMobile) langMenuMobile.addEventListener('click', handleLangClick);
})();
