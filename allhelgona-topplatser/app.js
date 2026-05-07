/* Topplatser-leaderboard. Renderar 3000+ rader som en enkel HTML-tabell.
 * Filter och sortering körs på klientsidan. Datat (data/leaderboard.json,
 * ~1.6 MB) hämtas en gång; tabellen byggs om vid varje filter/sort. */
(() => {
  "use strict";

  const $ = (s) => document.querySelector(s);
  const tbody = $("#rows");
  const search = $("#search");
  const stiftFilter = $("#stift-filter");
  const yearFilter = $("#year-filter");
  const status = $("#status");
  const metaSummary = $("#meta-summary");
  const ljusHeader = $("#ljus-header");

  let data = null;
  let filtered = [];
  let activeYear = "total";  // "total" eller "2020".."2025"

  const fmt = (n) => n.toLocaleString("sv-SE");

  /* ---------- Renderering ---------- */

  function buildSparkline(plats, years, activeYearStr) {
    const counts = years.map((y) => plats.ljus[String(y)] || 0);
    const maxLocal = Math.max(...counts) || 1;
    const peakIdx = counts.indexOf(maxLocal);
    const bars = counts.map((c, i) => {
      const h = c === 0 ? 2 : 4 + (c / maxLocal) * 18;
      let cls = c === 0 ? "empty" : "";
      const yr = String(years[i]);
      if (activeYearStr === yr) cls += " active";
      else if (i === peakIdx && c > 0) cls += " peak";
      return `<div class="bar ${cls.trim()}" style="height:${h}px" title="${years[i]}: ${fmt(c)}"></div>`;
    }).join("");
    return `<div class="spark">${bars}</div>`;
  }

  function platsName(plats) {
    return plats.name;
  }

  function displayYear(plats, activeYearStr) {
    // För "total"-vyn: använd senaste året platsen hade ljus.
    if (activeYearStr !== "total") return activeYearStr;
    const lit = Object.keys(plats.ljus).map(Number).sort((a, b) => b - a);
    return String(lit[0] || data.years[data.years.length - 1]);
  }

  function platsSubInfo(plats, activeYearStr) {
    // Stift + ekonomisk enhet (pastorat) + församling, dedupe-ade.
    const yr = displayYear(plats, activeYearStr);
    const yearData = (plats.per_ar || {})[yr] || {};
    const parts = [];
    if (plats.stift) parts.push(plats.stift);
    if (yearData.f) parts.push(yearData.f);
    if (yearData.e && yearData.e !== yearData.f) parts.push(yearData.e);
    return parts.join(" · ") || "—";
  }

  function renderRow(plats, rank, years, activeYearStr) {
    const name = platsName(plats);
    const subInfo = platsSubInfo(plats, activeYearStr);
    const rankCls = rank <= 10 ? "rank top" : "rank";

    const value = activeYearStr === "total"
      ? plats.total
      : (plats.ljus[activeYearStr] || 0);

    return `<tr>
      <td class="${rankCls}">${rank}</td>
      <td class="kyrka">${escapeHtml(name)}</td>
      <td class="stift hide-narrow">${escapeHtml(subInfo)}</td>
      <td>${buildSparkline(plats, years, activeYearStr)}</td>
      <td class="r total">${fmt(value)}</td>
    </tr>`;
  }

  function escapeHtml(s) {
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function render() {
    const years = data.years;

    if (filtered.length === 0) {
      tbody.innerHTML = `<tr><td colspan="5" class="loading">Inga träffar.</td></tr>`;
      status.textContent = "0 platser";
      return;
    }

    const html = filtered.map((k, i) => renderRow(k, i + 1, years, activeYear))
                         .join("");
    tbody.innerHTML = html;

    const totalLjus = activeYear === "total"
      ? filtered.reduce((s, k) => s + k.total, 0)
      : filtered.reduce((s, k) => s + (k.ljus[activeYear] || 0), 0);
    const periodText = activeYear === "total" ? "2020-2025" : activeYear;
    status.textContent =
      `Visar ${fmt(filtered.length)} av ${fmt(data.platser.length)} platser - `
      + `${fmt(totalLjus)} ljus ${periodText}`;
  }

  /* ---------- Filter + sortering ---------- */

  function applyFilters() {
    const q = search.value.trim().toLowerCase();
    const stift = stiftFilter.value;
    activeYear = yearFilter.value;
    ljusHeader.textContent =
      activeYear === "total" ? "Ljus 2020-2025" : `Ljus ${activeYear}`;

    filtered = data.platser.filter((k) => {
      if (stift && (k.stift || "") !== stift) return false;
      if (q) {
        const name = platsName(k).toLowerCase();
        const sub = platsSubInfo(k, activeYear).toLowerCase();
        if (!name.includes(q) && !sub.includes(q)) return false;
      }
      return true;
    });

    if (activeYear === "total") {
      filtered.sort((a, b) => b.total - a.total);
    } else {
      filtered.sort((a, b) =>
        (b.ljus[activeYear] || 0) - (a.ljus[activeYear] || 0));
      // Filtrera bort platser som inte hade några ljus alls valt år
      filtered = filtered.filter((k) => (k.ljus[activeYear] || 0) > 0);
    }

    render();
  }

  /* ---------- Init ---------- */

  fetch("data/leaderboard.json")
    .then((r) => r.json())
    .then((d) => {
      data = d;

      // Bygg stift-filter (källa: shapefile via point-in-polygon)
      const stifts = new Set();
      for (const k of d.platser) {
        if (k.stift) stifts.add(k.stift);
      }
      [...stifts].sort((a, b) => a.localeCompare(b, "sv")).forEach((s) => {
        const opt = document.createElement("option");
        opt.value = s;
        opt.textContent = s;
        stiftFilter.appendChild(opt);
      });

      // Bygg år-väljare
      d.years.forEach((y) => {
        const opt = document.createElement("option");
        opt.value = String(y);
        opt.textContent = `Bara ${y}`;
        yearFilter.appendChild(opt);
      });

      const totalLjus = d.platser.reduce((s, k) => s + k.total, 0);
      metaSummary.textContent =
        `${fmt(d.platser.length)} platser, ${fmt(totalLjus)} ljus 2020-2025`;

      filtered = [...d.platser];
      render();

      search.addEventListener("input", applyFilters);
      stiftFilter.addEventListener("change", applyFilters);
      yearFilter.addEventListener("change", applyFilters);
    })
    .catch((err) => {
      console.error(err);
      tbody.innerHTML =
        `<tr><td colspan="6" class="loading">Kunde inte ladda data. Kör build_data.py först?</td></tr>`;
    });
})();
