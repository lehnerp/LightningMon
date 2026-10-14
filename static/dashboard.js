'use strict';

const I18N = {
  en: {
    title:'Lightning Monitor', subtitle:'Live LightningMaps / Blitzortung monitoring · Zabbix · SMTP', live:'LIVE', offline:'OFFLINE',
    language:'Language', switchLight:'Light mode', switchDark:'Dark mode', settings:'Settings', configuration:'CONFIGURATION', runtimeSettings:'Runtime settings',
    settingsHelp:'Edit the complete configuration here. Changes are written to config.json; safe settings are applied immediately.', configFile:'Config file',
    reloadConfig:'Reload', saveApply:'Save & apply', saved:'Configuration saved.', restartNeeded:'Restart required for', invalidJson:'Invalid JSON',
    saveFailed:'Could not save configuration', loadFailed:'Could not load configuration', restartMonitor:'Restart monitor', saveRestart:'Save & restart', restarting:'Restarting monitor…',
    restartFailed:'Could not restart monitor', restartDisabled:'Web restart is disabled.', writesDisabled:'Configuration writes are disabled.', restartConfirm:'Restart the Lightning Monitor now?',
    authRequired:'Password required (web.admin_password).',
    strikes10:'STRIKES · 10 MIN', insideRadius:r=>`within ${r} km`, closest10:'CLOSEST STRIKE · 10 MIN', distancePoint:'distance from monitored point',
    lastStrike:'LAST STRIKE', lastNotification:'last email notification', liveArea:'LIVE MAP', satelliteMap:'Lightning activity',
    r10m:'10 minutes', r1h:'1 hour', r6h:'6 hours', r24h:'24 hours', r7d:'7 days', r30d:'30 days', latestSnapshot:'Open snapshot', recenter:'Recenter',
    monitoredPoint:'monitored point', criticalLegend:r=>`≤ ${r} km critical`, warningLegend:r=>`≤ ${r} km warning`, lightningStrike:'lightning strike', newestStrike:'newest strike',
    timeline:'ACTIVITY TIMELINE', strikesOverTime:'Strikes over time', perBucket:s=>`strikes per ${s}`, otherLegend:'further away', peak:n=>`peak ${n}`, total:n=>`${n} total`,
    strikeLog:'STRIKE HISTORY', recentDetections:'Recent detections', observed:'Observed', distance:'Distance', locality:'Locality', latitude:'Latitude', longitude:'Longitude', zone:'Zone',
    waiting:'Waiting for lightning data…', noStrikes:'No strikes in the selected period.', noStrike:'No strike recorded', resolving:'resolving…', noPlace:'open area / water',
    showingN:(n,total)=>`showing newest ${n} of ${total}`,
    wsConnected:'Live feed connected', wsDisconnected:'Live feed disconnected — reconnecting…', serverOffline:'Dashboard server unreachable — retrying…',
    monitoredLocation:'Monitored location', strikePopup:'Lightning strike',
    critical:'CRITICAL', warning:'WARNING', monitor:'MONITOR', regional:'REGIONAL', satellite:'Satellite', streetMap:'Street map',
    sent:'Sent', failed:'Failed', notSent:'Not sent', disabled:'Disabled',
    stormTrend:'STORM TREND', activityTrend:'ACTIVITY', nearbyActivity:'NEARBY ACTIVITY', systemHealth:'SYSTEM HEALTH', strikesWithinWarn:r=>`strikes within ${r} km / 10 min`,
    approaching:'APPROACHING', receding:'MOVING AWAY', new_activity:'NEW ACTIVITY', quieting:'QUIETING', quiet:'QUIET', stable:'STABLE', increasing:'INCREASING', decreasing:'DECREASING', steady:'STEADY', unknown:'UNKNOWN',
    healthy:'HEALTHY', degraded:'DEGRADED', closestChange:(a,b)=>`${a} km → ${b} km`, noTrendData:'not enough data yet', recentVsPrevious:(a,b)=>`${a} now · ${b} previous`,
    comp:{web:'Web',database:'DB',websocket:'Feed',smtp:'SMTP',zabbix:'Zabbix',geocoder:'Geocoder'},
    secondsAgo:s=>`${s}s ago`, minutesAgo:m=>`${m} min ago`, hoursAgo:(h,m)=>m?`${h}h ${m}m ago`:`${h}h ago`, daysAgo:d=>`${d}d ago`,
    unitMin:m=>`${m} min`, unitH:h=>`${h} h`,
    footerNotice:'Community-sourced lightning data. Do not use this dashboard as an official severe-weather or life-safety warning service.'
  },
  cs: {
    title:'Monitor blesků', subtitle:'Živé sledování LightningMaps / Blitzortung · Zabbix · SMTP', live:'ŽIVĚ', offline:'OFFLINE',
    language:'Jazyk', switchLight:'Světlý režim', switchDark:'Tmavý režim', settings:'Nastavení', configuration:'KONFIGURACE', runtimeSettings:'Nastavení za běhu',
    settingsHelp:'Zde můžete upravit kompletní konfiguraci. Změny se zapíší do config.json; bezpečné volby se použijí ihned.', configFile:'Konfigurační soubor',
    reloadConfig:'Načíst znovu', saveApply:'Uložit a použít', saved:'Konfigurace byla uložena.', restartNeeded:'Je nutný restart pro', invalidJson:'Neplatný JSON',
    saveFailed:'Konfiguraci se nepodařilo uložit', loadFailed:'Konfiguraci se nepodařilo načíst', restartMonitor:'Restartovat monitor', saveRestart:'Uložit a restartovat', restarting:'Monitor se restartuje…',
    restartFailed:'Monitor se nepodařilo restartovat', restartDisabled:'Restart z webu je zakázán.', writesDisabled:'Zápis konfigurace je zakázán.', restartConfirm:'Restartovat Monitor blesků nyní?',
    authRequired:'Je vyžadováno heslo (web.admin_password).',
    strikes10:'ÚDERY · 10 MIN', insideRadius:r=>`v okruhu ${r} km`, closest10:'NEJBLIŽŠÍ ÚDER · 10 MIN', distancePoint:'vzdálenost od sledovaného místa',
    lastStrike:'POSLEDNÍ ÚDER', lastNotification:'poslední e-mailové upozornění', liveArea:'ŽIVÁ MAPA', satelliteMap:'Aktivita blesků',
    r10m:'10 minut', r1h:'1 hodina', r6h:'6 hodin', r24h:'24 hodin', r7d:'7 dní', r30d:'30 dní', latestSnapshot:'Otevřít snímek', recenter:'Vycentrovat',
    monitoredPoint:'sledované místo', criticalLegend:r=>`≤ ${r} km kritická zóna`, warningLegend:r=>`≤ ${r} km výstražná zóna`, lightningStrike:'úder blesku', newestStrike:'nejnovější úder',
    timeline:'ČASOVÁ OSA', strikesOverTime:'Údery v čase', perBucket:s=>`úderů za ${s}`, otherLegend:'vzdálenější', peak:n=>`maximum ${n}`, total:n=>`celkem ${n}`,
    strikeLog:'HISTORIE ÚDERŮ', recentDetections:'Poslední detekce', observed:'Čas detekce', distance:'Vzdálenost', locality:'Lokalita', latitude:'Zem. šířka', longitude:'Zem. délka', zone:'Zóna',
    waiting:'Čekám na data o blescích…', noStrikes:'Ve zvoleném období nebyly zaznamenány žádné údery.', noStrike:'Zatím nebyl zaznamenán žádný úder', resolving:'zjišťuji…', noPlace:'volná plocha / voda',
    showingN:(n,total)=>`zobrazeno nejnovějších ${n} z ${total}`,
    wsConnected:'Živý přenos je připojen', wsDisconnected:'Živý přenos je odpojen — obnovuji spojení…', serverOffline:'Server panelu je nedostupný — zkouším znovu…',
    monitoredLocation:'Sledované místo', strikePopup:'Úder blesku',
    critical:'KRITICKÁ', warning:'VÝSTRAHA', monitor:'DOHLED', regional:'REGIONÁLNÍ', satellite:'Satelitní', streetMap:'Mapa ulic',
    sent:'Odesláno', failed:'Chyba', notSent:'Neodesláno', disabled:'Vypnuto',
    stormTrend:'VÝVOJ BOUŘKY', activityTrend:'AKTIVITA', nearbyActivity:'AKTIVITA V OKOLÍ', systemHealth:'STAV SYSTÉMU', strikesWithinWarn:r=>`úderů do ${r} km / 10 min`,
    approaching:'PŘIBLIŽUJE SE', receding:'VZDALUJE SE', new_activity:'NOVÁ AKTIVITA', quieting:'SLÁBNE', quiet:'KLID', stable:'STABILNÍ', increasing:'ROSTE', decreasing:'KLESÁ', steady:'STABILNÍ', unknown:'NEZNÁMÝ',
    healthy:'V POŘÁDKU', degraded:'OMEZENÝ', closestChange:(a,b)=>`${a} km → ${b} km`, noTrendData:'zatím není dost dat', recentVsPrevious:(a,b)=>`${a} nyní · ${b} předtím`,
    comp:{web:'Web',database:'DB',websocket:'Přenos',smtp:'SMTP',zabbix:'Zabbix',geocoder:'Geokódér'},
    secondsAgo:s=>`před ${s} s`, minutesAgo:m=>`před ${m} min`, hoursAgo:(h,m)=>m?`před ${h} h ${m} min`:`před ${h} h`, daysAgo:d=>`před ${d} d`,
    unitMin:m=>`${m} min`, unitH:h=>`${h} h`,
    footerNotice:'Data o blescích pocházejí z komunitních zdrojů. Panel neslouží jako oficiální výstražný systém pro nebezpečné počasí ani ochranu života.'
  }
};

/* ---------- small helpers ---------- */
const $ = id => document.getElementById(id);
const store = {
  get(k){ try{ return localStorage.getItem(k); }catch(e){ return null; } },
  set(k,v){ try{ localStorage.setItem(k,v); }catch(e){} }
};
function escapeHtml(v){ return String(v ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])); }
function normalizeLang(v){ v=String(v||'').toLowerCase(); return ['cs','cz','cs-cz'].includes(v)?'cs':'en'; }
function fmtKm(v){ return Number.isInteger(v) ? String(v) : Number(v).toFixed(1); }
async function getJson(url, opts){
  const r = await fetch(url, Object.assign({cache:'no-store'}, opts||{}));
  let data = null; try{ data = await r.json(); }catch(e){}
  if(!r.ok && !(r.status===503 && data)) { const err = new Error((data && data.error) || `HTTP ${r.status}`); err.status=r.status; throw err; }
  return data;
}

let currentLang = normalizeLang(store.get('lightning-language') || window.DEFAULT_LANGUAGE || 'en');
const t = (key, ...args) => { const v = I18N[currentLang][key] ?? I18N.en[key] ?? key; return typeof v === 'function' ? v(...args) : v; };
const locale = () => currentLang === 'cs' ? 'cs-CZ' : 'en-GB';

/* ---------- live configuration (radii come from config.json) ---------- */
const cfg = {
  center: [window.MONITOR.lat, window.MONITOR.lon],
  warn: window.MONITOR.warning, crit: window.MONITOR.critical, max: window.MONITOR.max,
  rings: null, geocoding: true
};
function zoneKey(d){ if(d<=cfg.crit)return 'critical'; if(d<=cfg.warn)return 'warning'; if(d<=50)return 'monitor'; return 'regional'; }
const ZONE_COLOR = {critical:'#ff4d5a', warning:'#ff8b38', monitor:'#ffbd43', regional:'#ffffff'};

/* ---------- map ---------- */
const map = L.map('map', {zoomControl:true}).setView(cfg.center, 9);
const satellite = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {maxZoom:19, attribution:'Tiles © Esri'}).addTo(map);
const osm = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {maxZoom:19, attribution:'© OpenStreetMap contributors'});
let layerControl = null;
function rebuildLayerControl(){
  if(layerControl) map.removeControl(layerControl);
  layerControl = L.control.layers({[t('satellite')]:satellite, [t('streetMap')]:osm}, null, {collapsed:true}).addTo(map);
}
const ringLayer = L.layerGroup().addTo(map);
const strikeLayer = L.layerGroup().addTo(map);
const centerMarker = L.circleMarker(cfg.center, {radius:8, color:'#fff', weight:2, fillColor:'#56c7ff', fillOpacity:1}).addTo(map);
let newestMarker = null;

const RING_STYLE = {
  outer:   {color:'#ffffff', weight:1, opacity:.35, fillOpacity:0, dashArray:'6 8'},
  monitor: {color:'#ffbd43', weight:1, opacity:.55, fillOpacity:0, dashArray:'6 8'},
  warning: {color:'#ff8b38', weight:2, opacity:.8,  fillOpacity:.025},
  critical:{color:'#ff4d5a', weight:2, opacity:.95, fillOpacity:.035}
};
function drawRings(rings){
  const sig = JSON.stringify([cfg.center, rings]);
  if(sig === cfg.rings) return;
  cfg.rings = sig; ringLayer.clearLayers();
  rings.forEach(r => L.circle(cfg.center, Object.assign({radius:r.radius_km*1000, interactive:false}, RING_STYLE[r.kind]||RING_STYLE.outer)).addTo(ringLayer));
  centerMarker.setLatLng(cfg.center);
}
drawRings([
  {radius_km:cfg.max, kind:'outer'}, {radius_km:50, kind:'monitor'},
  {radius_km:cfg.warn, kind:'warning'}, {radius_km:cfg.crit, kind:'critical'}
].filter(r => r.radius_km <= cfg.max));

/* ---------- formatting ---------- */
function fmtTime(ts){ if(!ts) return '—'; return new Date(ts*1000).toLocaleString(locale(), {dateStyle:'short', timeStyle:'medium'}); }
function fmtAge(ts){
  if(!ts) return t('noStrike');
  const s = Math.max(0, Math.round(Date.now()/1000 - ts));
  if(s<60) return t('secondsAgo',s); if(s<3600) return t('minutesAgo',Math.floor(s/60));
  if(s<86400) return t('hoursAgo',Math.floor(s/3600),Math.floor((s%3600)/60)); return t('daysAgo',Math.floor(s/86400));
}
function localizeMailStatus(value){
  if(!value) return '—'; const raw = String(value);
  if(/^sent\b/i.test(raw)) return raw.replace(/^sent/i, t('sent'));
  if(/^failed\s*:/i.test(raw)) return t('failed');
  if(/^not sent$/i.test(raw)) return t('notSent');
  if(/^disabled$/i.test(raw)) return t('disabled');
  return raw;
}
function localityHtml(loc){
  if(loc === '—') return `<span class="muted">${t('noPlace')}</span>`;
  if(!loc) return cfg.geocoding ? `<span class="muted">${t('resolving')}</span>` : '—';
  return escapeHtml(loc);
}
function updateLegend(){
  $('legend-critical').textContent = t('criticalLegend', fmtKm(cfg.crit));
  $('legend-warning').textContent = t('warningLegend', fmtKm(cfg.warn));
  $('inside-radius').textContent = t('insideRadius', fmtKm(cfg.max));
  $('within-warn').textContent = t('strikesWithinWarn', fmtKm(cfg.warn));
}

/* ---------- strikes on map + table ---------- */
let latestData = [];
let lastSeenStrikeTs = null;
const TABLE_LIMIT = 150;
function renderStrikes(data){
  strikeLayer.clearLayers();
  if(newestMarker){ map.removeLayer(newestMarker); newestMarker = null; }
  const now = Date.now()/1000;
  const minutes = Number($('range-filter').value);
  const span = Math.max(600, minutes*60);
  // Oldest first so the newest strikes are drawn on top.
  for(let i=data.length-1; i>=0; i--){
    const x = data[i]; const age = Math.max(0, now - x.ts); const fresh = Math.max(0, 1 - age/span);
    L.circleMarker([x.lat, x.lon], {
      radius: 3 + fresh*3, color:'#fff', weight: fresh>.6 ? 1 : 0,
      fillColor: ZONE_COLOR[zoneKey(x.distance_km)], fillOpacity: .25 + fresh*.7
    }).bindPopup(
      `<b>${t('strikePopup')}</b><br>${x.distance_km.toFixed(1)} km<br>${fmtTime(x.ts)}<br>` +
      (x.locality && x.locality!=='—' ? `<b>${escapeHtml(x.locality)}</b><br>` : '') +
      `${x.lat.toFixed(5)}, ${x.lon.toFixed(5)}`
    ).addTo(strikeLayer);
  }
  if(data.length){
    const n = data[0];
    newestMarker = L.marker([n.lat, n.lon], {
      interactive:false, keyboard:false,
      icon: L.divIcon({className:'', html:`<span class="pulse ${zoneKey(n.distance_km)}"></span>`, iconSize:[30,30], iconAnchor:[15,15]})
    }).addTo(map);
  }

  const tbody = $('events');
  if(!data.length){ tbody.innerHTML = `<tr><td colspan="6" class="empty">${t('noStrikes')}</td></tr>`; $('table-note').textContent=''; return; }
  tbody.innerHTML = data.slice(0, TABLE_LIMIT).map(x => {
    const z = zoneKey(x.distance_km);
    return `<tr class="row-${z}"><td>${fmtTime(x.ts)}</td><td><b>${x.distance_km.toFixed(1)} km</b></td><td>${localityHtml(x.locality)}</td>` +
           `<td>${x.lat.toFixed(5)}</td><td>${x.lon.toFixed(5)}</td><td><span class="zone ${z}">${t(z)}</span></td></tr>`;
  }).join('');
  $('table-note').textContent = data.length > TABLE_LIMIT ? t('showingN', TABLE_LIMIT, data.length) : '';
}

/* ---------- timeline (stacked SVG bars) ---------- */
let latestTimeline = null;
function bucketLabel(sec){ return sec < 3600 ? t('unitMin', Math.round(sec/60*10)/10) : t('unitH', Math.round(sec/360)/10); }
function renderTimeline(tl){
  latestTimeline = tl; const host = $('timeline-chart'); if(!tl || !tl.buckets){ host.innerHTML=''; return; }
  const W = Math.max(280, host.clientWidth - 36 || 1000), H = 150, padL = 30, padB = 22, padT = 8, n = tl.buckets.length;
  const totals = tl.buckets.map(b => b.critical + b.warning + b.other);
  const peak = Math.max(0, ...totals); const top = Math.max(4, Math.ceil(peak*1.15));
  const bw = (W - padL) / n; const y = v => padT + (H - padT - padB) * (1 - v/top);
  let svg = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${escapeHtml(t('strikesOverTime'))}">`;
  [0, .5, 1].forEach(f => { const v = Math.round(top*f); const yy = y(v);
    svg += `<line x1="${padL}" x2="${W}" y1="${yy}" y2="${yy}" class="grid"/><text x="${padL-6}" y="${yy+3}" class="axis" text-anchor="end">${v}</text>`; });
  tl.buckets.forEach((b,i) => {
    const x = padL + i*bw + 1; const w = Math.max(1, bw - 2); let base = 0;
    [['critical',b.critical],['warning',b.warning],['other',b.other]].forEach(([k,v]) => {
      if(!v) return; const y1 = y(base+v), y0 = y(base);
      svg += `<rect x="${x.toFixed(1)}" y="${y1.toFixed(1)}" width="${w.toFixed(1)}" height="${Math.max(1,(y0-y1)).toFixed(1)}" class="bar ${k}"><title>${fmtTime(b.t)} · ${v}</title></rect>`;
      base += v;
    });
  });
  const ticks = W < 600 ? 3 : 6;
  for(let k=0;k<=ticks;k++){
    const i = Math.min(n-1, Math.round(k*(n-1)/ticks)); const b = tl.buckets[i];
    const d = new Date(b.t*1000);
    const label = tl.bucket_seconds*n > 86400*2 ? d.toLocaleDateString(locale(), {day:'numeric', month:'numeric'}) : d.toLocaleTimeString(locale(), {hour:'2-digit', minute:'2-digit'});
    const anchor = k === 0 ? 'start' : k === ticks ? 'end' : 'middle';
    const tx = k === 0 ? padL : k === ticks ? W : padL + i*bw + bw/2;
    svg += `<text x="${tx}" y="${H-6}" class="axis" text-anchor="${anchor}">${label}</text>`;
  }
  svg += '</svg>';
  host.innerHTML = svg;
  const total = totals.reduce((a,b)=>a+b,0);
  $('timeline-meta').textContent = `${t('perBucket', bucketLabel(tl.bucket_seconds))} · ${t('peak', peak)} · ${t('total', total)}`;
}

/* ---------- data loaders ---------- */
function setOnline(online){
  $('live-chip').classList.toggle('offline', !online);
  $('live-label').textContent = online ? t('live') : t('offline');
}
let lastStatus = null;
async function loadStatus(){
  const s = await getJson('/api/status'); lastStatus = s; const m = s.metrics;
  cfg.center = [s.center.lat, s.center.lon]; cfg.warn = s.warning_radius_km; cfg.crit = s.critical_radius_km; cfg.max = s.max_radius_km;
  cfg.geocoding = s.geocoding_enabled !== false;
  if(s.rings) drawRings(s.rings);
  updateLegend();
  $('sum-strikes').textContent = m['lightning.strikes.100km.10min'];
  const closest = m['lightning.closest.distance_km'];
  const closestEl = $('sum-closest'); closestEl.textContent = closest >= 0 ? `${closest.toFixed(1)} km` : '—';
  closestEl.className = closest >= 0 ? 'z-' + zoneKey(closest) : '';
  $('sum-last').textContent = s.latest_strike_distance_km != null ? `${s.latest_strike_distance_km.toFixed(1)} km` : '—';
  $('sum-last-detail').textContent = s.latest_strike_time ? `${fmtAge(s.latest_strike_time)} · ${fmtTime(s.latest_strike_time)}` : t('noStrike');
  $('sum-mail').textContent = s.smtp_enabled === false ? t('disabled') : localizeMailStatus(s.last_email_status);
  $('sum-mail').title = s.last_email_status || '';
  setOnline(s.ws_connected);
  $('ws-status').textContent = s.ws_connected ? t('wsConnected') : t('wsDisconnected');
  $('ws-dot').classList.toggle('bad', !s.ws_connected);
  $('version').textContent = s.version ? `v${s.version}` : '';
  notifyNewStrike(s);
}
async function loadStrikes(){
  const minutes = $('range-filter').value;
  latestData = await getJson(`/api/strikes?minutes=${minutes}&limit=2000`);
  renderStrikes(latestData);
}
async function loadTimeline(){ renderTimeline(await getJson(`/api/timeline?minutes=${$('range-filter').value}`)); }
function setIntelClass(el, kind){ el.classList.remove('good','warn','bad','info'); if(kind) el.classList.add(kind); }
async function loadIntelligence(){
  const x = await getJson('/api/intelligence');
  const trendEl = $('intel-trend'), activityEl = $('intel-activity');
  trendEl.textContent = t(x.trend || 'unknown'); activityEl.textContent = t(x.activity_trend || 'unknown');
  setIntelClass(trendEl, x.trend==='approaching'?'bad':(x.trend==='receding'||x.trend==='quieting')?'good':x.trend==='new_activity'?'warn':'info');
  setIntelClass(activityEl, x.activity_trend==='increasing'?'bad':(x.activity_trend==='decreasing'||x.activity_trend==='quiet')?'good':'info');
  $('intel-count25').textContent = x.strikes_25km_10min ?? 0;
  const a = x.previous_closest_km, b = x.recent_closest_km;
  $('intel-trend-detail').textContent = (a!=null && b!=null) ? t('closestChange', a.toFixed(1), b.toFixed(1)) : t('noTrendData');
  $('intel-activity-detail').textContent = t('recentVsPrevious', x.strikes_25km_recent_slice ?? 0, x.strikes_25km_previous_slice ?? 0);
}
async function loadHealth(){
  const h = await getJson('/api/health'); const el = $('health-overall');
  el.textContent = h.ok ? t('healthy') : t('degraded'); setIntelClass(el, h.ok ? 'good' : 'warn');
  const names = t('comp');
  $('health-detail').innerHTML = Object.entries(h.components || {}).map(([k,c]) => {
    const state = c.ok === true ? 'ok' : c.ok === false ? 'bad' : 'off';
    const tip = [c.status, c.error].filter(Boolean).join(' — ');
    return `<span class="chip ${state}" title="${escapeHtml(tip)}">${escapeHtml(names[k] || k)}</span>`;
  }).join('');
}

/* ---------- new-strike attention (tab title flash) ---------- */
const baseTitle = () => t('title');
let titleTimer = null;
function notifyNewStrike(s){
  const ts = s.latest_strike_time, d = s.latest_strike_distance_km;
  if(lastSeenStrikeTs === null){ lastSeenStrikeTs = ts || 0; return; }
  if(!ts || ts <= lastSeenStrikeTs) return;
  lastSeenStrikeTs = ts;
  if(d == null || d > cfg.warn || !document.hidden) return;
  clearInterval(titleTimer); let on = false;
  titleTimer = setInterval(() => { document.title = (on = !on) ? `⚡ ${d.toFixed(1)} km — ${baseTitle()}` : baseTitle(); }, 1000);
}
document.addEventListener('visibilitychange', () => {
  if(!document.hidden){ clearInterval(titleTimer); titleTimer = null; document.title = baseTitle(); refresh(); }
});

/* ---------- language / theme ---------- */
async function persistDashboardLanguage(lang){
  try{
    const r = await fetch('/api/config', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({updates:{localization:{default_language:normalizeLang(lang)}}})});
    if(!r.ok) console.warn('Could not persist dashboard language', r.status);
  }catch(e){ console.warn('Could not persist dashboard language', e); }
}
function applyLanguage(lang, persist=false){
  currentLang = normalizeLang(lang); store.set('lightning-language', currentLang);
  document.documentElement.lang = currentLang;
  document.title = t('title');
  document.querySelectorAll('[data-i18n]').forEach(el => { const v = I18N[currentLang][el.dataset.i18n]; if(typeof v === 'string') el.textContent = v; });
  document.querySelectorAll('.lang-button').forEach(btn => { const active = normalizeLang(btn.dataset.lang) === currentLang; btn.classList.toggle('active', active); btn.setAttribute('aria-pressed', String(active)); });
  $('language-control').setAttribute('aria-label', t('language'));
  $('snapshot-link').href = `/api/snapshot/latest.png?lang=${currentLang}`;
  centerMarker.bindPopup(`<b>${t('monitoredLocation')}</b><br>${cfg.center[0].toFixed(5)}, ${cfg.center[1].toFixed(5)}`);
  rebuildLayerControl(); updateLegend();
  setTheme(document.documentElement.dataset.theme || 'dark', false);
  renderStrikes(latestData); renderTimeline(latestTimeline);
  if(lastStatus) refresh();
  if(persist) persistDashboardLanguage(currentLang);
}
const themeToggle = $('theme-toggle');
function setTheme(theme, save=true){
  document.documentElement.dataset.theme = theme; if(save) store.set('lightning-theme', theme);
  const next = theme === 'light' ? t('switchDark') : t('switchLight');
  $('theme-label').textContent = next; $('theme-icon').textContent = theme === 'light' ? '☾' : '☀';
  themeToggle.title = next; themeToggle.setAttribute('aria-label', next);
}

/* ---------- settings modal ---------- */
let loadedConfig = null;
const settingsModal = $('settings-modal'), settingsEditor = $('config-editor'), settingsMessage = $('settings-message');
function showSettingsMessage(text, kind=''){ settingsMessage.textContent = text || ''; settingsMessage.className = 'settings-message' + (kind ? ' ' + kind : ''); }
function authAware(e, prefix){ return e.status === 401 ? t('authRequired') : `${prefix}: ${e.message}`; }
async function loadConfigEditor(){
  showSettingsMessage('');
  const data = await getJson('/api/config');
  loadedConfig = data.config; settingsEditor.value = JSON.stringify(data.config, null, 2);
  $('config-path').textContent = data.config_path || 'config.json';
  $('settings-save').disabled = data.writable === false;
  $('settings-save-restart').disabled = data.writable === false || data.restart_allowed === false;
  $('settings-restart').disabled = data.restart_allowed === false;
  if(data.restart_allowed === false) showSettingsMessage(t('restartDisabled'), 'warn');
  else if(data.writable === false) showSettingsMessage(t('writesDisabled'), 'warn');
}
async function openSettings(){
  settingsModal.hidden = false; document.body.style.overflow = 'hidden'; settingsEditor.focus();
  try{ await loadConfigEditor(); }catch(e){ showSettingsMessage(authAware(e, t('loadFailed')), 'error'); }
}
function closeSettings(){ settingsModal.hidden = true; document.body.style.overflow = ''; }
async function saveSettings(reloadAfter=true){
  let parsed; try{ parsed = JSON.parse(settingsEditor.value); }catch(e){ showSettingsMessage(`${t('invalidJson')}: ${e.message}`, 'error'); return null; }
  const btn = $('settings-save'), sr = $('settings-save-restart');
  btn.disabled = true; sr.disabled = true; showSettingsMessage('…');
  try{
    const data = await getJson('/api/config', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({updates:parsed})});
    if(!data.ok) throw new Error(data.error || 'error');
    loadedConfig = data.config; settingsEditor.value = JSON.stringify(data.config, null, 2);
    btn.disabled = false; sr.disabled = false;
    const restart = data.restart_required || [];
    if(restart.length) showSettingsMessage(`${t('saved')} ${t('restartNeeded')}: ${restart.join(', ')}`, 'warn');
    else showSettingsMessage(t('saved'), 'ok');
    const configuredLang = normalizeLang(data.config?.localization?.default_language || currentLang);
    if(configuredLang !== currentLang) applyLanguage(configuredLang, false);
    if(reloadAfter && !restart.includes('web.port') && !restart.includes('web.host')) refresh();
    return data;
  }catch(e){ showSettingsMessage(authAware(e, t('saveFailed')), 'error'); btn.disabled = false; sr.disabled = false; return null; }
}
function restartTarget(config){
  const port = Number(config?.web?.port || location.port || (location.protocol === 'https:' ? 443 : 80));
  const defaultPort = (location.protocol === 'https:' && port === 443) || (location.protocol === 'http:' && port === 80);
  return `${location.protocol}//${location.hostname}${defaultPort ? '' : `:${port}`}/`;
}
async function restartMonitor(confirmFirst=true){
  if(confirmFirst && !window.confirm(t('restartConfirm'))) return;
  const target = restartTarget(loadedConfig);
  const rb = $('settings-restart'), sr = $('settings-save-restart'), sb = $('settings-save');
  rb.disabled = sr.disabled = sb.disabled = true; showSettingsMessage(t('restarting'), 'warn');
  try{
    const data = await getJson('/api/restart', {method:'POST', headers:{'Content-Type':'application/json'}, body:'{}'});
    if(!data.ok) throw new Error(data.error || 'error');
    await new Promise(r => setTimeout(r, 1400));
    const deadline = Date.now() + 30000;
    while(Date.now() < deadline){
      try{ const h = await fetch(target + 'api/health', {cache:'no-store'}); if(h.ok || h.status === 503){ location.href = target; return; } }catch(e){}
      await new Promise(r => setTimeout(r, 800));
    }
    location.href = target;
  }catch(e){ showSettingsMessage(authAware(e, t('restartFailed')), 'error'); rb.disabled = sr.disabled = sb.disabled = false; }
}
async function saveAndRestart(){ const data = await saveSettings(false); if(!data) return; loadedConfig = data.config; await restartMonitor(false); }

$('settings-toggle').addEventListener('click', openSettings);
$('settings-close').addEventListener('click', closeSettings);
$('settings-reset').addEventListener('click', () => loadConfigEditor().catch(e => showSettingsMessage(authAware(e, t('loadFailed')), 'error')));
$('settings-save').addEventListener('click', () => saveSettings(true));
$('settings-restart').addEventListener('click', () => restartMonitor(true));
$('settings-save-restart').addEventListener('click', saveAndRestart);
settingsModal.addEventListener('click', e => { if(e.target === settingsModal) closeSettings(); });
document.addEventListener('keydown', e => { if(e.key === 'Escape' && !settingsModal.hidden) closeSettings(); });
settingsEditor.addEventListener('keydown', e => {
  if(e.key === 'Tab'){ e.preventDefault(); const s = settingsEditor.selectionStart; settingsEditor.setRangeText('  ', s, settingsEditor.selectionEnd, 'end'); }
  if((e.ctrlKey || e.metaKey) && e.key === 's'){ e.preventDefault(); saveSettings(true); }
});

/* ---------- refresh loop ---------- */
let refreshing = false;
async function refresh(){
  if(refreshing) return; refreshing = true;
  try{
    await loadStatus();
    await Promise.all([loadStrikes(), loadTimeline(), loadIntelligence(), loadHealth()]);
    $('ws-status').classList.remove('server-down');
  }catch(e){
    console.error(e); setOnline(false);
    $('ws-status').textContent = t('serverOffline'); $('ws-dot').classList.add('bad');
  }finally{ refreshing = false; }
}
$('range-filter').addEventListener('change', () => { store.set('lightning-range', $('range-filter').value); Promise.all([loadStrikes(), loadTimeline()]).catch(console.error); });
let resizeTimer = null;
window.addEventListener('resize', () => { clearTimeout(resizeTimer); resizeTimer = setTimeout(() => renderTimeline(latestTimeline), 150); });
$('recenter').addEventListener('click', () => map.setView(cfg.center, 9));
document.querySelectorAll('.lang-button').forEach(btn => btn.addEventListener('click', () => applyLanguage(btn.dataset.lang, true)));
themeToggle.addEventListener('click', () => setTheme(document.documentElement.dataset.theme === 'light' ? 'dark' : 'light'));

const savedRange = store.get('lightning-range');
if(savedRange && [...$('range-filter').options].some(o => o.value === savedRange)) $('range-filter').value = savedRange;
setTheme(store.get('lightning-theme') || 'dark');
applyLanguage(currentLang, false);
setInterval(() => { $('clock').textContent = new Date().toLocaleTimeString(locale()); }, 1000);
setInterval(() => { if(!document.hidden) refresh(); }, 10000);
refresh();
