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

function setCount(id, n, warn) {
  const el = document.getElementById(id); if (!el) return;
  el.textContent = n;
  el.className = warn ? (n > 0 ? 'q-badge' : 'q-badge ok') : 'q-badge';
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
