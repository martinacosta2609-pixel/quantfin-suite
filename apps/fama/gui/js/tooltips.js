// Tooltips del glosario y render de la pestaña "Guía de Indicadores".
//
// Uso: cualquier elemento con data-glossary="<clave>" muestra al pasar el cursor qué es, qué mide y
// cómo usar ese indicador. Un data-note opcional agrega una línea "En este análisis" con el valor actual.
// Funciona con contenido dinámico porque usa delegación de eventos sobre document.

function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}

const Tooltips = (() => {
  const SHOW_DELAY_MS = 140;
  const EDGE_PADDING = 12;

  const groupColor = Object.fromEntries(GLOSSARY_GROUPS.map(g => [g.id, g.color]));
  let tip = null;
  let anchor = null;
  let showTimer = null;

  function section(label, text, cls = '') {
    return text ? `<div class="gt-row ${cls}"><span class="gt-label">${label}</span><p>${escapeHtml(text)}</p></div>` : '';
  }

  function render(key, note) {
    const g = GLOSSARY[key];
    if (!g) return '';
    return `
      <div class="gt-head">
        <span class="gt-term" style="color:${groupColor[g.group] || '#06b6d4'}">${escapeHtml(g.term)}</span>
        <span class="gt-name">${escapeHtml(g.name)}</span>
      </div>
      ${section('Qué es', g.what)}
      ${section('Qué mide', g.measures)}
      ${section('Cómo usarlo', g.use, 'gt-use')}
      ${section('Cuidado', g.watch, 'gt-warn')}
      ${section('En este análisis', note, 'gt-note')}`;
  }

  function place(el, mouseX, mouseY) {
    const vw = window.innerWidth;
    const vh = window.innerHeight;
    const rect = el.getBoundingClientRect();
    const tw = tip.offsetWidth;
    const th = tip.offsetHeight;

    const refX = mouseX != null ? mouseX - 18 : rect.left;
    const x = Math.max(EDGE_PADDING, Math.min(refX, vw - tw - EDGE_PADDING));

    // Los elementos altos (tarjetas, gráficos) anclan al cursor; los chicos, al borde del elemento.
    const tall = rect.height > 70 && mouseY != null;
    let y = tall ? mouseY + 18 : rect.bottom + 8;
    if (y + th > vh - EDGE_PADDING) {
      y = (tall ? mouseY - 18 : rect.top - 8) - th;
    }
    y = Math.max(EDGE_PADDING, Math.min(y, vh - th - EDGE_PADDING));

    tip.style.left = `${Math.round(x)}px`;
    tip.style.top = `${Math.round(y)}px`;
  }

  function show(el, mouseX, mouseY) {
    const html = render(el.dataset.glossary, el.dataset.note);
    if (!html) return;
    tip.innerHTML = html;
    tip.classList.add('visible');
    anchor = el;
    el.setAttribute('aria-describedby', 'glossaryTooltip');
    place(el, mouseX, mouseY);
  }

  function hide() {
    clearTimeout(showTimer);
    showTimer = null;
    if (anchor) anchor.removeAttribute('aria-describedby');
    anchor = null;
    if (tip) tip.classList.remove('visible');
  }

  function target(node) {
    return node && node.closest ? node.closest('[data-glossary]') : null;
  }

  function init() {
    tip = document.createElement('div');
    tip.id = 'glossaryTooltip';
    tip.className = 'glossary-tooltip';
    tip.setAttribute('role', 'tooltip');
    document.body.appendChild(tip);

    document.addEventListener('mouseover', e => {
      const el = target(e.target);
      if (el === anchor) return;
      hide();
      if (!el) return;
      const { clientX, clientY } = e;
      showTimer = setTimeout(() => show(el, clientX, clientY), SHOW_DELAY_MS);
    });

    document.addEventListener('mouseout', e => {
      const el = target(e.target);
      if (!el) return;
      const next = target(e.relatedTarget);
      if (next !== el) hide();
    });

    // Un clic (p. ej. abrir un <select>), una tecla Escape o un scroll cierran el tooltip.
    document.addEventListener('mousedown', hide, true);
    document.addEventListener('scroll', hide, true);
    document.addEventListener('keydown', e => { if (e.key === 'Escape') hide(); });

    // Accesibilidad: los campos con foco de teclado también muestran su ayuda.
    document.addEventListener('focusin', e => {
      const el = target(e.target);
      if (el) { hide(); show(el); }
    });
    document.addEventListener('focusout', hide);
  }

  return { init, hide };
})();

// ---------------------------------------------------------------------------
// Pestaña "Guía de Indicadores"
// ---------------------------------------------------------------------------
function renderGuide(query = '') {
  const container = document.getElementById('guideContainer');
  if (!container) return;

  const q = query.trim().toLowerCase();
  const matches = ([, g]) => !q || [g.term, g.name, g.what, g.measures, g.use, g.watch || '']
    .some(text => text.toLowerCase().includes(q));

  const entries = Object.entries(GLOSSARY).filter(matches);
  if (!entries.length) {
    container.innerHTML = `<div class="guide-empty">No hay indicadores que coincidan con “${escapeHtml(query)}”.</div>`;
    return;
  }

  container.innerHTML = GLOSSARY_GROUPS.map(group => {
    const items = entries.filter(([, g]) => g.group === group.id);
    if (!items.length) return '';
    const cards = items.map(([, g]) => `
      <article class="guide-card">
        <header class="guide-card-head">
          <span class="guide-term" style="color:${group.color}">${escapeHtml(g.term)}</span>
          <span class="guide-name">${escapeHtml(g.name)}</span>
        </header>
        <dl>
          <dt>Qué es</dt><dd>${escapeHtml(g.what)}</dd>
          <dt>Qué mide</dt><dd>${escapeHtml(g.measures)}</dd>
          <dt class="use">Cómo usarlo</dt><dd>${escapeHtml(g.use)}</dd>
          ${g.watch ? `<dt class="warn">Cuidado</dt><dd>${escapeHtml(g.watch)}</dd>` : ''}
        </dl>
      </article>`).join('');
    return `
      <section class="guide-group">
        <h3 class="guide-group-title" style="border-color:${group.color}">${group.label}<span>${items.length}</span></h3>
        <div class="guide-grid">${cards}</div>
      </section>`;
  }).join('');
}

document.addEventListener('DOMContentLoaded', () => {
  Tooltips.init();
  renderGuide();
});
