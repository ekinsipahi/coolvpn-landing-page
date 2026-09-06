(function () {
  const html = document.documentElement;

  /* ---------- Theme ---------- */
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
    applyTheme(html.classList.contains('dark') ? 'light' : 'dark');
  }
  const btnDesk = document.getElementById('themeToggle');
  const btnMob = document.getElementById('themeToggleMobile');
  if (btnDesk) btnDesk.addEventListener('click', toggleTheme);
  if (btnMob) btnMob.addEventListener('click', toggleTheme);

  /* ---------- Navbar scroll state ---------- */
  const nav = document.getElementById('siteNav');
  if (nav) {
    const onScroll = () => nav.classList.toggle('is-scrolled', window.scrollY > 8);
    onScroll();
    window.addEventListener('scroll', onScroll, { passive: true });
  }

  /* ---------- Dropdowns ---------- */
  const menus = [];
  function closeMenu(entry) {
    entry.menu.classList.add('hidden-anim');
    entry.btn.setAttribute('aria-expanded', 'false');
    setTimeout(() => entry.menu.classList.add('hidden'), 150);
  }
  function openMenu(entry) {
    menus.forEach(m => { if (m !== entry) closeMenu(m); });
    entry.menu.classList.remove('hidden');
    requestAnimationFrame(() =>
      requestAnimationFrame(() => entry.menu.classList.remove('hidden-anim')));
    entry.btn.setAttribute('aria-expanded', 'true');
  }
  function bindMenuToggle(btnId, menuId) {
    const btn = document.getElementById(btnId);
    const menu = document.getElementById(menuId);
    if (!btn || !menu) return;
    const entry = { btn, menu };
    menus.push(entry);
    btn.addEventListener('click', (e) => {
      e.stopPropagation();
      menu.classList.contains('hidden') ? openMenu(entry) : closeMenu(entry);
    });
    menu.addEventListener('click', (e) => e.stopPropagation());
  }
  bindMenuToggle('featBtn', 'featMenu');
  bindMenuToggle('prdBtn', 'prdMenu');
  bindMenuToggle('langBtn', 'langMenu');
  bindMenuToggle('userBtn', 'userMenu');
  bindMenuToggle('userBtnM', 'userMenuM');

  document.addEventListener('click', () => menus.forEach(closeMenu));
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') menus.forEach(closeMenu);
  });

  /* ---------- Mobile menu ---------- */
  const navToggle = document.getElementById('navToggle');
  const mobileMenu = document.getElementById('mobileMenu');
  if (navToggle && mobileMenu) {
    navToggle.addEventListener('click', (e) => {
      e.stopPropagation();
      const open = mobileMenu.classList.toggle('hidden');
      navToggle.setAttribute('aria-expanded', String(!open));
    });
    mobileMenu.addEventListener('click', (e) => e.stopPropagation());
  }

  /* ---------- Scroll reveal ---------- */
  const revealEls = document.querySelectorAll('.vs-reveal');
  if (revealEls.length && 'IntersectionObserver' in window) {
    const ro = new IntersectionObserver((entries, obs) => {
      entries.forEach(en => {
        if (en.isIntersecting) { en.target.classList.add('in'); obs.unobserve(en.target); }
      });
    }, { threshold: 0.12, rootMargin: '0px 0px -40px 0px' });
    revealEls.forEach(el => ro.observe(el));
  } else {
    revealEls.forEach(el => el.classList.add('in'));
  }

  /* ---------- Language handling ---------- */
  const DEFAULT_LANG = 'en';

  function rewritePathWithLang(currentPath, code) {
    const re = /^\/([a-z]{2})(?:-[A-Z]{2})?(?=\/|$)/;
    if (code === DEFAULT_LANG) {
      if (re.test(currentPath)) {
        const cleaned = currentPath.replace(re, '');
        return cleaned || '/';
      }
      return currentPath || '/';
    }
    if (re.test(currentPath)) return currentPath.replace(re, `/${code}`);
    return `/${code}${currentPath.startsWith('/') ? '' : '/'}${currentPath.replace(/^\//, '') ? '/' + currentPath.replace(/^\//, '') : '/'}`.replace(/\/+$/, '/').replace(/\/{2,}/g, '/');
  }

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
    } catch (err) { /* sessiz geç */ }

    window.location.href = nextUrl;
  }

  const langMenu = document.getElementById('langMenu');
  const langMenuMobile = document.getElementById('langMenuMobile');
  if (langMenu) langMenu.addEventListener('click', handleLangClick);
  if (langMenuMobile) langMenuMobile.addEventListener('click', handleLangClick);
})();
