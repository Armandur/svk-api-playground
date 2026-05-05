function hvs(lat1, lng1, lat2, lng2) {
  const R = 6371000, toRad = x => x * Math.PI / 180;
  const dp = toRad(lat2-lat1), dl = toRad(lng2-lng1);
  const a = Math.sin(dp/2)**2 + Math.cos(toRad(lat1))*Math.cos(toRad(lat2))*Math.sin(dl/2)**2;
  return Math.round(2 * R * Math.asin(Math.sqrt(a)));
}

function distColor(m) {
  return m >= 5000 ? '#c62828' : m >= 1000 ? '#e53935' : m >= 500 ? '#f57c00' : '#fbc02d';
}

function fmtDist(m) {
  if (m == null) return '-';
  return m >= 1000 ? (m/1000).toFixed(1)+' km' : m+' m';
}

function setCount(id, n) {
  const el = document.getElementById(id); if (!el) return;
  el.textContent = n;
  el.className = n === 0 ? 'q-badge ok' : 'q-badge';
}

function mapBtn(lat, lng, name) {
  if (lat == null) return '<td class="no-print"></td>';
  const safe = (name||'').replace(/'/g, "\\'").replace(/"/g,'&quot;');
  return `<td class="no-print"><button class="map-btn" onclick="jumpToKBR(${lat},${lng},'${safe}')" title="Visa på karta">&#x2316;</button></td>`;
}

function rows(data, fields) {
  return data.map(r =>
    '<tr><td>' + fields.map(f => {
      const v = r[f]; return v == null ? '-' : v === true ? 'Ja' : v === false ? '' : v;
    }).join('</td><td>') + '</td>' + mapBtn(r.kbr_lat, r.kbr_lng, r.namn) + '</tr>'
  ).join('');
}

function buildQualityNav(pane) {
  // After first build, sections live inside .quality-content
  const container = pane.querySelector('.quality-content') || pane;
  const sections = [...container.querySelectorAll(':scope > .q-section')];
  if (sections.length < 2) return;

  sections.forEach(sec => {
    const badge = sec.querySelector('h2 .q-badge');
    if (badge?.id) sec.id = 'sec-' + badge.id.replace('cnt-', '');
    else if (!sec.id) sec.id = 'sec-' + Math.random().toString(36).slice(2, 7);
  });

  if (pane.classList.contains('quality-with-nav')) {
    // Refresh only: update counts and show/hide links to match section visibility
    const nav = pane.querySelector('.quality-nav');
    if (!nav) return;
    sections.forEach(sec => {
      const link = nav.querySelector(`[data-target="${sec.id}"]`);
      if (!link) return;
      const badge = sec.querySelector('h2 .q-badge');
      link.querySelector('.qnav-count').textContent = badge?.textContent ?? '';
      link.style.display = sec.style.display === 'none' ? 'none' : '';
    });
    return;
  }

  const nav = document.createElement('nav');
  nav.className = 'quality-nav';
  nav.innerHTML = sections.map(sec => {
    const h2 = sec.querySelector('h2');
    const badge = h2?.querySelector('.q-badge');
    const title = h2
      ? [...h2.childNodes].filter(n => n.nodeType === Node.TEXT_NODE).map(n => n.textContent).join('').trim()
      : '';
    const hidden = sec.style.display === 'none' ? ' style="display:none"' : '';
    return `<a class="qnav-link" data-target="${sec.id}"${hidden}>${title}<span class="qnav-count">${badge?.textContent ?? ''}</span></a>`;
  }).join('');

  const content = document.createElement('div');
  content.className = 'quality-content';
  [...pane.children].forEach(child => content.appendChild(child));
  const toggle = document.createElement('button');
  toggle.className = 'qnav-toggle';
  toggle.textContent = 'Gå till avsnitt ▾';
  toggle.addEventListener('click', () => {
    nav.classList.toggle('open');
    toggle.textContent = nav.classList.contains('open') ? 'Gå till avsnitt ▴' : 'Gå till avsnitt ▾';
  });

  pane.appendChild(toggle);
  pane.appendChild(nav);
  pane.appendChild(content);
  pane.classList.add('quality-with-nav');

  nav.querySelectorAll('.qnav-link').forEach(a => {
    a.addEventListener('click', e => {
      e.preventDefault();
      content.querySelector('#' + a.dataset.target)
        ?.scrollIntoView({ behavior: 'smooth', block: 'start' });
      nav.classList.remove('open');
      toggle.textContent = 'Gå till avsnitt ▾';
    });
  });

  content.addEventListener('scroll', () => {
    const top = content.getBoundingClientRect().top;
    let active = null;
    sections.filter(s => s.style.display !== 'none')
      .forEach(sec => { if (sec.getBoundingClientRect().top <= top + 60) active = sec; });
    nav.querySelectorAll('.qnav-link').forEach(a =>
      a.classList.toggle('active', !!active && a.dataset.target === active.id));
  }, { passive: true });
}

function makeSortable(table) {
  const ths = [...table.querySelectorAll('thead th')];
  let col = -1, asc = true;
  ths.forEach((th, ci) => {
    if (th.classList.contains('no-print')) return;
    th.addEventListener('click', () => {
      asc = col === ci ? !asc : true;
      col = ci;
      const tbody = table.querySelector('tbody');
      if (!tbody) return;
      [...tbody.rows].sort((a, b) => {
        const va = (a.cells[ci]?.textContent || '').trim();
        const vb = (b.cells[ci]?.textContent || '').trim();
        const na = parseFloat(va), nb = parseFloat(vb);
        const cmp = (!isNaN(na) && !isNaN(nb)) ? na - nb : va.localeCompare(vb, 'sv');
        return asc ? cmp : -cmp;
      }).forEach(r => tbody.appendChild(r));
      ths.forEach((h, i) => {
        if (h.classList.contains('no-print')) return;
        const base = h.dataset.label || (h.dataset.label = h.textContent.trim());
        h.textContent = base + (i === ci ? (asc ? ' ▲' : ' ▼') : '');
      });
    });
  });
}
