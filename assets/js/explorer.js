/* HFI Explorer
   Static GitHub Pages implementation. Reads official HFI release files from /data.
   Included data files:
   - data/hfi_tracts.geojson        browser-ready tract geometry + HFI attributes
   - data/hfi_tract_data.csv        original tract-level HFI data
   - data/hfi_hospitals.csv         linked hospital/HCAHPS data
*/

const CONFIG = {
  tractGeoJsonUrl: 'data/hfi_tracts.geojson',
  tractDataUrl: 'data/hfi_tract_data.csv',
  hospitalUrl: 'data/hfi_hospitals.csv',
  mapCenter: [40.7128, -74.0060],
  mapZoom: 10,
  colors: ['#2c7bb6', '#74add1', '#abd9e9', '#ffffbf', '#fdae61', '#d7191c'],
  hfiAliases: ['hfi', 'hfi_v1', 'hfi_v1_0', 'hfi_score', 'fragmentation', 'fragmentation_index', 'fi_time_space_std', 'fi_time_adjusted_std', 'fi_complexity_std'],
  geoidAliases: ['geoid', 'geo_id', 'tract_geoid', 'geoid10', 'geoid20', 'geoidfq', 'tractid', 'tract_id', 'map_id'],
  boroughAliases: ['borough', 'boro_name', 'county', 'county_name', 'boroname'],
  hospitalNameAliases: ['hospital_name', 'name', 'facility_name', 'hospital', 'facility'],
  latitudeAliases: ['lat', 'latitude', 'y', '_cy', 'cy'],
  longitudeAliases: ['lon', 'lng', 'long', 'longitude', 'x', '_cx', 'cx'],
  communicationAliases: ['communication_index', 'patient_experience_index', 'hcahps_communication', 'comm_index'],
  tractProviderAliases: ['provider_time_weight_sum', 'providers', 'provider_count_timefile'],
  hfiClassAliases: ['frag_q', 'hfi_class', 'hfi_quintile']
};

let map, tractLayer, hospitalLayer, tractFeatures = [], hospitalRecords = [], hospitalMarkers = [];
let hfiBreaks = [];
let fullBounds = null;
let mapWrapResizeObserver = null;
let selectedTractLayer = null;
let selectedHospitalMarker = null;

bootExplorer();
window.addEventListener('load', () => { updateExplorerHeight(); scheduleMapResize(); });
window.addEventListener('resize', () => { updateExplorerHeight(); scheduleMapResize(); });

async function bootExplorer() {
  if (document.readyState === 'loading') {
    await new Promise(resolve => document.addEventListener('DOMContentLoaded', resolve, { once: true }));
  }
  updateExplorerHeight();
  // Give the fixed CSS grid one paint cycle to settle before Leaflet reads dimensions.
  await new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)));
  await waitForMapBox();
  await initExplorer();
}

function updateExplorerHeight() {
  const header = document.querySelector('.explorer-header');
  if (!header) return;
  document.documentElement.style.setProperty('--hfi-header-height', `${Math.ceil(header.getBoundingClientRect().height)}px`);
}

function waitForMapBox() {
  return new Promise(resolve => {
    let tries = 0;
    const tick = () => {
      updateExplorerHeight();
      const box = document.querySelector('.map-wrap')?.getBoundingClientRect();
      if (box && box.width > 300 && box.height > 300) return resolve();
      if (tries++ > 90) return resolve();
      requestAnimationFrame(tick);
    };
    requestAnimationFrame(tick);
  });
}

async function initExplorer() {
  updateExplorerHeight();
  map = L.map('map', { zoomControl: true, zoomSnap: 0.25, preferCanvas: true }).setView(CONFIG.mapCenter, CONFIG.mapZoom);
  map.whenReady(() => scheduleMapResize());
  L.tileLayer('https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png', {
    attribution: '&copy; OpenStreetMap contributors &copy; CARTO',
    maxZoom: 19
  }).addTo(map);

  const wrap = document.querySelector('.map-wrap');
  if (window.ResizeObserver && wrap) {
    mapWrapResizeObserver = new ResizeObserver(() => scheduleMapResize());
    mapWrapResizeObserver.observe(wrap);
  }

  map.createPane('tractPane');
  map.getPane('tractPane').style.zIndex = 410;
  map.createPane('hospitalPane');
  map.getPane('hospitalPane').style.zIndex = 650;

  tractLayer = L.geoJSON(null, { pane: 'tractPane', style: styleTract, onEachFeature: onEachTract }).addTo(map);
  hospitalLayer = L.layerGroup().addTo(map);
  wireControls();
  scheduleMapResize();

  try {
    const [tractGeoJson, hospitalRows] = await Promise.all([
      loadGeoJson(CONFIG.tractGeoJsonUrl),
      loadCsv(CONFIG.hospitalUrl)
    ]);
    buildMapFromGeoJson(tractGeoJson, hospitalRows);
  } catch (err) {
    console.error(err);
    setStatus('error', `Could not load the browser-ready HFI release files. Check /data/hfi_tracts.geojson and /data/hfi_hospitals.csv. Details: ${err.message}`);
  }
}

function scheduleMapResize() {
  if (!map) return;
  const run = () => {
    updateExplorerHeight();
    const wrap = document.querySelector('.map-wrap');
    const mapEl = document.getElementById('map');
    if (wrap && mapEl) {
      const r = wrap.getBoundingClientRect();
      mapEl.style.width = `${Math.max(1, Math.round(r.width))}px`;
      mapEl.style.height = `${Math.max(1, Math.round(r.height))}px`;
    }
    map.invalidateSize({ pan: false, debounceMoveend: true });
  };
  requestAnimationFrame(() => {
    run();
    setTimeout(run, 100);
    setTimeout(run, 300);
    setTimeout(run, 800);
  });
}

function fitMapWhenStable(bounds) {
  const fit = () => {
    updateExplorerHeight();
    const box = document.getElementById('map')?.getBoundingClientRect();
    if (!box || box.width < 300 || box.height < 300) return scheduleMapResize();
    map.invalidateSize({ pan: false });
    map.fitBounds(bounds.pad(0.05), { animate: false, padding: [24, 24] });
    map.once('moveend', () => map.invalidateSize({ pan: false }));
  };
  scheduleMapResize();
  requestAnimationFrame(() => requestAnimationFrame(fit));
  setTimeout(fit, 250);
  setTimeout(fit, 900);
}

async function loadGeoJson(url) {
  const res = await fetch(url, { cache: 'no-store' });
  if (!res.ok) throw new Error(`${url}: ${res.status} ${res.statusText}`);
  return await res.json();
}

function loadCsv(url) {
  return new Promise((resolve, reject) => {
    Papa.parse(url, {
      download: true,
      header: true,
      dynamicTyping: false,
      skipEmptyLines: true,
      complete: results => resolve(results.data.map(normalizeRecord)),
      error: error => reject(new Error(`${url}: ${error.message || error}`))
    });
  });
}

function normalizeRecord(row) {
  const out = {};
  Object.entries(row || {}).forEach(([key, value]) => {
    out[normalizeKey(key)] = typeof value === 'string' ? value.trim() : value;
  });
  return out;
}

function normalizeKey(key) {
  return String(key || '').trim().toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_+|_+$/g, '');
}

function normalizeProperties(props) {
  const out = {};
  Object.entries(props || {}).forEach(([key, value]) => { out[normalizeKey(key)] = value; });
  return out;
}

function getValue(row, aliases) {
  for (const alias of aliases) {
    const key = normalizeKey(alias);
    if (row && row[key] !== undefined && row[key] !== null && row[key] !== '') return row[key];
  }
  return undefined;
}

function numberValue(value) {
  if (value === undefined || value === null || value === '') return null;
  const n = Number(String(value).replace(/,/g, ''));
  return Number.isFinite(n) ? n : null;
}

function buildMapFromGeoJson(geojson, hospitalRows) {
  tractFeatures = (geojson.features || []).map(feature => {
    const props = normalizeProperties(feature.properties || {});
    props.geoid = cleanGeoid(getValue(props, CONFIG.geoidAliases));
    props.hfi_value = numberValue(getValue(props, CONFIG.hfiAliases));
    props.borough_label = inferBorough(props);
    props.hfi_class = getValue(props, CONFIG.hfiClassAliases) || classifyHfi(props.hfi_value);
    return { type: 'Feature', geometry: feature.geometry, properties: props };
  }).filter(f => f.geometry && f.properties.geoid);

  const hfiValues = tractFeatures.map(f => f.properties.hfi_value).filter(v => Number.isFinite(v));
  hfiBreaks = quantileBreaks(hfiValues, CONFIG.colors.length);
  tractLayer.addData({ type: 'FeatureCollection', features: tractFeatures });

  hospitalRecords = hospitalRows
    .map(row => ({ ...row, name: getValue(row, CONFIG.hospitalNameAliases) || 'Hospital' }))
    .filter(row => Number.isFinite(numberValue(getValue(row, CONFIG.latitudeAliases))) && Number.isFinite(numberValue(getValue(row, CONFIG.longitudeAliases))));

  populateHospitalOptions(hospitalRecords);
  drawHospitals(hospitalRecords);
  updateStats(hfiValues, hospitalRecords.length);
  drawLegend();
  setStatus('ready', `Loaded ${tractFeatures.length.toLocaleString()} HFI tracts and ${hospitalRecords.length.toLocaleString()} linked hospitals.`);

  const bounds = tractLayer.getBounds();
  if (bounds.isValid()) {
    fullBounds = bounds;
    fitMapWhenStable(bounds);
  } else {
    scheduleMapResize();
  }
}

function cleanGeoid(value) {
  if (value === undefined || value === null || value === '') return '';
  const s = String(value).trim();
  const digits = s.match(/\d{11}/);
  return digits ? digits[0] : s.replace(/\.0$/, '');
}

function inferBorough(props) {
  const direct = getValue(props, CONFIG.boroughAliases);
  if (direct) return standardBorough(direct);
  const geoid = cleanGeoid(props.geoid);
  const county = geoid.slice(2, 5);
  return ({ '005': 'Bronx', '047': 'Brooklyn', '061': 'Manhattan', '081': 'Queens', '085': 'Staten Island' }[county]) || 'Unknown';
}

function standardBorough(value) {
  const v = String(value).toLowerCase();
  if (v.includes('bronx')) return 'Bronx';
  if (v.includes('brook') || v.includes('kings')) return 'Brooklyn';
  if (v.includes('manhattan') || v.includes('new york')) return 'Manhattan';
  if (v.includes('queen')) return 'Queens';
  if (v.includes('staten') || v.includes('richmond')) return 'Staten Island';
  return String(value);
}

function quantileBreaks(values, bins) {
  if (!values.length) return [];
  const sorted = values.slice().sort((a, b) => a - b);
  const breaks = [];
  for (let i = 0; i <= bins; i++) {
    const idx = Math.min(sorted.length - 1, Math.max(0, Math.round((i / bins) * (sorted.length - 1))));
    breaks.push(sorted[idx]);
  }
  return breaks;
}

function colorForValue(value) {
  if (!Number.isFinite(value) || !hfiBreaks.length) return '#d7dde4';
  for (let i = 0; i < CONFIG.colors.length; i++) {
    if (value <= hfiBreaks[i + 1]) return CONFIG.colors[i];
  }
  return CONFIG.colors[CONFIG.colors.length - 1];
}

function styleTract(feature) {
  const value = feature.properties.hfi_value;
  return {
    color: '#1c3147',
    weight: .7,
    opacity: .72,
    fillColor: colorForValue(value),
    fillOpacity: Number.isFinite(value) ? .66 : .22
  };
}

function onEachTract(feature, layer) {
  layer.options.interactive = true;
  layer.on({
    mouseover: () => {
      if (layer !== selectedTractLayer) {
        layer.setStyle({ weight: 2.2, color: '#07192c', fillOpacity: .88 });
      }
      layer.bringToFront();
    },
    mouseout: () => {
      if (layer !== selectedTractLayer) tractLayer.resetStyle(layer);
    },
    click: () => selectTract(feature, layer)
  });
}

function selectTract(feature, layer, options = {}) {
  if (!feature || !layer) return;
  if (selectedTractLayer && selectedTractLayer !== layer) {
    tractLayer.resetStyle(selectedTractLayer);
  }
  if (selectedHospitalMarker) {
    resetHospitalMarker(selectedHospitalMarker);
    selectedHospitalMarker = null;
  }

  selectedTractLayer = layer;
  layer.setStyle({ color: '#07192c', weight: 3.4, opacity: 1, fillOpacity: .9 });
  layer.bringToFront();

  const p = feature.properties;
  showFeatureInfo('Tract', `Tract ${p.geoid}`, {
    Borough: p.borough_label,
    'HFI value': formatNumber(p.hfi_value, 3),
    'HFI category': p.hfi_class || classifyHfi(p.hfi_value),
    'Provider time weight': formatNumber(numberValue(getValue(p, CONFIG.tractProviderAliases)), 3),
    Interpretation: interpretHfi(p.hfi_value)
  });

  layer.bindPopup(`<strong>Tract ${escapeHtml(p.geoid)}</strong><br>HFI: ${formatNumber(p.hfi_value, 3)}<br>${escapeHtml(p.borough_label)}`).openPopup();
  focusFeatureInfo();
  if (options.fit) fitMapWhenStable(layer.getBounds());
}

function drawHospitals(records) {
  hospitalLayer.clearLayers();
  hospitalMarkers = [];
  selectedHospitalMarker = null;
  records.forEach(row => {
    const lat = numberValue(getValue(row, CONFIG.latitudeAliases));
    const lon = numberValue(getValue(row, CONFIG.longitudeAliases));
    const comm = numberValue(getValue(row, CONFIG.communicationAliases));
    const rating = numberValue(row.hospital_overall_rating);
    const marker = L.circleMarker([lat, lon], {
      pane: 'hospitalPane',
      radius: 7.5,
      color: '#07192c',
      weight: 2.1,
      fillColor: Number.isFinite(comm) ? '#ffd166' : '#ffffff',
      fillOpacity: .98
    });
    marker.defaultStyle = {
      radius: 7.5,
      color: '#07192c',
      weight: 2.1,
      fillColor: Number.isFinite(comm) ? '#ffd166' : '#ffffff',
      fillOpacity: .98
    };
    marker.on('click', () => {
      selectHospital(row, marker, comm, rating);
    });
    marker.bindPopup(hospitalPopup(row, comm, rating));
    marker.addTo(hospitalLayer);
    hospitalMarkers.push({ row, marker, lat, lon });
  });
}

function selectHospital(row, marker, comm = numberValue(getValue(row, CONFIG.communicationAliases)), rating = numberValue(row.hospital_overall_rating)) {
  if (!row || !marker) return;
  if (selectedTractLayer) {
    tractLayer.resetStyle(selectedTractLayer);
    selectedTractLayer = null;
  }
  if (selectedHospitalMarker && selectedHospitalMarker !== marker) resetHospitalMarker(selectedHospitalMarker);
  selectedHospitalMarker = marker;
  marker.setStyle({ radius: 11, color: '#07192c', weight: 3.2, fillColor: '#ffd166', fillOpacity: 1 });
  marker.bringToFront();
  marker.openPopup();
  showFeatureInfo('Hospital', row.name, {
    Borough: standardBorough(row.county || ''),
    'Overall CMS rating': formatNumber(rating, 0),
    'Communication index': formatNumber(comm, 2),
    'Doctor communication': formatNumber(numberValue(row.hcahps_doctor_comm_linear), 1),
    'Nurse communication': formatNumber(numberValue(row.hcahps_nurse_comm_linear), 1),
    'Linked tract HFI': formatNumber(numberValue(row.fragmentation), 3)
  });
  focusFeatureInfo();
}

function resetHospitalMarker(marker) {
  if (!marker) return;
  marker.setStyle(marker.defaultStyle || { radius: 7.5, color: '#07192c', weight: 2.1, fillColor: '#ffd166', fillOpacity: .98 });
}

function wireControls() {
  document.getElementById('toggle-tracts').addEventListener('change', e => e.target.checked ? tractLayer.addTo(map) : map.removeLayer(tractLayer));
  document.getElementById('toggle-hospitals').addEventListener('change', e => e.target.checked ? hospitalLayer.addTo(map) : map.removeLayer(hospitalLayer));
  document.getElementById('borough-filter').addEventListener('change', filterMap);
  document.getElementById('search-input').addEventListener('input', filterMap);
  document.getElementById('clear-search')?.addEventListener('click', () => {
    document.getElementById('search-input').value = '';
    filterMap(false);
  });
  document.getElementById('reset-map')?.addEventListener('click', () => {
    document.getElementById('borough-filter').value = 'all';
    document.getElementById('search-input').value = '';
    filterMap(false);
    if (fullBounds?.isValid()) fitMapWhenStable(fullBounds);
  });
  document.getElementById('zoom-nyc')?.addEventListener('click', () => {
    map.setView(CONFIG.mapCenter, 10.25, { animate: true });
    scheduleMapResize();
  });
}

function filterMap(shouldFit = true) {
  const borough = document.getElementById('borough-filter').value;
  const query = document.getElementById('search-input').value.trim().toLowerCase();
  tractLayer.clearLayers();
  selectedTractLayer = null;
  const filtered = tractFeatures.filter(f => {
    const p = f.properties;
    const boroughMatch = borough === 'all' || p.borough_label === borough;
    const hay = Object.values(p).join(' ').toLowerCase();
    return boroughMatch && (!query || hay.includes(query));
  });
  tractLayer.addData({ type: 'FeatureCollection', features: filtered });

  const filteredHospitals = hospitalRecords.filter(h => {
    const boroughMatch = borough === 'all' || standardBorough(h.county || '') === borough;
    const hay = Object.values(h).join(' ').toLowerCase();
    return boroughMatch && (!query || hay.includes(query));
  });
  drawHospitals(filteredHospitals);
  document.getElementById('tract-count').textContent = filtered.length.toLocaleString();
  document.getElementById('hospital-count').textContent = filteredHospitals.length.toLocaleString();
  const filteredValues = filtered.map(f => f.properties.hfi_value).filter(v => Number.isFinite(v));
  if (filteredValues.length) {
    document.getElementById('hfi-range').textContent = `${formatNumber(Math.min(...filteredValues), 2)} to ${formatNumber(Math.max(...filteredValues), 2)}`;
  } else {
    document.getElementById('hfi-range').textContent = '—';
  }
  updateSummary(filtered.length, filteredHospitals.length, filteredValues);
  const b = tractLayer.getBounds();
  if (shouldFit && query && hospitalMarkers.length && (filtered.length === 0 || hospitalMarkers.length <= 3)) {
    const hospitalBounds = L.latLngBounds(hospitalMarkers.map(item => [item.lat, item.lon]));
    if (hospitalBounds.isValid()) {
      fitMapWhenStable(hospitalBounds);
      if (hospitalMarkers.length === 1) {
        hospitalMarkers[0].marker.openPopup();
        hospitalMarkers[0].marker.fire('click');
      }
      return;
    }
  }
  if (shouldFit && b.isValid() && (borough !== 'all' || query)) fitMapWhenStable(b);
}

function updateStats(values, hospitals) {
  document.getElementById('tract-count').textContent = tractFeatures.length.toLocaleString();
  document.getElementById('hospital-count').textContent = hospitals.toLocaleString();
  const min = Math.min(...values), max = Math.max(...values);
  document.getElementById('hfi-range').textContent = values.length ? `${formatNumber(min, 2)} to ${formatNumber(max, 2)}` : '—';
  updateSummary(tractFeatures.length, hospitals, values);
}

function updateSummary(tracts, hospitals, values) {
  const tractEl = document.getElementById('summary-tract-count');
  const hospitalEl = document.getElementById('summary-hospital-count');
  const rangeEl = document.getElementById('summary-hfi-range');
  if (tractEl) tractEl.textContent = tracts.toLocaleString();
  if (hospitalEl) hospitalEl.textContent = hospitals.toLocaleString();
  if (rangeEl) {
    const clean = values.filter(v => Number.isFinite(v));
    rangeEl.textContent = clean.length ? `${formatNumber(Math.min(...clean), 2)} to ${formatNumber(Math.max(...clean), 2)}` : '—';
  }
}

function drawLegend() {
  const legend = document.getElementById('legend');
  legend.innerHTML = '';
  CONFIG.colors.forEach((color, i) => {
    const low = hfiBreaks[i], high = hfiBreaks[i + 1];
    const row = document.createElement('div');
    row.className = 'legend-row';
    const label = i === 0 ? 'Least fragmented' : (i === CONFIG.colors.length - 1 ? 'Most fragmented' : `Class ${i + 1}`);
    row.innerHTML = `<span class="legend-swatch" style="background:${color}"></span><span><strong>${label}</strong><br>${formatNumber(low, 2)} – ${formatNumber(high, 2)}</span>`;
    legend.appendChild(row);
  });
}

function showFeatureInfo(type, title, rows) {
  const el = document.getElementById('feature-info');
  const table = Object.entries(rows).map(([k, v]) => `<tr><th>${escapeHtml(k)}</th><td>${escapeHtml(v)}</td></tr>`).join('');
  el.innerHTML = `<span class="feature-kicker">${escapeHtml(type)}</span><h2>${escapeHtml(title)}</h2><table class="info-table">${table}</table>`;
  el.classList.add('has-selection');
}

function focusFeatureInfo() {
  const panel = document.querySelector('.explorer-panel');
  const el = document.getElementById('feature-info');
  if (!panel || !el) return;
  const panelBox = panel.getBoundingClientRect();
  const elBox = el.getBoundingClientRect();
  if (elBox.top < panelBox.top || elBox.bottom > panelBox.bottom) {
    el.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
  }
}

function hospitalPopup(row, comm, rating) {
  const tractHfi = numberValue(row.fragmentation);
  return `<div class="popup-card">
    <strong>${escapeHtml(row.name)}</strong>
    <span>${escapeHtml(row.address || '')}${row.city ? `, ${escapeHtml(row.city)}` : ''}</span>
    <span>Communication index: ${formatNumber(comm, 2)}</span>
    <span>CMS rating: ${formatNumber(rating, 0)}</span>
    <span>Linked tract HFI: ${formatNumber(tractHfi, 3)}</span>
  </div>`;
}

function populateHospitalOptions(records) {
  const list = document.getElementById('hospital-options');
  if (!list) return;
  list.innerHTML = '';
  records
    .map(row => row.name)
    .filter(Boolean)
    .sort((a, b) => a.localeCompare(b))
    .forEach(name => {
      const option = document.createElement('option');
      option.value = name;
      list.appendChild(option);
    });
}

function classifyHfi(value) {
  if (!Number.isFinite(value)) return 'No HFI value available';
  if (value >= 1) return 'High';
  if (value >= 0) return 'Moderate';
  if (value <= -1) return 'Least fragmented';
  return 'Low';
}

function interpretHfi(value) {
  if (!Number.isFinite(value)) return 'No HFI value available';
  if (value >= 1) return 'High fragmentation';
  if (value >= 0) return 'Above-average fragmentation';
  if (value <= -1) return 'Low fragmentation';
  return 'Below-average fragmentation';
}

function setStatus(type, text) {
  const el = document.getElementById('data-status');
  el.className = `data-status ${type}`;
  el.textContent = text;
}

function formatNumber(value, digits = 2) {
  return Number.isFinite(value) ? value.toLocaleString(undefined, { maximumFractionDigits: digits, minimumFractionDigits: digits }) : '—';
}

function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>'"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' }[c]));
}
