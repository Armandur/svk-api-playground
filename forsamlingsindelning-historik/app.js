function escapeHtml(s) {
  return String(s ?? "").replace(/[&<>"']/g, c =>
    ({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"}[c]));
}
// Församlings-strängarna i summary lagras som "namn (kod)" eller
// "fran → till (kod)". Pluck:a ut koden i slutet.
function extractKod(s) {
  return (s.match(/\(([0-9?]+)\)$/) || [])[1];
}
function showBanner(msg, isError = false) {
  const el = document.getElementById("banner");
  el.innerHTML = msg;
  el.className = "banner" + (isError ? " err" : "");
  el.hidden = false;
}

// preferCanvas ger 3-10x snabbare rendering för 1000+ polygoner
const map = L.map("map", { preferCanvas: true }).setView([62.5, 16.0], 5);
L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
  maxZoom: 19,
  attribution: "© OpenStreetMap-bidragsgivare",
}).addTo(map);

// Färgkodning av status
const STATUS_STYLE = {
  pastorat: {
    ny:        { color: "#00554B", weight: 2.5, fillColor: "#00554B", fillOpacity: 0.30 },
    andrad:    { color: "#BC8E4C", weight: 2.2, fillColor: "#BC8E4C", fillOpacity: 0.25 },
    forsvunnen:{ color: "#7D0037", weight: 2.2, fillColor: "#7D0037", fillOpacity: 0.18, dashArray: "5, 4" },
    stabil:    { color: "#7D0037", weight: 0.7, fillColor: "#7D0037", fillOpacity: 0.04 },
  },
  forsamling: {
    ny:        { color: "#00554B", weight: 1.4, fillColor: "#00554B", fillOpacity: 0.25, dashArray: "3, 3" },
    tillagd:   { color: "#00554B", weight: 1.6, fillColor: "#00554B", fillOpacity: 0.30 },
    andrad:    { color: "#BC8E4C", weight: 1.4, fillColor: "#BC8E4C", fillOpacity: 0.20, dashArray: "3, 3" },
    borttagen:   { color: "#7D0037", weight: 1.6, fillColor: "#7D0037", fillOpacity: 0.30 },
    forsvunnen:{ color: "#7D0037", weight: 1.4, fillColor: "#7D0037", fillOpacity: 0.15, dashArray: "3, 3" },
    stabil:    { color: "#6b5f5a", weight: 0.6, fillColor: "#6b5f5a", fillOpacity: 0, dashArray: "2, 3" },
  },
};

// Cache: {år: { pastorat_gj, forsamlingar_gj, forsamlingMap }}
const dataCache = new Map();
// Renderade lager hålls bara för innevarande vy så GC kan släppa gamla
let current = {
  pastorat: null, forsamlingar: null,
  forsvunna_pastorat: null, forsvunna_forsamlingar: null,
};
let summary = null;
let currentYear = null;
let onlyChanges = false;

async function fetchYearData(year) {
  if (dataCache.has(year)) {
    const v = dataCache.get(year);
    return v === null ? null : v;
  }
  try {
    const [pr, fr] = await Promise.all([
      fetch(`data/pastorat_${year}.geojson`, { cache: "force-cache" }),
      fetch(`data/forsamlingar_${year}.geojson`, { cache: "force-cache" }),
    ]);
    if (!pr.ok || !fr.ok) {
      dataCache.set(year, null);
      return null;
    }
    const [pg, fg] = await Promise.all([pr.json(), fr.json()]);
    const forsamlingMap = new Map(
      fg.features.map(f => [f.properties.kod, f.properties.namn])
    );
    const obj = { pastorat_gj: pg, forsamlingar_gj: fg, forsamlingMap };
    dataCache.set(year, obj);
    return obj;
  } catch (e) {
    dataCache.set(year, null);
    showBanner(`<b>Fel:</b> ${escapeHtml(String(e))}`, true);
    return null;
  }
}

function statusMaps(year) {
  // Returnera {pastorat: Map<kod, status>, forsamling: Map<kod, status>}
  const empty = { pastorat: new Map(), forsamling: new Map() };
  const idx = summary.ar.indexOf(year);
  if (idx <= 0) return empty;
  const prev = summary.ar[idx - 1];
  const f = summary.forandringar[`${prev}-${year}`];
  if (!f) return empty;
  const ps = new Map();
  (f.pastorat.nya || []).forEach(x => ps.set(x.kod, "ny"));
  // Pastoratsbildning markeras som "ny" på kartan eftersom strukturen
  // är en nybildning, även om skpkod råkar återanvändas
  (f.pastorat.pastoratsbildning || []).forEach(x => ps.set(x.kod, "ny"));
  (f.pastorat.pastoratsupplosning || []).forEach(x => ps.set(x.kod, "andrad"));
  (f.pastorat.sammansattning || []).forEach(x => {
    if (!ps.has(x.kod)) ps.set(x.kod, "andrad");
  });
  (f.pastorat.namnbyte || []).forEach(x => {
    if (!ps.has(x.kod)) ps.set(x.kod, "andrad");
  });
  // Försvunna gäller på prev-årets features, separat hantering
  const fs = new Map();
  // Församlingsändringar är redan packade som strängar i forsamlingar.{nya,...}
  // Vi har inte koderna direkt - extrahera från strängarna via extractKod.
  (f.forsamlingar.nya || []).forEach(s => {
    const k = extractKod(s); if (k) fs.set(k, "ny");
  });
  // Tillagda/borttagna församlingar: dyker upp i ett pastorats sammansättning
  (f.pastorat.sammansattning || []).forEach(x => {
    (x.tillagda_kod || []).forEach(fk => {
      if (!fs.has(fk)) fs.set(fk, "tillagd");
    });
    (x.borttagna_kod || []).forEach(fk => {
      if (!fs.has(fk)) fs.set(fk, "borttagen");
    });
  });
  (f.forsamlingar.namnbyte || []).forEach(s => {
    const k = extractKod(s); if (k && !fs.has(k)) fs.set(k, "andrad");
  });
  return { pastorat: ps, forsamling: fs };
}

function getYearChanges(year) {
  const idx = summary.ar.indexOf(year);
  if (idx <= 0) return null;
  const prev = summary.ar[idx - 1];
  return { prev, year, f: summary.forandringar[`${prev}-${year}`] };
}

function pastoratStatusHtml(kod, year) {
  const ctx = getYearChanges(year);
  if (!ctx?.f) return "";
  const p = ctx.f.pastorat;
  const find = (arr, key = "kod") => (arr || []).find(x => x[key] === kod);
  const since = ` sedan ${ctx.prev}`;
  let m;
  if ((m = find(p.nya))) return `<div class="popup-status status-ny">Nytt pastorat${since}</div>`;
  if ((m = find(p.pastoratsbildning))) {
    return `<div class="popup-status status-ny">Bildat pastorat${since}</div>` +
      `<div class="popup-meta">Tidigare ${escapeHtml(m.fran)} (FörE)</div>`;
  }
  if ((m = find(p.pastoratsupplosning))) {
    return `<div class="popup-status status-andrad">Pastorat → FörE${since}</div>` +
      `<div class="popup-meta">Tidigare ${escapeHtml(m.fran)}</div>`;
  }
  if ((m = find(p.sammansattning))) {
    const adds = m.tillagda?.length ? `+ ${m.tillagda.map(escapeHtml).join(", ")}` : "";
    const rems = m.borttagna?.length ? `− ${m.borttagna.map(escapeHtml).join(", ")}` : "";
    return `<div class="popup-status status-andrad">Ändrad sammansättning${since}</div>` +
      (adds ? `<div class="popup-meta">${adds}</div>` : "") +
      (rems ? `<div class="popup-meta">${rems}</div>` : "");
  }
  if ((m = find(p.namnbyte))) {
    return `<div class="popup-status status-andrad">Namnbyte${since}</div>` +
      `<div class="popup-meta">Tidigare ${escapeHtml(m.fran)}</div>`;
  }
  // Skpkod-omkodning matchar via kod_till. Ingen strukturell ändring -
  // bara administrativ omkodning av ekonomisk-enhet-koden.
  const omk = (p.skpkod_omkodning || []).find(x => x.kod_till === kod);
  if (omk) {
    return `<div class="popup-status status-omkodning">Skpkod-omkodning${since}</div>` +
      `<div class="popup-meta">Tidigare skpkod ${escapeHtml(omk.kod_fran)} (ingen strukturell ändring)</div>`;
  }
  return "";
}

function forsamlingStatusHtml(kod, year) {
  const ctx = getYearChanges(year);
  if (!ctx?.f) return "";
  const fc = ctx.f.forsamlingar;
  const since = ` sedan ${ctx.prev}`;
  if ((fc.nya || []).some(s => extractKod(s) === kod)) {
    return `<div class="popup-status status-ny">Ny församling${since}</div>`;
  }
  // Tillagd eller borttagen i ett pastorats sammansättning
  for (const x of (ctx.f.pastorat.sammansattning || [])) {
    if ((x.tillagda_kod || []).includes(kod)) {
      return `<div class="popup-status status-ny">Tillagd i ${escapeHtml(x.namn)}${since}</div>`;
    }
    if ((x.borttagna_kod || []).includes(kod)) {
      return `<div class="popup-status status-forsvunnen">Borttagen från ${escapeHtml(x.namn)}${since}</div>`;
    }
  }
  const nb = (fc.namnbyte || []).find(s => extractKod(s) === kod);
  if (nb) {
    const fran = nb.split(" → ")[0];
    return `<div class="popup-status status-andrad">Namnbyte${since}</div>` +
      `<div class="popup-meta">Tidigare ${escapeHtml(fran)}</div>`;
  }
  return "";
}

function pastoratPopup(f, forsamlingMap, year) {
  const p = f.properties;
  const members = (p.forsamlingar_kod || [])
    .map(k => forsamlingMap.get(k) || k)
    .sort();
  const memHtml = members.length
    ? `<div class="popup-members">${members.length} församlingar:<br>` +
      members.map(escapeHtml).join("<br>") + `</div>`
    : "";
  return `<div class="popup-name">${escapeHtml(p.namn)}</div>` +
    `<div class="popup-meta">Kod: ${escapeHtml(p.kod)}</div>` +
    pastoratStatusHtml(p.kod, year) + memHtml;
}

function forsamlingPopup(f, year) {
  const p = f.properties;
  return `<div class="popup-name">${escapeHtml(p.namn)}</div>` +
    `<div class="popup-meta">Kod: ${escapeHtml(p.kod)}</div>` +
    forsamlingStatusHtml(p.kod, year);
}

function zoomToFeature(typ, kod) {
  const layerByTyp = {
    "pastorat": current.pastorat,
    "forsamling": current.forsamlingar,
    "pastorat-forsvunnet": current.forsvunna_pastorat,
    "forsamling-forsvunnen": current.forsvunna_forsamlingar,
  };
  const lyr = layerByTyp[typ];
  if (!lyr) return;
  let target = null;
  lyr.eachLayer(l => {
    if (l.feature?.properties?.kod === kod) target = l;
  });
  if (!target) return;
  // Säkerställ att lagret är synligt
  if (!map.hasLayer(lyr)) lyr.addTo(map);
  const bounds = target.getBounds();
  if (bounds && bounds.isValid()) {
    map.flyToBounds(bounds.pad(0.25), { duration: 0.7, maxZoom: 11 });
    setTimeout(() => target.openPopup(), 750);
  }
}

function buildLayers(year, data, prevData, statuses) {
  // Pastorat-lager med status-baserad styling
  const pastorat = L.geoJSON(data.pastorat_gj, {
    style: f => {
      const s = statuses.pastorat.get(f.properties.kod) || "stabil";
      return STATUS_STYLE.pastorat[s];
    },
    filter: f => {
      if (!onlyChanges) return true;
      return statuses.pastorat.has(f.properties.kod);
    },
    onEachFeature: (f, l) => l.bindPopup(pastoratPopup(f, data.forsamlingMap, year)),
  });
  const forsamlingar = L.geoJSON(data.forsamlingar_gj, {
    style: f => {
      const s = statuses.forsamling.get(f.properties.kod) || "stabil";
      return STATUS_STYLE.forsamling[s];
    },
    filter: f => {
      if (!onlyChanges) return true;
      return statuses.forsamling.has(f.properties.kod);
    },
    onEachFeature: (f, l) => l.bindPopup(forsamlingPopup(f, year)),
  });
  // Försvunna pastorat och församlingar: features från prev som inte
  // finns i curr. De ritas streckade i mörkrött med tooltip om upplösning.
  let forsvunna_pastorat = null, forsvunna_forsamlingar = null;
  if (prevData) {
    // Bygg mapping forsamling_kod → {kod, namn} för curr-året så vi
    // kan visa vart en upplöst pastorats församlingar tagit vägen.
    const forsamlingTillPastorat = new Map();
    data.pastorat_gj.features.forEach(p => {
      (p.properties.forsamlingar_kod || []).forEach(fk => {
        forsamlingTillPastorat.set(fk, {
          kod: p.properties.kod,
          namn: p.properties.namn,
        });
      });
    });
    const currPKoder = new Set(
      data.pastorat_gj.features.map(x => x.properties.kod));
    // Skpkod-omkodningar ska INTE räknas som upplösta - de bytte bara
    // identifier utan strukturell ändring.
    const ctx = getYearChanges(year);
    const omkodadeFran = new Set(
      (ctx?.f?.pastorat?.skpkod_omkodning || []).map(x => x.kod_fran));
    const fp = prevData.pastorat_gj.features.filter(
      x => !currPKoder.has(x.properties.kod)
        && !omkodadeFran.has(x.properties.kod));
    if (fp.length) {
      forsvunna_pastorat = L.geoJSON(
        { type: "FeatureCollection", features: fp },
        {
          style: () => STATUS_STYLE.pastorat.forsvunnen,
          onEachFeature: (f, l) => {
            const oldFKoder = f.properties.forsamlingar_kod || [];
            // Gruppera de gamla församlingarna efter vilket pastorat
            // de hamnade i (curr-året).
            const grupper = new Map();
            oldFKoder.forEach(fk => {
              const dest = forsamlingTillPastorat.get(fk);
              const key = dest?.kod || "?";
              if (!grupper.has(key)) {
                grupper.set(key, {
                  namn: dest?.namn || "Försvunnet",
                  forsamlingar: [],
                });
              }
              grupper.get(key).forsamlingar.push(
                prevData.forsamlingMap.get(fk) || fk);
            });
            const destHtml = grupper.size
              ? Array.from(grupper.values()).map(g =>
                  `<div class="popup-meta"><b>${escapeHtml(g.namn)}</b>: ` +
                  g.forsamlingar.map(escapeHtml).join(", ") + `</div>`
                ).join("")
              : "";
            l.bindPopup(pastoratPopup(f, prevData.forsamlingMap, null) +
              `<div class="popup-status status-forsvunnen">Upplöst ${year}</div>` +
              (destHtml ? `<div class="popup-meta" style="margin-top:4px"><i>Församlingarna ingår nu i:</i></div>` + destHtml : ""));
          },
        });
    }
    const currFKoder = new Set(
      data.forsamlingar_gj.features.map(x => x.properties.kod));
    const ff = prevData.forsamlingar_gj.features.filter(
      x => !currFKoder.has(x.properties.kod));
    if (ff.length) {
      forsvunna_forsamlingar = L.geoJSON(
        { type: "FeatureCollection", features: ff },
        {
          style: () => STATUS_STYLE.forsamling.forsvunnen,
          onEachFeature: (f, l) => {
            l.bindPopup(forsamlingPopup(f, null) +
              `<div class="popup-status status-forsvunnen">Försvann ${year}</div>`);
          },
        });
    }
  }
  return { pastorat, forsamlingar, forsvunna_pastorat, forsvunna_forsamlingar };
}

function writeYearToUrl(year) {
  const u = new URL(location);
  u.searchParams.set("year", year);
  history.replaceState(null, "", u);
}

function readYearFromUrl() {
  const u = new URL(location);
  const y = parseInt(u.searchParams.get("year"), 10);
  return isNaN(y) ? null : y;
}

async function setYear(year) {
  currentYear = year;
  writeYearToUrl(year);
  document.getElementById("year-display").textContent = year;
  document.getElementById("subtitle").textContent =
    `${year} - ${summary?.antal_pastorat_per_ar?.[String(year)] ?? "?"} pastorat`;
  // Rensa befintliga lager
  for (const k of Object.keys(current)) {
    if (current[k]) map.removeLayer(current[k]);
  }
  current = {
    pastorat: null, forsamlingar: null,
    forsvunna_pastorat: null, forsvunna_forsamlingar: null,
  };

  // Hämta innevarande + föregående år parallellt
  const idx = summary.ar.indexOf(year);
  const prev = idx > 0 ? summary.ar[idx - 1] : null;
  const [data, prevData] = await Promise.all([
    fetchYearData(year),
    prev ? fetchYearData(prev) : Promise.resolve(null),
  ]);
  if (!data) {
    showBanner(`Saknar data för ${year}`, true);
    return;
  }

  const statuses = statusMaps(year);
  current = buildLayers(year, data, prevData, statuses);
  applyVisibility();
  renderStats(year);
  renderPastoratChanges(year);
  renderForsamlingChanges(year);

  // Prefetch grannår i bakgrunden så slidern blir snabbare
  if (idx > 0) fetchYearData(summary.ar[idx - 1]);
  if (idx < summary.ar.length - 1) fetchYearData(summary.ar[idx + 1]);
}

function applyVisibility() {
  const showP = document.getElementById("show-pastorat").checked;
  const showF = document.getElementById("show-forsamlingar").checked;
  const set = (lyr, on) => {
    if (!lyr) return;
    if (on) lyr.addTo(map); else map.removeLayer(lyr);
  };
  set(current.forsamlingar, showF);
  set(current.forsvunna_forsamlingar, showF);
  set(current.pastorat, showP);
  set(current.forsvunna_pastorat, showP);
  // Pastorat ovanpå församlingar
  if (showP && current.pastorat) current.pastorat.bringToFront();
  if (showP && current.forsvunna_pastorat) current.forsvunna_pastorat.bringToFront();
}

function renderStats(year) {
  if (!summary) return;
  const total = summary.antal_pastorat_per_ar[String(year)];
  const fcount = summary.antal_forsamlingar_per_ar[String(year)];
  const start = summary.antal_pastorat_per_ar[String(summary.ar[0])];
  const delta = total - start;
  const arrow = delta < 0 ? "↓" : delta > 0 ? "↑" : "=";
  const cls = delta < 0 ? "delta-down" : delta > 0 ? "delta-up" : "";
  document.getElementById("stats").innerHTML =
    `<b>${total}</b> pastorat / <b>${fcount}</b> församlingar ` +
    `<span class="${cls}">${arrow} ${Math.abs(delta)}</span> p sedan ${summary.ar[0]}`;
}

function renderMembersList(items) {
  return items.slice(0, 8).map(escapeHtml).join(", ") +
    (items.length > 8 ? ` … (+${items.length - 8})` : "");
}

function detailsBlock(title, count, body, open = false, cat = "") {
  const cls = cat ? ` class="cat-rubrik ${cat}"` : "";
  return `<details${open ? " open" : ""}${cls}>` +
    `<summary>${escapeHtml(title)} <span class="count">(${count})</span></summary>` +
    `<div>${body}</div></details>`;
}

function renderPastoratChanges(year) {
  const container = document.getElementById("changes-pastorat");
  const idx = summary.ar.indexOf(year);
  if (idx <= 0) {
    container.innerHTML = `<div class="empty">${year} är startår - inget tidigare år att jämföra med.</div>`;
    return;
  }
  const prev = summary.ar[idx - 1];
  const f = summary.forandringar[`${prev}-${year}`];
  if (!f) {
    container.innerHTML = `<div class="empty">Inga förändringar mellan ${prev} och ${year}.</div>`;
    return;
  }
  const p = f.pastorat;
  const totalt = (p.nya?.length || 0) + (p.sammansattning?.length || 0) +
                 (p.forsvunna?.length || 0) + (p.forsvunna_fore?.length || 0) +
                 (p.namnbyte?.length || 0) +
                 (p.pastoratsbildning?.length || 0) + (p.pastoratsupplosning?.length || 0) +
                 (p.skpkod_omkodning?.length || 0);
  const sections = [];

  if (p.nya?.length) {
    const body = `<ul class="changes-list cat-ny">` +
      p.nya.slice(0, 100).map(x =>
        `<li data-typ="pastorat" data-kod="${escapeHtml(x.kod)}"><b>${escapeHtml(x.namn)}</b>` +
        (x.ingaende.length ? `<span class="members">${renderMembersList(x.ingaende)}</span>` : ``) +
        `</li>`).join("") + `</ul>` +
      (p.nya.length > 100 ? `<div class="empty">…och ${p.nya.length - 100} till</div>` : "");
    sections.push(detailsBlock("Nya pastorat", p.nya.length, body, false, "cat-ny"));
  }
  if (p.pastoratsbildning?.length) {
    const body = `<ul class="changes-list cat-bildning">` +
      p.pastoratsbildning.slice(0, 100).map(x =>
        `<li data-typ="pastorat" data-kod="${escapeHtml(x.kod)}"><b>${escapeHtml(x.till)}</b>` +
        `<span class="members">tidigare ${escapeHtml(x.fran)} (församling med egen ekonomi)</span>` +
        (x.ingaende?.length ? `<span class="members">Ingår nu: ${renderMembersList(x.ingaende)}</span>` : ``) +
        `</li>`).join("") + `</ul>` +
      (p.pastoratsbildning.length > 100 ? `<div class="empty">…och ${p.pastoratsbildning.length - 100} till</div>` : "");
    sections.push(detailsBlock("Bildat pastorat", p.pastoratsbildning.length, body, false, "cat-bildning"));
  }
  if (p.pastoratsupplosning?.length) {
    const body = `<ul class="changes-list cat-andrad">` +
      p.pastoratsupplosning.slice(0, 100).map(x =>
        `<li data-typ="pastorat" data-kod="${escapeHtml(x.kod)}"><b>${escapeHtml(x.till)}</b>` +
        `<span class="members">tidigare ${escapeHtml(x.fran)}</span>` +
        `</li>`).join("") + `</ul>`;
    sections.push(detailsBlock("Pastorat sammanslaget till FörE", p.pastoratsupplosning.length, body, false, "cat-andrad"));
  }
  if (p.sammansattning?.length) {
    const body = `<ul class="changes-list cat-andrad">` +
      p.sammansattning.slice(0, 100).map(x => {
        const adds = x.tillagda.length ? `+ ${renderMembersList(x.tillagda)}` : "";
        const rems = x.borttagna.length ? `− ${renderMembersList(x.borttagna)}` : "";
        return `<li data-typ="pastorat" data-kod="${escapeHtml(x.kod)}"><b>${escapeHtml(x.namn)}</b>` +
          (adds ? `<span class="members">${escapeHtml(adds)}</span>` : "") +
          (rems ? `<span class="members">${escapeHtml(rems)}</span>` : "") +
          `</li>`;
      }).join("") + `</ul>` +
      (p.sammansattning.length > 100 ? `<div class="empty">…och ${p.sammansattning.length - 100} till</div>` : "");
    sections.push(detailsBlock("Ändrad sammansättning", p.sammansattning.length, body, false, "cat-andrad"));
  }
  if (p.forsvunna?.length) {
    const body = `<ul class="changes-list cat-forsvunnen">` +
      p.forsvunna.slice(0, 100).map(x =>
        `<li data-typ="pastorat-forsvunnet" data-kod="${escapeHtml(x.kod)}"><b>${escapeHtml(x.namn)}</b>` +
        (x.ingaende.length ? `<span class="members">${renderMembersList(x.ingaende)}</span>` : ``) +
        `</li>`).join("") + `</ul>`;
    sections.push(detailsBlock("Upplösta pastorat", p.forsvunna.length, body, false, "cat-forsvunnen"));
  }
  if (p.forsvunna_fore?.length) {
    const body = `<ul class="changes-list cat-forsvunnen">` +
      p.forsvunna_fore.slice(0, 100).map(x =>
        `<li data-typ="pastorat-forsvunnet" data-kod="${escapeHtml(x.kod)}"><b>${escapeHtml(x.namn)}</b>` +
        `<span class="members">FörE upphör - inkorporeras i annat pastorat</span>` +
        `</li>`).join("") + `</ul>` +
      (p.forsvunna_fore.length > 100 ? `<div class="empty">…och ${p.forsvunna_fore.length - 100} till</div>` : "");
    sections.push(detailsBlock("FörE upphör (församling med egen ekonomi)", p.forsvunna_fore.length, body, false, "cat-forsvunnen"));
  }
  if (p.namnbyte?.length) {
    const body = `<ul class="changes-list cat-andrad">` +
      p.namnbyte.slice(0, 100).map(x =>
        `<li data-typ="pastorat" data-kod="${escapeHtml(x.kod)}">${escapeHtml(x.fran)} → <b>${escapeHtml(x.till)}</b></li>`).join("") +
      `</ul>`;
    sections.push(detailsBlock("Namnbyte", p.namnbyte.length, body, false, "cat-andrad"));
  }
  if (p.skpkod_omkodning?.length) {
    const body = `<ul class="changes-list cat-omkodning">` +
      p.skpkod_omkodning.slice(0, 100).map(x =>
        `<li data-typ="pastorat" data-kod="${escapeHtml(x.kod_till)}"><b>${escapeHtml(x.namn)}</b>` +
        `<span class="members">Skpkod ${escapeHtml(x.kod_fran)} → ${escapeHtml(x.kod_till)} (ingen strukturell ändring)</span>` +
        `</li>`).join("") + `</ul>` +
      (p.skpkod_omkodning.length > 100 ? `<div class="empty">…och ${p.skpkod_omkodning.length - 100} till</div>` : "");
    sections.push(detailsBlock("Skpkod-omkodning", p.skpkod_omkodning.length, body, false, "cat-omkodning"));
  }
  // Wrap allt i ett topnivå-<details open> så hela sektionen kan vikas
  const inner = sections.join("");
  container.innerHTML = inner
    ? `<details open class="top-section">` +
      `<summary>Pastorat ${prev} → ${year} ` +
      `<span class="count">(${totalt})</span></summary>` +
      `<div>${inner}</div></details>`
    : `<div class="empty">Inga pastoratsförändringar.</div>`;
}

function renderForsamlingChanges(year) {
  const container = document.getElementById("changes-forsamlingar");
  const idx = summary.ar.indexOf(year);
  if (idx <= 0) { container.innerHTML = ""; return; }
  const prev = summary.ar[idx - 1];
  const f = summary.forandringar[`${prev}-${year}`];
  if (!f) { container.innerHTML = ""; return; }
  const fc = f.forsamlingar;
  const totalt = (fc.nya?.length || 0) + (fc.forsvunna?.length || 0) + (fc.namnbyte?.length || 0);
  const sections = [];
  const renderItems = (items, cat, max = 100, typ = "forsamling", clickable = true) =>
    `<ul class="changes-list ${cat}">${items.slice(0, max).map(n => {
      const kod = clickable ? extractKod(n) : null;
      const attr = kod ? ` data-typ="${typ}" data-kod="${escapeHtml(kod)}"` : "";
      return `<li${attr}>${escapeHtml(n)}</li>`;
    }).join("")}</ul>` +
    (items.length > max ? `<div class="empty">…och ${items.length - max} till</div>` : "");
  if (fc.nya?.length) {
    sections.push(detailsBlock("Nya församlingar", fc.nya.length,
      renderItems(fc.nya, "", 100, "forsamling"), false, "cat-ny"));
  }
  if (fc.forsvunna?.length) {
    sections.push(detailsBlock("Försvunna församlingar", fc.forsvunna.length,
      renderItems(fc.forsvunna, "", 100, "forsamling-forsvunnen"), false, "cat-forsvunnen"));
  }
  if (fc.namnbyte?.length) {
    // Namnbyte-strängar har formen "gammalt → nytt (kod)" - extrahera kod
    sections.push(detailsBlock("Namnbyte", fc.namnbyte.length,
      renderItems(fc.namnbyte, "", 100, "forsamling"), false, "cat-andrad"));
  }
  const inner = sections.join("");
  container.innerHTML = inner
    ? `<details class="top-section">` +
      `<summary>Församlingar ${prev} → ${year} ` +
      `<span class="count">(${totalt})</span></summary>` +
      `<div>${inner}</div></details>`
    : `<div class="empty">Inga församlingsändringar.</div>`;
}

async function init() {
  const r = await fetch("data/summary.json", { cache: "no-store" });
  if (!r.ok) {
    showBanner(`<b>Saknar data.</b> Kör <code>uv run forsamlingsindelning-historik/build_historik.py</code>.`, true);
    return;
  }
  summary = await r.json();
  const slider = document.getElementById("year-slider");
  const minY = summary.ar[0], maxY = summary.ar[summary.ar.length - 1];
  slider.min = minY; slider.max = maxY; slider.value = maxY;
  // Fyll datalist med tick-options för varje år
  const datalist = document.getElementById("year-ticks");
  datalist.innerHTML = summary.ar.map(y => `<option value="${y}"></option>`).join("");
  // Justera tick-bakgrunden så antalet streck matchar år-1 intervall
  const intervals = summary.ar.length - 1;
  document.querySelector(".slider-ticks").style.backgroundSize =
    `calc(100% / ${intervals}) 8px, 100% 8px`;
  slider.addEventListener("input", e => {
    document.getElementById("year-display").textContent = e.target.value;
  });
  slider.addEventListener("change", e => {
    setYear(parseInt(e.target.value, 10));
  });
  document.getElementById("show-pastorat").addEventListener("change", applyVisibility);
  document.getElementById("show-forsamlingar").addEventListener("change", applyVisibility);
  document.getElementById("only-changes").addEventListener("change", e => {
    onlyChanges = e.target.checked;
    if (currentYear !== null) setYear(currentYear);
  });
  // Klick på en rad i listan: zooma till motsvarande feature på kartan
  document.querySelector("aside").addEventListener("click", e => {
    const li = e.target.closest("li[data-kod]");
    if (!li) return;
    zoomToFeature(li.dataset.typ, li.dataset.kod);
  });
  // Drawer-toggle
  const aside = document.getElementById("aside-panel");
  const backdrop = document.getElementById("aside-backdrop");
  const infoBtn = document.getElementById("info-toggle");
  const setDrawer = (open) => {
    aside.classList.toggle("open", open);
    backdrop.classList.toggle("open", open);
    infoBtn.classList.toggle("is-open", open);
    infoBtn.setAttribute("aria-label", open ? "Stäng" : "Visa förändringar");
  };
  infoBtn.addEventListener("click", () =>
    setDrawer(!aside.classList.contains("open")));
  backdrop.addEventListener("click", () => setDrawer(false));

  // Play-knapp - autospelar tidslinjen 2 sekunder per år
  const PLAY_INTERVAL_MS = 2000;
  let playInterval = null;
  const playBtn = document.getElementById("play-toggle");
  const stopPlay = () => {
    if (playInterval) clearInterval(playInterval);
    playInterval = null;
    playBtn.classList.remove("is-playing");
  };
  const startPlay = () => {
    playBtn.classList.add("is-playing");
    playInterval = setInterval(() => {
      const idx = summary.ar.indexOf(currentYear);
      if (idx >= summary.ar.length - 1) { stopPlay(); return; }
      const nextY = summary.ar[idx + 1];
      slider.value = nextY;
      setYear(nextY);
    }, PLAY_INTERVAL_MS);
  };
  playBtn.addEventListener("click", () => {
    if (playInterval) stopPlay(); else startPlay();
  });
  // Användarmanipulering avbryter uppspelning
  slider.addEventListener("change", () => stopPlay(), { capture: true });

  // Initialt år: från ?year=YYYY i URL om giltigt, annars senaste året
  const urlYear = readYearFromUrl();
  const startYear = (urlYear && summary.ar.includes(urlYear)) ? urlYear : maxY;
  slider.value = startYear;
  await setYear(startYear);
}

init();
