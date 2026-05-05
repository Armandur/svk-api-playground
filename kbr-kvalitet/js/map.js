var map = L.map('map').setView([62.5, 16], 5);
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
  attribution:'&copy; OpenStreetMap', maxZoom:19
}).addTo(map);

var markerLayer = L.layerGroup().addTo(map);
var unmatchedLayer = L.layerGroup();
var unmatchedRows = [];
var highlightMarker = null;

function renderUnmatched() {
  unmatchedLayer.clearLayers();
  unmatchedRows.forEach(r => {
    L.circleMarker([r.kbr_lat, r.kbr_lng], {radius:3, color:"#999", fillColor:"#bbb", fillOpacity:0.7, weight:1})
      .bindTooltip("<strong>Ej matchad i Platser/OSM</strong><br>"+r.namn+"<br>"+(r.stift||'')+"<br><span style='color:#999;font-size:10px'>Källa: KBR (Kyrkobyggnadsregistret)</span>", {sticky:true})
      .addTo(unmatchedLayer);
  });
}

function jumpToKBR(lat, lng, name) {
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
  document.querySelectorAll('.tab-pane').forEach(p => p.classList.remove('active'));
  document.querySelector('[data-tab="koordinater"]').classList.add('active');
  document.getElementById('tab-koordinater').classList.add('active');
  map.invalidateSize();
  if (highlightMarker) { map.removeLayer(highlightMarker); highlightMarker = null; }
  highlightMarker = L.circleMarker([lat, lng], {
    radius:14, color:'#7D0037', fillColor:'#7D0037', fillOpacity:0.25, weight:2.5,
  }).bindTooltip(name, {permanent:true, direction:'top'}).addTo(map);
  map.setView([lat, lng], 15);
  setTimeout(() => { if (highlightMarker) { map.removeLayer(highlightMarker); highlightMarker = null; } }, 6000);
}

function buildMarkers(rs) {
  markerLayer.clearLayers();
  rs.forEach(r => {
    const c = distColor(r.avstand_m);
    if (r.platser_lat != null) {
      L.polyline([[r.kbr_lat,r.kbr_lng],[r.platser_lat,r.platser_lng]],
        {color:'#1565c0',weight:1.5,opacity:0.5,dashArray:'4 4'}).addTo(markerLayer);
      L.circleMarker([r.platser_lat,r.platser_lng],{radius:4,color:'#1565c0',fillColor:'#42a5f5',fillOpacity:0.8,weight:1.5})
        .bindTooltip(`<strong>Platser-API</strong><br>${r.namn}<br>${r.platser_lat}, ${r.platser_lng}${r.platser_slug ? `<br><a href="https://www.svenskakyrkan.se/platser/${r.platser_slug}" target="_blank" style="color:#1565c0">Öppna på svenskakyrkan.se</a>` : ''}`,{sticky:true}).addTo(markerLayer);
    }
    if (r.osm_lat != null) {
      L.polyline([[r.kbr_lat,r.kbr_lng],[r.osm_lat,r.osm_lng]],
        {color:'#2e7d32',weight:1.5,opacity:0.5,dashArray:'2 4'}).addTo(markerLayer);
      L.circleMarker([r.osm_lat,r.osm_lng],{radius:4,color:'#2e7d32',fillColor:'#66bb6a',fillOpacity:0.8,weight:1.5})
        .bindTooltip(`<strong>OSM</strong><br>${r.namn}<br>${r.osm_lat}, ${r.osm_lng}`,{sticky:true}).addTo(markerLayer);
    }
    if (r.bv_lat != null) {
      L.polyline([[r.kbr_lat,r.kbr_lng],[r.bv_lat,r.bv_lng]],
        {color:'#7B1FA2',weight:1.5,opacity:0.5,dashArray:'3 5'}).addTo(markerLayer);
      L.circleMarker([r.bv_lat,r.bv_lng],{radius:4,color:'#7B1FA2',fillColor:'#CE93D8',fillOpacity:0.8,weight:1.5})
        .bindTooltip(`<strong>BV</strong><br>${r.namn}<br>${r.bv_lat}, ${r.bv_lng}`,{sticky:true}).addTo(markerLayer);
    }
    L.circleMarker([r.kbr_lat,r.kbr_lng],{radius:5,color:c,fillColor:c,fillOpacity:0.9,weight:1.5})
      .bindTooltip(`<strong>KBR (Kyrkobyggnadsregistret)</strong><br>${r.namn}<br>${r.kbr_lat}, ${r.kbr_lng}<br>Platser: ${fmtDist(r.avstand_platser_m)} | OSM: ${fmtDist(r.avstand_osm_m)} | BV: ${fmtDist(r.avstand_bv_m)}`,{sticky:true}).addTo(markerLayer);
  });
}
