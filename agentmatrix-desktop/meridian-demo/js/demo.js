/* ============================================
   MERIDIAN — Demo JS
   Dark mode toggle + nav highlighting
   ============================================ */

document.addEventListener('DOMContentLoaded', () => {
  // ---- DARK MODE TOGGLE ----
  const toggle = document.getElementById('dark-toggle');
  const icon = toggle?.querySelector('i');
  const html = document.documentElement;

  // Restore saved preference
  const saved = localStorage.getItem('meridian-theme');
  if (saved) {
    html.setAttribute('data-theme', saved);
    updateIcon(saved);
  }

  toggle?.addEventListener('click', () => {
    const current = html.getAttribute('data-theme');
    const next = current === 'dark' ? 'light' : 'dark';
    html.setAttribute('data-theme', next);
    localStorage.setItem('meridian-theme', next);
    updateIcon(next);
  });

  function updateIcon(theme) {
    if (!icon) return;
    icon.className = theme === 'dark' ? 'ti ti-sun' : 'ti ti-moon';
  }

  // ---- NAV ACTIVE HIGHLIGHT ----
  const sections = document.querySelectorAll('.section[id]');
  const navLinks = document.querySelectorAll('.sidebar-nav__link');

  if (sections.length && navLinks.length) {
    const observer = new IntersectionObserver((entries) => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          navLinks.forEach(link => link.classList.remove('active'));
          const active = document.querySelector(`.sidebar-nav__link[href="#${entry.target.id}"]`);
          active?.classList.add('active');
        }
      });
    }, {
      rootMargin: '-20% 0px -60% 0px',
      threshold: 0
    });

    sections.forEach(section => observer.observe(section));
  }
});
