/* Katoptron nationwide map + planned-route simulation.
   Source evidence and synthetic observations are deliberately separate. */
(() => {
  'use strict';
  const $ = (id) => document.getElementById(id);
  const CFG = window.KATOPTRON_CONFIG;
  const MAX_VISIBLE = 1200;
  const CAMERA_NEAR_ROUTE_M = 120; // Demonstration proximity threshold, NOT a device read range.
  const USA_CENTER = [39, -98];
  const state = {
    map: null, pointLayer: null, areaLayer: null, routeLayer: null, simLayer: null,
    visible: [], route: null, observations: [], replayTimer: null,
    abort: null, requestNumber: 0, lastGeocodeAt: 0, viewportTimer: null
  };

  function setText(id, value) { $(id).textContent = String(value); }
  function shortDate(value) { return value ? String(value).slice(0, 10) : 'Date not documented'; }
  function validCoord(lat, lon) {
    return Number.isFinite(lat) && Number.isFinite(lon) &&
      lat >= 17 && lat <= 72 && lon >= -180 && lon <= -64;
  }
  function safeUrl(raw) {
    try { const url = new URL(raw); return url.protocol === 'https:' ? url.href : null; }
    catch (_) { return null; }
  }
  function popupFor(record) {
    const div = document.createElement('div');
    div.className = 'camera-popup';
    function add(tag, txt) {
      const element = document.createElement(tag);
      element.textContent = txt;
      div.append(element);
      return element;
    }
    add('strong', record.label);
    add('span', record.location_accuracy === 'exact'
      ? 'Source-verified location · actual detections not available'
      : 'Approximate deployment area · NOT an individual camera position');
    add('span', record.jurisdiction_label);
    add('small', record.evidence_summary);
    add('small', 'Last documented: ' + shortDate(record.last_confirmed_on));
    const url = safeUrl(record.source_url);
    if (url) {
      const link = add('a', 'Inspect original evidence ↗');
      link.href = url;
      link.target = '_blank';
      link.rel = 'noopener noreferrer';
    }
    return div;
  }
  function setupMap() {
    if (!window.L) {
      setText('coverageStatus', 'Map library unavailable; try reloading with an internet connection.');
      return;
    }
    const map = L.map('map', {preferCanvas:true, worldCopyJump:false, minZoom:3})
      .setView(USA_CENTER, 4);
    state.map = map;
    L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '© OpenStreetMap contributors', maxZoom: 19
    }).addTo(map);
    state.areaLayer = L.layerGroup().addTo(map);
    state.pointLayer = L.layerGroup().addTo(map);
    state.routeLayer = L.featureGroup().addTo(map);
    state.simLayer = L.layerGroup().addTo(map);
    map.on('moveend', () => {
      clearTimeout(state.viewportTimer);
      state.viewportTimer = setTimeout(loadVisibleLocations, 250);
    });
    loadVisibleLocations();
  }
  async function loadVisibleLocations() {
    if (!state.map || !CFG?.supabaseUrl || !CFG?.supabasePublishableKey) {
      setText('coverageStatus', 'Public database configuration is unavailable.');
      return;
    }
    if (state.abort) state.abort.abort();
    state.abort = new AbortController();
    const requestId = ++state.requestNumber;
    const bounds = state.map.getBounds().pad(0.3);
    const south = Math.max(17, bounds.getSouth());
    const north = Math.min(72, bounds.getNorth());
    const west = Math.max(-180, bounds.getWest());
    const east = Math.min(-64, bounds.getEast());
    if (north < south || east < west) {
      state.visible = [];
      drawLocations();
      setText('coverageStatus', 'Move the map to a US location to inspect documented coverage.');
      return;
    }
    setText('coverageSpinner', 'Checking live sources…');
    const query = new URLSearchParams({
      select: 'id,record_key,label,jurisdiction_label,latitude,longitude,location_accuracy,uncertainty_radius_m,source_type,source_url,evidence_summary,last_confirmed_on',
      verification_status: 'eq.verified',
      latitude: 'gte.' + south.toFixed(6),
      longitude: 'gte.' + west.toFixed(6),
      order: 'published_at.desc',
      limit: String(MAX_VISIBLE)
    });
    // PostgREST supports repeated column filters for bounded coordinates.
    query.append('latitude', 'lte.' + north.toFixed(6));
    query.append('longitude', 'lte.' + east.toFixed(6));
    const url = CFG.supabaseUrl.replace(/\/$/, '') + '/rest/v1/flock_camera_locations?' + query.toString();
    try {
      const response = await fetch(url, {
        headers: {
          apikey: CFG.supabasePublishableKey,
          Authorization: 'Bearer ' + CFG.supabasePublishableKey
        },
        signal: state.abort.signal, cache:'no-store'
      });
      if (!response.ok) throw new Error('Camera API HTTP ' + response.status);
      const rows = await response.json();
      if (requestId !== state.requestNumber) return;
      if (!Array.isArray(rows)) throw new Error('Unexpected camera API response');
      state.visible = rows.filter((x) =>
        x && validCoord(Number(x.latitude), Number(x.longitude)) &&
        (x.location_accuracy === 'exact' || x.location_accuracy === 'approximate'));
      drawLocations();
      setText('coverageSpinner', 'Live data');
      const shown = state.visible.length;
      const capped = shown >= MAX_VISIBLE;
      setText('coverageStatus', shown
        ? String(shown) + (capped ? '+ records in current viewport. Zoom in to reduce the result limit.' :
           ' source-backed entries in the current map view; not an exhaustive camera census.')
        : 'No source-verified camera coordinates in this view yet. This is an evidence gap, NOT evidence that there are no cameras.');
    } catch (error) {
      if (error.name === 'AbortError' || requestId !== state.requestNumber) return;
      state.visible = [];
      drawLocations();
      setText('coverageSpinner', 'Source unavailable');
      setText('coverageStatus', 'Unable to load camera evidence (' +
        error.message + '). Camera coverage is unknown; retry by moving the map.');
    }
  }
  function drawLocations() {
    if (!state.map) return;
    state.pointLayer.clearLayers();
    state.areaLayer.clearLayers();
    let exact = 0, areas = 0;
    for (const record of state.visible) {
      const p = [Number(record.latitude), Number(record.longitude)];
      if (record.location_accuracy === 'exact' && $('showExact').checked) {
        exact += 1;
        L.circleMarker(p, {radius:6,color:'#0c292e',weight:2,fillColor:'#40d8bc',fillOpacity:1})
          .bindPopup(popupFor(record)).addTo(state.pointLayer);
      } else if (record.location_accuracy === 'approximate' && $('showApprox').checked) {
        const radius = Number(record.uncertainty_radius_m);
        if (!(radius >= 250 && radius <= 80000)) continue;
        areas += 1;
        L.circle(p, {radius,color:'#e3ae62',weight:1.5,dashArray:'5 6',
          fillColor:'#e3ae62',fillOpacity:.09})
          .bindPopup(popupFor(record)).addTo(state.areaLayer);
      }
    }
    setText('exactCount', exact);
    setText('areaCount', areas);
    if (state.route) computeObservations();
  }
  function rad(n) { return n * Math.PI / 180; }
  function meters(a,b) {
    const dl = rad(b[0]-a[0]), dlon = rad(b[1]-a[1]);
    const v = Math.sin(dl/2)**2 +
      Math.cos(rad(a[0]))*Math.cos(rad(b[0]))*Math.sin(dlon/2)**2;
    return 6371000 * 2 * Math.asin(Math.min(1,Math.sqrt(v)));
  }
  function kmString(m) {
    if (!Number.isFinite(m)) return '—';
    return (m / 1000).toFixed(m < 10000 ? 1 : 0) + ' km';
  }
  function coordinateInput(text) {
    const match = String(text).trim().match(/^(-?\d{1,2}(?:\.\d+)?)\s*,\s*(-?\d{1,3}(?:\.\d+)?)$/);
    if (!match) return null;
    const p = [Number(match[1]), Number(match[2])];
    return validCoord(...p) ? p : null;
  }
  function sleep(ms) { return new Promise(resolve => setTimeout(resolve,ms)); }
  async function getJson(url, timeoutMs) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeoutMs);
    try {
      const res = await fetch(url, {signal:controller.signal,headers:{Accept:'application/json'}});
      if (!res.ok) throw new Error('External location/routing service returned HTTP '+res.status);
      return await res.json();
    } finally { clearTimeout(timer); }
  }
  async function geocode(input) {
    const coord = coordinateInput(input);
    if (coord) return {point:coord,label:input + ' (coordinates)'};
    const q = input.trim();
    if (q.length < 3 || q.length > 160) throw new Error('Enter a more specific location.');
    // The Photon shared demo is rate-limited and is for a low-volume beta only.
    const wait = Math.max(0,1100-(Date.now()-state.lastGeocodeAt));
    if (wait) await sleep(wait);
    state.lastGeocodeAt = Date.now();
    const url = 'https://photon.komoot.io/api/?limit=5&lang=en&q=' + encodeURIComponent(q);
    const data = await getJson(url,13000);
    const features = (data.features || []).filter(feature => {
      const coords = feature.geometry?.coordinates;
      return Array.isArray(coords) && validCoord(Number(coords[1]),Number(coords[0])) &&
        String(feature.properties?.countrycode||'').toUpperCase() === 'US';
    });
    if (!features.length) throw new Error('No US location found for "' + q + '". Try a street address or lat,lon.');
    const f = features[0], p = f.properties || {};
    return {point:[Number(f.geometry.coordinates[1]),Number(f.geometry.coordinates[0])],
      label:[p.name,p.city,p.state].filter(Boolean).filter((s,i,arr)=>arr.indexOf(s)===i).join(', ')||q};
  }
  async function routing(from,to) {
    const a = from.point, b = to.point;
    const path = String(a[1]) + ',' + String(a[0]) + ';' + String(b[1]) + ',' + String(b[0]);
    const url = 'https://router.project-osrm.org/route/v1/driving/' + path +
      '?overview=full&geometries=geojson&steps=false';
    const data = await getJson(url,22000);
    const trip = data.routes?.[0];
    if (data.code !== 'Ok' || !trip || !Array.isArray(trip.geometry?.coordinates))
      throw new Error('No driving route was returned. Try more specific destinations.');
    const points = trip.geometry.coordinates.map(p=>[Number(p[1]),Number(p[0])])
      .filter(p=>Number.isFinite(p[0])&&Number.isFinite(p[1]));
    if (points.length < 2 || !Number.isFinite(trip.distance) || !Number.isFinite(trip.duration))
      throw new Error('The routing service did not provide reliable road geometry.');
    return {points,distance:trip.distance,duration:trip.duration,from:from.label,to:to.label};
  }
  function sampleIndex(points, proportion) {
    return points[Math.min(points.length-1,Math.round(proportion*(points.length-1)))];
  }
  function nearRoute(point,points) {
    let best = Infinity, bestIdx = -1;
    for (let i=0;i<points.length;i++) {
      const d = meters(point,points[i]);
      if (d < best) {best=d; bestIdx=i;}
    }
    return {distance:best,index:bestIdx};
  }
  function formatMinutes(value) { return 'T+' + Math.round(value) + ' min'; }
  function computeObservations() {
    if (!state.route) return;
    const points = state.route.points;
    let found = 0;
    const observations = [];
    for (const row of state.visible) {
      if (row.location_accuracy !== 'exact') continue;
      const close = nearRoute([Number(row.latitude),Number(row.longitude)],points);
      if (close.distance > CAMERA_NEAR_ROUTE_M) continue;
      found += 1;
      observations.push({kind:'verified',name:row.label,index:close.index,
        point:points[close.index],source:row.source_url});
    }
    const possibleAreas = state.visible.filter(row =>
      row.location_accuracy === 'approximate' &&
      nearRoute([Number(row.latitude),Number(row.longitude)],points).distance <
        Number(row.uncertainty_radius_m) + 1000).length;
    if ($('hypothetical').checked) {
      [0.20,0.45,0.73].forEach((fraction,i)=>{
        const index = Math.round(fraction*(points.length-1));
        observations.push({kind:'hypothetical',name:'Illustrative observation '+(i+1),
          index,point:sampleIndex(points,fraction),source:null});
      });
    }
    observations.sort((a,b)=>a.index-b.index);
    state.observations = observations;
    setText('nearbyCount',found);
    setText('observationCount',observations.length);
    setText('timelineBadge',observations.length+' MODELED EVENTS');
    const areaNote = possibleAreas ?
      String(possibleAreas)+' approximate mapped area(s) intersect the journey; no camera sighting is inferred there. ' : '';
    setText('timelineIntro',areaNote+'Potential events are estimates only. '+String(found)+
      ' documented exact point(s) lie within a hypothetical 120 m proximity band (NOT a camera read-range claim).'+
      ($('hypothetical').checked?' Three wholly fictional sample observations are also shown.':''));
    renderTimeline();
  }
  function renderTimeline(limit=state.observations.length) {
    $('timelineEvents').replaceChildren();
    const subset = state.observations.slice(0,Math.min(limit,150));
    if (!subset.length) {
      const li=document.createElement('li');
      li.textContent='No verified camera encounters are established along this route with the current dataset. That does NOT establish surveillance-free travel.';
      $('timelineEvents').append(li);
      return;
    }
    for (const event of subset) {
      const li=document.createElement('li');
      if (event.kind==='verified') li.className='verified';
      const bold=document.createElement('strong');
      const mins=state.route.duration/60 * event.index/Math.max(1,state.route.points.length-1);
      bold.textContent=formatMinutes(mins)+' · '+(event.kind==='verified'?'Potential camera proximity':'Fictional sample');
      const sub=document.createElement('small');
      sub.textContent=event.kind==='verified'
        ?event.name+' · Synthetic observation only; detection NOT verified'
        :'Not a documented camera location or real detection';
      li.append(bold,sub);$('timelineEvents').append(li);
    }
  }
  function renderRoute() {
    state.routeLayer.clearLayers();
    state.simLayer.clearLayers();
    const trip = state.route;
    if (!trip) return;
    L.polyline(trip.points,{color:'#52bce2',weight:5,opacity:.9})
      .addTo(state.routeLayer);
    L.circleMarker(trip.points[0],{radius:8,color:'#0a2931',
      fillColor:'#5edcbd',fillOpacity:1,weight:2}).bindPopup('Starting location')
      .addTo(state.routeLayer);
    L.circleMarker(trip.points[trip.points.length-1],
      {radius:8,color:'#0a2931',fillColor:'#eab76c',fillOpacity:1,weight:2})
      .bindPopup('Destination').addTo(state.routeLayer);
    state.map.fitBounds(state.routeLayer.getBounds().pad(.14));
  }
  function stopReplay() { if (state.replayTimer) clearInterval(state.replayTimer); state.replayTimer=null; }
  function replay() {
    if (!state.route) return;
    stopReplay();state.simLayer.clearLayers();
    let idx=0;
    const events=state.observations;
    renderTimeline(0);
    if (!events.length) {
      setText('routeStatus','No synthetic observations to replay. Camera coverage may be undocumented.');
      return;
    }
    setText('routeStatus','Replaying synthetic potential encounters. This is not Flock tracking data.');
    function frame() {
      if (idx>=events.length) {
        stopReplay();
        setText('routeStatus','Replay complete. These are modeled observations, not real plate reads.');
        return;
      }
      const event=events[idx++];
      const color=event.kind==='verified'?'#51d9be':'#da86db';
      L.circleMarker(event.point,{radius:10,color:'#ffffff',weight:2,
        fillColor:color,fillOpacity:.9}).bindPopup(
          event.kind==='verified'?'Modeled sighting at a documented location':
          'Wholly hypothetical sample sighting').addTo(state.simLayer);
      renderTimeline(idx);
    }
    frame();
    state.replayTimer=setInterval(frame,Math.max(400,2400/Math.max(1,events.length)));
  }
  async function planRoute(ev) {
    if (ev) ev.preventDefault();
    if (!state.map) return;
    const from=$('from').value.trim(), to=$('to').value.trim();
    if (!from || !to) return;
    $('planRoute').disabled=true;
    stopReplay();
    setText('routeStatus','Resolving US destinations; contacting routing service…');
    try {
      const a=await geocode(from);
      const b=await geocode(to);
      const trip=await routing(a,b);
      state.route=trip;
      setText('routeDistance',kmString(trip.distance));
      setText('routeStatus','Road route loaded: '+a.label+' → '+b.label+
        '. No license plate or location history is stored by Katoptron.');
      renderRoute();
      await loadVisibleLocations();
      computeObservations();
      $('play').disabled=false;
      $('reset').disabled=false;
      setText('mapLabel','Driving route: '+a.label+' → '+b.label);
    } catch (error) {
      setText('routeStatus','Route unavailable: '+error.message+
        ' No straight-line route or guessed detections will be displayed.');
    } finally { $('planRoute').disabled=false; }
  }
  function reset() {
    stopReplay();
    state.simLayer.clearLayers();
    state.routeLayer.clearLayers();
    state.route=null;
    state.observations=[];
    $('play').disabled=true;$('reset').disabled=true;
    setText('routeDistance','—');setText('nearbyCount','—');
    setText('observationCount','—');setText('timelineBadge','NO ROUTE YET');
    setText('timelineIntro','Route planning uses real street geometry when the external router is available. A modeled observation is an illustration, not a record retrieved from Flock.');
    $('timelineEvents').replaceChildren();
    setText('routeStatus','Route cleared. No personal route details were saved by Katoptron.');
    setText('mapLabel','Nationwide view · Camera inventory incomplete');
  }
  function bind() {
    $('showExact').addEventListener('change',drawLocations);
    $('showApprox').addEventListener('change',drawLocations);
    $('hypothetical').addEventListener('change',()=>{
      state.simLayer?.clearLayers();
      if (state.route) computeObservations();
    });
    $('routeForm').addEventListener('submit',planRoute);
    $('sampleRoute').addEventListener('click',()=>{
      $('from').value='Sacramento, California';
      $('to').value='Folsom, California';
      planRoute();
    });
    $('play').addEventListener('click',replay);
    $('reset').addEventListener('click',reset);
    $('national').addEventListener('click',()=>{
      state.map?.setView(USA_CENTER,4);
    });
  }
  bind();
  setupMap();
})();
