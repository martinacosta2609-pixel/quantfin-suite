// Global Navigation Bar for QuantFin Cloud Suite
(function() {
  function injectNavBar() {
    if (document.getElementById('quantfin-global-bar')) return;

    const currentPath = window.location.pathname;

    const nav = document.createElement('div');
    nav.id = 'quantfin-global-bar';
    nav.style.cssText = `
      position: fixed;
      top: 0;
      left: 0;
      right: 0;
      height: 38px;
      background: rgba(7, 11, 20, 0.94);
      backdrop-filter: blur(10px);
      -webkit-backdrop-filter: blur(10px);
      border-bottom: 1px solid rgba(51, 65, 85, 0.7);
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 0 16px;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Inter", monospace, sans-serif;
      font-size: 12px;
      z-index: 999999;
      color: #94a3b8;
      box-sizing: border-box;
      gap: 8px;
    `;

    // Inject mobile scrollbar helper
    if (!document.getElementById('quantfin-global-bar-style')) {
      const styleTag = document.createElement('style');
      styleTag.id = 'quantfin-global-bar-style';
      styleTag.textContent = `
        #quantfin-global-bar .quantfin-nav-scroll::-webkit-scrollbar { display: none; }
        @media (max-width: 640px) {
          #quantfin-global-bar {
            padding: 0 8px !important;
            gap: 6px !important;
          }
        }
      `;
      document.head.appendChild(styleTag);
    }

    const left = document.createElement('div');
    left.style.cssText = 'display: flex; align-items: center; gap: 8px; flex-shrink: 0;';
    left.innerHTML = `
      <a href="/?v=${Date.now()}" style="text-decoration: none; color: #38bdf8; font-weight: 800; font-size: 12px; display: flex; align-items: center; gap: 6px; white-space: nowrap;">
        <span style="display: inline-block; width: 8px; height: 8px; border-radius: 50%; background: #38bdf8; box-shadow: 0 0 8px #38bdf8;"></span>
        ECONOMATO
      </a>
    `;

    const links = [
      { name: '🏠 Hub Central', path: '/' },
      { name: '💵 Bonos', path: '/bonos/' },
      { name: '📈 Valoración', path: '/valoracion/' },
      { name: '📊 Fama-French', path: '/fama/' },
      { name: '🎯 Black-Scholes', path: '/bsm/' },
      { name: '♟️ Teoría de Juegos', path: '/juegos/' }
    ];

    const right = document.createElement('div');
    right.className = 'quantfin-nav-scroll';
    right.style.cssText = 'display: flex; align-items: center; gap: 4px; overflow-x: auto; white-space: nowrap; -webkit-overflow-scrolling: touch; scrollbar-width: none; min-width: 0; flex-shrink: 1;';

    links.forEach(item => {
      const a = document.createElement('a');
      a.href = item.path === '/' ? '/?v=' + Date.now() : item.path;
      a.textContent = item.name;
      const isActive = (item.path === '/' && (currentPath === '/' || currentPath === '')) ||
                       (item.path !== '/' && (currentPath.startsWith(item.path.replace(/\/$/, '')) || (item.path === '/juegos/' && currentPath.startsWith('/apps'))));
      a.style.cssText = `
        text-decoration: none;
        padding: 4px 10px;
        border-radius: 6px;
        color: ${isActive ? '#ffffff' : '#94a3b8'};
        background: ${isActive ? 'rgba(56, 189, 248, 0.2)' : 'transparent'};
        border: 1px solid ${isActive ? 'rgba(56, 189, 248, 0.4)' : 'transparent'};
        font-weight: ${isActive ? '600' : '500'};
        transition: all 0.15s ease;
      `;
      a.onmouseenter = () => {
        if (!isActive) {
          a.style.color = '#ffffff';
          a.style.background = 'rgba(255, 255, 255, 0.06)';
        }
      };
      a.onmouseleave = () => {
        if (!isActive) {
          a.style.color = '#94a3b8';
          a.style.background = 'transparent';
        }
      };
      right.appendChild(a);
    });

    nav.appendChild(left);
    nav.appendChild(right);

    document.body.prepend(nav);
    document.body.style.paddingTop = '38px';
    document.documentElement.style.setProperty('--suite-nav-height', '38px');
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', injectNavBar);
  } else {
    injectNavBar();
  }
})();
