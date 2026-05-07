/* Allhelgona-replay - spelar upp tända ljus på Bönewebben i tidsordning.
 *
 * Datat (data/candles.json) är sorterat ASC på epoch-timestamp. Replay-
 * tiden ökar med wall-clock-delta * speedFactor. Vid varje frame ritar vi
 * alla ljus med ts <= currentReplayTs på en canvas-overlay; de allra
 * senaste tändningarna pulsar i några sekunder innan de stadgar sig som
 * en stilla flamma. Hela ljusbilden ritas om varje frame, vilket
 * uppfattas trögt vid 16k+ poster på cellulär hårdvara - därför rendrar
 * vi en separat "static layer" en gång per zoom/pan och en "active
 * layer" per frame.
 */
(() => {
  "use strict";

  const DATA_URL = "data/candles.json";
  const PULSE_DURATION_MS = 4500;   // hur länge ett nytt ljus pulsar
  const RECENT_WINDOW_S   = 4 * 3600; // ljus tända inom X sek räknas som "aktiva" (för pulse-färg)

  /* ---------------- Karta ---------------- */
  // Sveriges geografiska bbox (med viss marginal i söder/norr).
  // Används som default-vy och som lower bound för fitBounds vid load.
  const SWEDEN_BOUNDS = L.latLngBounds(
    [55.0, 10.5],   // sydväst (Skåne / Öresund)
    [69.1, 24.5]    // nordost (Treriksröset / Tornedalen)
  );

  const map = L.map("map", {
    zoomControl: true,
    attributionControl: true,
  });
  map.fitBounds(SWEDEN_BOUNDS, { padding: [10, 10] });

  L.control.scale({ imperial: false }).addTo(map);

  // CartoDB DarkMatter passar mörk natthimmel-stämning för flammor.
  L.tileLayer(
    "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png",
    {
      attribution:
        '&copy; <a href="https://www.openstreetmap.org/copyright">OSM</a> ' +
        '&copy; <a href="https://carto.com/attributions">CARTO</a> · ' +
        'data <a href="https://be.svenskakyrkan.se/">Svenska kyrkan</a>',
      subdomains: "abcd",
      maxZoom: 18,
    }
  ).addTo(map);

  /* ---------------- Canvas-overlay för ljus ---------------- */
  /* Egen Leaflet-overlay som ritar alla synliga ljus på ett <canvas>
   * positionerat med samma transform som mapPane. Snabbare än 16k
   * circleMarkers; hela bilden ritas om per frame. */
  const CandleLayer = L.Layer.extend({
    onAdd(map) {
      this._map = map;
      const c = (this._canvas = L.DomUtil.create("canvas", "leaflet-zoom-animated"));
      c.style.position = "absolute";
      c.style.pointerEvents = "none";
      this._ctx = c.getContext("2d");
      map.getPanes().overlayPane.appendChild(c);
      map.on("moveend zoomend resize", this._reset, this);
      map.on("zoomanim", this._animateZoom, this);
      this._reset();
    },
    onRemove(map) {
      map.getPanes().overlayPane.removeChild(this._canvas);
      map.off("moveend zoomend resize", this._reset, this);
      map.off("zoomanim", this._animateZoom, this);
    },
    _animateZoom(e) {
      const scale = this._map.getZoomScale(e.zoom);
      const offset = this._map._latLngBoundsToNewLayerBounds
        ? this._map._latLngBoundsToNewLayerBounds(this._map.getBounds(), e.zoom, e.center).min
        : this._map._getCenterOffset(e.center)._multiplyBy(-scale).subtract(this._map._getMapPanePos());
      L.DomUtil.setTransform(this._canvas, offset, scale);
    },
    _reset() {
      const size = this._map.getSize();
      const topLeft = this._map.containerPointToLayerPoint([0, 0]);
      L.DomUtil.setPosition(this._canvas, topLeft);
      this._canvas.width = size.x;
      this._canvas.height = size.y;
      this._size = size;
      this._topLeft = topLeft;
      if (this._draw) this._draw();
    },
    setDraw(fn) { this._draw = fn; this._reset(); },
    redraw() { if (this._draw) this._draw(); },
    project(lat, lng) {
      // Canvas-koord = layerpoint - topLeft
      const lp = this._map.latLngToLayerPoint([lat, lng]);
      return [lp.x - this._topLeft.x, lp.y - this._topLeft.y];
    },
  });

  const candleLayer = new CandleLayer();
  candleLayer.addTo(map);

  /* ---------------- State ---------------- */
  let candles = [];           // [[ts, lat, lng], ...] sorted asc
  let firstTs = 0;
  let lastTs = 0;
  let totalCount = 0;

  let replayTs = 0;           // aktuell sim-tid (epoch sek)
  let speedFactor = 3600;     // sim-sek per wall-sek
  let playing = false;
  let lastFrameWall = 0;      // performance.now()
  let litIndex = 0;           // index till nästa ljus som *inte* tänts än

  // För pulse-effekten: senaste N tända ljus med tändningstid (sim-sek)
  // som vi animerar i några sekunder efter tändning. Vi använder en
  // glidande array: ljus inom litIndex - PULSE_BUFFER ... litIndex.
  const PULSE_BUFFER = 200;

  /* ---------------- Render ---------------- */
  function drawCandles() {
    const ctx = candleLayer._ctx;
    const w = candleLayer._size.x;
    const h = candleLayer._size.y;
    ctx.clearRect(0, 0, w, h);
    if (litIndex === 0) return;

    const bounds = map.getBounds().pad(0.1);
    const pulseStart = Math.max(0, litIndex - PULSE_BUFFER);

    // Statiska ljus (alla tända utom de allra senaste)
    ctx.fillStyle = "rgba(255, 179, 71, 0.55)";  // var(--flame), translucent
    for (let i = 0; i < pulseStart; i++) {
      const [, lat, lng] = candles[i];
      if (!bounds.contains([lat, lng])) continue;
      const [x, y] = candleLayer.project(lat, lng);
      ctx.beginPath();
      ctx.arc(x, y, 2.2, 0, Math.PI * 2);
      ctx.fill();
    }

    // Pulsande ljus - de senaste PULSE_BUFFER. Animering baserad på
    // hur lång sim-tid som gått sedan tändning, omräknat till wall-tid
    // via aktuell speed.
    const pulseSimWindow = (PULSE_DURATION_MS / 1000) * speedFactor;
    for (let i = pulseStart; i < litIndex; i++) {
      const [ts, lat, lng] = candles[i];
      if (!bounds.contains([lat, lng])) continue;
      const [x, y] = candleLayer.project(lat, lng);
      const ageSim = replayTs - ts;
      const ageNorm = Math.min(1, Math.max(0, ageSim / pulseSimWindow));
      // Pulse: börjar stort + ljust, krymper till stadig glöd
      const radius = 2.2 + (1 - ageNorm) * 9;
      const alpha = 0.55 + (1 - ageNorm) * 0.45;
      const isVeryRecent = ageSim < RECENT_WINDOW_S;

      // Halo
      const grad = ctx.createRadialGradient(x, y, 0, x, y, radius * 2);
      grad.addColorStop(0, isVeryRecent
        ? `rgba(255, 213, 128, ${alpha * 0.9})`
        : `rgba(255, 179, 71, ${alpha * 0.7})`);
      grad.addColorStop(1, "rgba(255, 179, 71, 0)");
      ctx.fillStyle = grad;
      ctx.beginPath();
      ctx.arc(x, y, radius * 2, 0, Math.PI * 2);
      ctx.fill();

      // Kärna
      ctx.fillStyle = isVeryRecent
        ? `rgba(255, 235, 200, ${alpha})`
        : `rgba(255, 179, 71, ${alpha})`;
      ctx.beginPath();
      ctx.arc(x, y, Math.max(2.2, radius * 0.45), 0, Math.PI * 2);
      ctx.fill();
    }
  }

  candleLayer.setDraw(drawCandles);

  /* ---------------- Replay-loop ---------------- */
  function tick(now) {
    if (!playing) return;
    const dt = (now - lastFrameWall) / 1000;
    lastFrameWall = now;

    replayTs += dt * speedFactor;
    if (replayTs >= lastTs) {
      replayTs = lastTs;
      playing = false;
      updatePlayBtn();
    }

    advanceLitIndex();
    syncUiToReplayTs();
    candleLayer.redraw();

    if (playing) requestAnimationFrame(tick);
  }

  function advanceLitIndex() {
    while (litIndex < candles.length && candles[litIndex][0] <= replayTs) {
      litIndex++;
    }
  }

  function rewindLitIndex() {
    // När user drar slidern bakåt - kasta bort ljus som inte längre är tända.
    while (litIndex > 0 && candles[litIndex - 1][0] > replayTs) {
      litIndex--;
    }
  }

  /* ---------------- UI ---------------- */
  const $ = (sel) => document.querySelector(sel);
  const slider = $("#slider");
  const heatmap = $("#heatmap");
  const btnPlay = $("#btn-play");
  const btnReset = $("#btn-reset");
  const playIcon = $("#play-icon");
  const speedBtns = document.querySelectorAll(".speeds button");
  const clockDate = $("#clock-date");
  const clockTime = $("#clock-time");
  const litCount = $("#lit-count");
  const litTotal = $("#lit-total");
  const infoTotal = $("#info-total");
  const infoTag = $("#info-tag");
  const metaTag = $("#meta-tag");
  const infoFetched = $("#info-fetched");
  const info = $("#info");
  const infoOpen = $("#info-open");

  const dateFmt = new Intl.DateTimeFormat("sv-SE", {
    weekday: "long", year: "numeric", month: "long", day: "numeric",
    timeZone: "Europe/Stockholm",
  });
  const timeFmt = new Intl.DateTimeFormat("sv-SE", {
    hour: "2-digit", minute: "2-digit",
    timeZone: "Europe/Stockholm",
  });

  /* Heatmap över tidslinjen - histogram över när ljus tänds, ritat som
   * bakgrund till slidern. Använder N buckets över [firstTs, lastTs].
   * Logaritmisk skala för intensitet eftersom helgen är 100x tätare än
   * dagarna i kanten. */
  const HEATMAP_BUCKETS = 200;

  function drawHeatmap() {
    if (!candles.length) return;
    const dpr = window.devicePixelRatio || 1;
    const cssW = heatmap.clientWidth;
    const cssH = heatmap.clientHeight;
    if (cssW === 0 || cssH === 0) return;
    heatmap.width = cssW * dpr;
    heatmap.height = cssH * dpr;
    const ctx = heatmap.getContext("2d");
    ctx.scale(dpr, dpr);
    ctx.clearRect(0, 0, cssW, cssH);

    const span = lastTs - firstTs || 1;
    const buckets = new Array(HEATMAP_BUCKETS).fill(0);
    for (let i = 0; i < candles.length; i++) {
      const f = (candles[i][0] - firstTs) / span;
      const b = Math.min(HEATMAP_BUCKETS - 1, Math.floor(f * HEATMAP_BUCKETS));
      buckets[b]++;
    }
    let max = 0;
    for (const v of buckets) if (v > max) max = v;
    if (max === 0) return;

    const bw = cssW / HEATMAP_BUCKETS;
    for (let i = 0; i < HEATMAP_BUCKETS; i++) {
      if (buckets[i] === 0) continue;
      // Log-skala så även små värden syns
      const norm = Math.log1p(buckets[i]) / Math.log1p(max);
      const alpha = 0.18 + norm * 0.72;
      // Färgen interpolerar från mörk orange till varm gul
      const r = Math.round(255);
      const g = Math.round(140 + norm * 100);
      const b = Math.round(50 + norm * 80);
      ctx.fillStyle = `rgba(${r},${g},${b},${alpha})`;
      ctx.fillRect(i * bw, 0, Math.ceil(bw) + 0.5, cssH);
    }
  }

  // Rita om vid resize (kontrollernas bredd kan ändras)
  let resizeTimer;
  window.addEventListener("resize", () => {
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(drawHeatmap, 120);
  });

  function syncUiToReplayTs() {
    const date = new Date(replayTs * 1000);
    clockDate.textContent = dateFmt.format(date);
    clockTime.textContent = timeFmt.format(date);
    litCount.textContent = litIndex.toLocaleString("sv-SE");
    const span = lastTs - firstTs || 1;
    slider.value = String(Math.round(((replayTs - firstTs) / span) * 1000));
  }

  function setSpeed(s) {
    speedFactor = s;
    speedBtns.forEach((b) =>
      b.classList.toggle("active", Number(b.dataset.speed) === s));
  }

  function updatePlayBtn() {
    if (playing) {
      // Pause-ikon
      playIcon.setAttribute("d", "M6 4h4v16H6zM14 4h4v16h-4z");
    } else {
      playIcon.setAttribute("d", "M6 4l14 8-14 8z");
    }
  }

  function play() {
    if (replayTs >= lastTs) replayTs = firstTs;
    playing = true;
    lastFrameWall = performance.now();
    updatePlayBtn();
    requestAnimationFrame(tick);
  }
  function pause() {
    playing = false;
    updatePlayBtn();
  }

  btnPlay.addEventListener("click", () => playing ? pause() : play());
  btnReset.addEventListener("click", () => {
    pause();
    replayTs = firstTs;
    litIndex = 0;
    syncUiToReplayTs();
    candleLayer.redraw();
  });
  speedBtns.forEach((b) =>
    b.addEventListener("click", () => setSpeed(Number(b.dataset.speed))));

  slider.addEventListener("input", () => {
    const span = lastTs - firstTs || 1;
    replayTs = firstTs + (Number(slider.value) / 1000) * span;
    advanceLitIndex();
    rewindLitIndex();
    syncUiToReplayTs();
    candleLayer.redraw();
  });

  // Info-toggle
  $("#info-close").addEventListener("click", () => {
    info.classList.add("hidden");
    infoOpen.classList.add("show");
  });
  infoOpen.addEventListener("click", () => {
    info.classList.remove("hidden");
    infoOpen.classList.remove("show");
  });

  // Tangentbord: mellanslag = play/pause, H = toggla UI
  document.addEventListener("keydown", (e) => {
    if (e.target.tagName === "INPUT") return;
    if (e.code === "Space") {
      e.preventDefault();
      playing ? pause() : play();
    } else if (e.key === "h" || e.key === "H") {
      e.preventDefault();
      document.body.classList.toggle("ui-hidden");
    }
  });

  /* ---------------- Init ---------------- */
  fetch(DATA_URL)
    .then((r) => r.json())
    .then((d) => {
      candles = d.candles;
      totalCount = d.count;
      firstTs = candles[0][0];
      lastTs = candles[candles.length - 1][0];
      replayTs = firstTs;

      // Default-vy: hela Sverige - bounds satt redan vid map-init,
      // anropar igen för säkerhets skull eftersom container kan ha
      // bytt storlek mellan init och data-load.
      map.fitBounds(SWEDEN_BOUNDS, { padding: [10, 10] });

      litTotal.textContent = totalCount.toLocaleString("sv-SE");
      infoTotal.textContent = totalCount.toLocaleString("sv-SE");
      const tagYear = (d.tag.match(/\d{4}/) || ["?"])[0];
      infoTag.textContent = tagYear;
      metaTag.textContent = tagYear;
      infoFetched.textContent =
        `hämtat ${d.fetched.replace("T", " ").replace("Z", " UTC")}`;

      syncUiToReplayTs();
      candleLayer.redraw();
      drawHeatmap();
    })
    .catch((err) => {
      console.error(err);
      alert("Kunde inte ladda candles.json - kör build_data.py först?");
    });
})();
