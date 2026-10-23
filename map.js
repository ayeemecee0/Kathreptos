/* Katoptron nationwide map + planned-route simulation.
   Source evidence and synthetic observations are deliberately separate. */
(() => {
  'use strict';
  const $ = (id) => document.getElementById(id);
  const CFG = window.KATOPTRON_CONFIG;
  const Geo = window.KatoptronRouteGeometry;
  const MAX_VISIBLE = 1200;
  const CAMERA_NEAR_ROUTE_M = 120; // Demonstration proximity threshold, NOT a device read range.
  const USA_CENTER = [39, -98];
  const state = {
    map: null, pointLayer: null, areaLayer: null, routeLayer: null, simLayer: null,
    visible: [], areas: [], programs: [], agendaMentions: [], route: null, routeRecords: [], routeCoverage: 'unchecked',
    observations: [], replayTimer: null,
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
    add('small', 'Source last checked: ' + shortDate(record.last_source_recheck_at || record.last_confirmed_on));
    add('small', 'Published evidence: ' + shortDate(record.published_at));
    // Distinguish a government's OWN GIS host from an externally hosted
    // Esri layer that the agency independently endorses. Neither statement
    // establishes camera uptime or an actual ALPR read.
    const originalEvidence=safeUrl(record.source_url);
    const arcgisExternal=originalEvidence && /^services[0-9]*\.arcgis\.com$/i
      .test(new URL(originalEvidence).hostname);
    add('small',record.verification_method === 'official_georeferenced_camera_record_v1'
      ? (arcgisExternal
          ? 'Evidence tier: government-endorsed EXTERNAL ArcGIS point; government does not host this source'
          : 'Evidence tier: original government-operated GIS point')
      : 'Evidence tier: corroborated public source');
    const url = safeUrl(record.source_url);
    if (url) {
      const link = add('a', 'Inspect original evidence ↗');
      link.href = url;
      link.target = '_blank';
      link.rel = 'noopener noreferrer';
    }
    const historyButton=add('button','View evidence history');
    historyButton.type='button';
    historyButton.className='history-button';
    historyButton.addEventListener('click',async ()=>{
      historyButton.disabled=true;
      historyButton.textContent='Retrieving history…';
      const q=new URLSearchParams({select:'event_type,recorded_at',
        record_key:'eq.'+record.record_key,order:'recorded_at.desc',limit:'15'});
      try {
        const response=await fetch(CFG.supabaseUrl.replace(/\/$/,'')+
          '/rest/v1/flock_camera_evidence_history?'+q.toString(),
          {headers:{apikey:CFG.supabasePublishableKey},cache:'no-store'});
        if(!response.ok)throw new Error('API HTTP '+response.status);
        const rows=await response.json();
        if(!Array.isArray(rows))throw new Error('Invalid evidence history response');
        const list=document.createElement('ol');
        list.className='evidence-history';
        for(const event of rows){
          const li=document.createElement('li');
          const category={
            published:'Evidence originally published',
            source_rechecked:'Original source rechecked',
            withdrawn:'Record withdrawn'
          }[event.event_type] || 'Evidence event';
          li.textContent=category+' · '+shortDate(event.recorded_at);
          list.append(li);
        }
        if(!rows.length){
          const note=document.createElement('small');
          note.textContent='No public audit entries for this verified record.';
          div.append(note);
        } else div.append(list);
        historyButton.textContent='Evidence history loaded';
      }catch(error){
        historyButton.disabled=false;
        historyButton.textContent='Retry evidence history';
        const status=add('small','History temporarily unavailable: '+error.message);
        status.className='muted';
      }
    });
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
    loadDocumentedPrograms();
    loadNationalSummary();
    loadVerifiedAgendaMentions();
  }
  function renderPrograms() {
    const list=$('programList');
    list.replaceChildren();
    const term=$('programSearch').value.trim().toLowerCase();
    const found=state.programs.filter(p=>
      (p.jurisdiction_label+' '+p.official_claim_summary).toLowerCase().includes(term));
    // Limit initial DOM work while preserving the full searchable source list.
    for(const program of found.slice(0,60)) {
      const item=document.createElement('li');
      const title=document.createElement('strong');
      title.textContent=program.jurisdiction_label;
      const status=document.createElement('span');
      status.className=program.program_status==='terminated_at_source_date'
        ? 'program-ended':'program-documented';
      status.textContent=(program.program_status==='terminated_at_source_date'
        ? 'Program terminated per source · ':'Program documented · ')+shortDate(program.source_date);
      const description=document.createElement('p');
      description.textContent=program.official_claim_summary;
      const evidence=document.createElement('a');
      evidence.textContent='Original government source ↗';
      const original=safeUrl(program.official_evidence_url);
      if(original) {
        evidence.href=original; evidence.target='_blank'; evidence.rel='noopener noreferrer';
      }
      item.append(title,status,description);
      if(original)item.append(evidence);
      list.append(item);
    }
    setText('programStatus',(found.length>60 ? 'Showing first 60 of ' : '')+
      found.length+' dated original-government program record(s). '+
      'These are not verified camera coordinates. Narrow the search for more results.');
  }
  async function loadNationalSummary() {
    if(!CFG?.supabaseUrl || !CFG?.supabasePublishableKey){
      setText('nationalStats','National published evidence counts unavailable.');
      return;
    }
    try {
      const response=await fetch(CFG.supabaseUrl.replace(/\/$/,'')+
        '/rest/v1/flock_public_coverage_stats?select=*',
        {headers:{apikey:CFG.supabasePublishableKey},cache:'no-store'});
      if(!response.ok)throw new Error('HTTP '+response.status);
      const rows=await response.json();
      if(!Array.isArray(rows)||rows.length!==1)
        throw new Error('National evidence response incomplete');
      const metrics=rows[0];
      const keys=['verified_camera_points','verified_point_jurisdictions',
        'verified_area_polygons','documented_government_programs'];
      if(keys.some(key=>!Number.isInteger(Number(metrics[key]))||Number(metrics[key])<0))
        throw new Error('National source counts invalid');
      setText('nationalStats',
        Number(metrics.verified_camera_points).toLocaleString()+
        ' verified camera points in '+Number(metrics.verified_point_jurisdictions)+
        ' sourced jurisdictions nationwide · '+
        Number(metrics.verified_area_polygons)+' documented deployment polygons · '+
        Number(metrics.documented_government_programs)+
        ' government program records. Coverage is incomplete, not zero elsewhere.');
    }catch(error) {
      setText('nationalStats','National published evidence totals unavailable: '+
        error.message+'. Missing counts do not mean no cameras.');
    }
  }
  function renderVerifiedAgendaMentions() {
    const list=$('agendaMapList');
    list.replaceChildren();
    const term=$('agendaMapSearch').value.trim().toLowerCase();
    const matches=state.agendaMentions.filter(m=>
      (m.jurisdiction_label+' '+m.matter_title).toLowerCase().includes(term));
    for(const mention of matches.slice(0,60)) {
      const item=document.createElement('li');
      const title=document.createElement('strong');
      title.textContent=mention.jurisdiction_label;
      const when=document.createElement('span');
      when.className='program-documented';
      when.textContent='Original government agenda · '+shortDate(mention.intro_date);
      const description=document.createElement('p');
      description.textContent=mention.matter_title;
      item.append(title,when,description);
      const url=safeUrl(mention.government_evidence_url);
      if(url) {
        const link=document.createElement('a');
        link.href=url;link.target='_blank';link.rel='noopener noreferrer';
        link.textContent='Original government proceedings ↗';
        item.append(link);
      }
      list.append(item);
    }
    setText('agendaMapStatus',(matches.length>60?'Showing first 60 of ':'')+
      matches.length+' verified government agenda mention(s). '+
      'A mention is not proof of deployment, equipment, or approval.');
  }
  async function loadVerifiedAgendaMentions() {
    if(!CFG?.supabaseUrl || !CFG?.supabasePublishableKey) {
      setText('agendaMapStatus','Original government agenda source unavailable.');
      return;
    }
    const all=[],size=25,cap=2000;
    try {
      for(let offset=0;offset<cap;offset+=size){
        const q=new URLSearchParams({
          select:'tenant,matter_id,jurisdiction_label,matter_title,government_evidence_url,intro_date',
          status:'eq.verified',order:'tenant.asc,matter_id.asc',
          limit:String(size),offset:String(offset)
        });
        const response=await fetch(CFG.supabaseUrl.replace(/\/$/,'')+
          '/rest/v1/verified_flock_agenda_mentions?'+q.toString(),
          {headers:{apikey:CFG.supabasePublishableKey},cache:'no-store'});
        if(!response.ok)throw new Error('Agenda API HTTP '+response.status);
        const rows=await response.json();
        if(!Array.isArray(rows)||rows.length>size)
          throw new Error('Original government agenda response incomplete');
        all.push(...rows);
        if(rows.length<size){
          state.agendaMentions=all;
          renderVerifiedAgendaMentions();
          return;
        }
      }
      throw new Error('Verified government agenda results exceed scan capacity');
    }catch(error){
      setText('agendaMapStatus','Government proceedings unavailable: '+error.message+
        '. Missing records do not establish absence of proceedings.');
    }
  }

  async function loadDocumentedPrograms() {
    if(!CFG?.supabaseUrl || !CFG?.supabasePublishableKey) {
      setText('programStatus','Source configuration unavailable.');
      return;
    }
    // All pages are read with a stable unique key. Do not quietly discard
    // jurisdictions when the published government directory grows beyond 100.
    const pageSize=25,capacity=2000;
    const all=[];
    try {
      for(let offset=0;offset<capacity;offset+=pageSize){
        const query=new URLSearchParams({
          select:'program_key,jurisdiction_label,state_code,program_status,official_evidence_url,official_claim_summary,source_date,reported_camera_count',
          record_status:'eq.verified',order:'program_key.asc',
          limit:String(pageSize),offset:String(offset)
        });
        const response=await fetch(CFG.supabaseUrl.replace(/\/$/,'')+
          '/rest/v1/flock_documented_programs?'+query.toString(),
          {headers:{apikey:CFG.supabasePublishableKey},cache:'no-store'});
        if(!response.ok)throw new Error('Program evidence API HTTP '+response.status);
        const records=await response.json();
        if(!Array.isArray(records)||records.length>pageSize)
          throw new Error('Government program source page invalid');
        all.push(...records);
        if(records.length<pageSize) {
          state.programs=all;
          renderPrograms();
          return;
        }
      }
      throw new Error('Government directory exceeds the verified scan limit');
    }catch(error){
      // An incomplete paged response is UNKNOWN, not evidence of absent
      // programs. Do not replace previous complete evidence with a partial set.
      setText('programStatus','Documented-program directory unavailable: '+error.message);
    }
  }
  function publicCameraUrl(bounds) {
    const query = new URLSearchParams({
      select: 'id,record_key,label,jurisdiction_label,latitude,longitude,location_accuracy,uncertainty_radius_m,source_type,source_url,evidence_summary,last_confirmed_on,last_source_recheck_at,published_at,verification_method',
      verification_status: 'eq.verified',
      latitude: 'gte.' + bounds.south.toFixed(6),
      longitude: 'gte.' + bounds.west.toFixed(6),
      order: 'published_at.desc',
      limit: String(MAX_VISIBLE)
    });
    query.append('latitude', 'lte.' + bounds.north.toFixed(6));
    query.append('longitude', 'lte.' + bounds.east.toFixed(6));
    return CFG.supabaseUrl.replace(/\/$/, '') +
      '/rest/v1/flock_camera_locations?' + query.toString();
  }
  async function cameraRows(bounds, signal) {
    const response = await fetch(publicCameraUrl(bounds), {
      // Publishable API keys are not user JWTs.
      headers: { apikey: CFG.supabasePublishableKey },
      signal, cache:'no-store'
    });
    if (!response.ok) throw new Error('Camera API HTTP ' + response.status);
    const rows = await response.json();
    if (!Array.isArray(rows)) throw new Error('Unexpected camera API response');
    return rows.filter(x => x && validCoord(Number(x.latitude),Number(x.longitude)) &&
      (x.location_accuracy === 'exact' || x.location_accuracy === 'approximate'));
  }
  async function loadRouteEvidence(route) {
    state.routeCoverage='checking';
    state.routeRecords=[];
    setText('nearbyCount','…');
    setText('observationCount','…');
    setText('routeStatus','Checking verified camera evidence across the ENTIRE driving route…');
    try {
      if (!Geo) throw new Error('Route geometry library unavailable');
      const boxes=Geo.corridorBoxes(route.points);
      const collected=new Map();
      // Bounded, small concurrent requests; never silently claim no cameras
      // if any corridor portion fails or hits the query record limit.
      let next=0;
      async function worker() {
        while(next<boxes.length) {
          const box=boxes[next++];
          const rows=await cameraRows(box);
          if(rows.length>=MAX_VISIBLE)
            throw new Error('Camera evidence density exceeds this corridor query limit; analysis incomplete');
          for(const row of rows) collected.set(row.record_key,row);
        }
      }
      await Promise.all(Array.from({length:Math.min(3,boxes.length)},worker));
      if(state.route!==route)return;
      state.routeRecords=[...collected.values()];
      state.routeCoverage='complete';
      computeObservations();
      setText('routeStatus','Checked '+boxes.length+
        ' evidence region(s) across the route. Results are modeled, never actual plate reads. '+
        'Unpublished cameras may still exist.');
    } catch(e) {
      if(state.route!==route)return;
      state.routeCoverage='unavailable';
      state.routeRecords=[];
      setText('nearbyCount','Unknown');
      setText('observationCount','Unknown');
      setText('timelineBadge','DATA INCOMPLETE');
      setText('timelineIntro','Some or all of this journey could not be checked against published records. '+
        'Do not infer that there are no Flock cameras. '+e.message);
      $('timelineEvents').replaceChildren();
      $('play').disabled=true;
      setText('routeStatus','Verified camera coverage unavailable: '+e.message+
        '. Road route remains visible, but detection estimates are disabled.');
    }
  }

  async function loadOfficialAreas(signal,viewport) {
    // Original government polygons may eventually number in the thousands.
    // Read each page to completion, but render only geographic footprints
    // whose bounding rectangles intersect the visible map. Never interpret
    // a truncated list as proof that there are no other deployment areas.
    const pageSize=20,maxRecords=2000;
    const result=[];
    for(let offset=0;offset<maxRecords;offset+=pageSize) {
      const query=new URLSearchParams({
        select:'area_key,jurisdiction_label,area_label,outline_lonlat,evidence_url,evidence_summary,evidence_verified_at',
        geometry_status:'eq.verified',order:'area_key.asc',
        limit:String(pageSize),offset:String(offset)
      });
      const response=await fetch(CFG.supabaseUrl.replace(/\/$/,'')+
        '/rest/v1/flock_documented_coverage_areas?'+query.toString(),
        {headers:{apikey:CFG.supabasePublishableKey},signal,cache:'no-store'});
      if(!response.ok)throw new Error('Area evidence API HTTP '+response.status);
      const records=await response.json();
      if(!Array.isArray(records)||records.length>pageSize)
        throw new Error('Original government area page incomplete');
      for(const area of records) {
        if(!(area && Array.isArray(area.outline_lonlat) &&
          area.outline_lonlat.length>=4 && area.outline_lonlat.length<=250 &&
          area.outline_lonlat.every(vertex=>
            Array.isArray(vertex)&&vertex.length===2&&
            validCoord(Number(vertex[1]),Number(vertex[0]))) &&
          JSON.stringify(area.outline_lonlat[0])===
            JSON.stringify(area.outline_lonlat[area.outline_lonlat.length-1]))) {
          throw new Error('Source-backed deployment polygon malformed');
        }
        const latitudes=area.outline_lonlat.map(pt=>Number(pt[1]));
        const longitudes=area.outline_lonlat.map(pt=>Number(pt[0]));
        if (Math.max(...latitudes)>=viewport.south &&
            Math.min(...latitudes)<=viewport.north &&
            Math.max(...longitudes)>=viewport.west &&
            Math.min(...longitudes)<=viewport.east) {
          result.push(area);
        }
      }
      if(records.length<pageSize)return result;
    }
    throw new Error('Government coverage polygon source scan reached capacity');
  }
  function officialAreaPopup(area) {
    const root=document.createElement('div');
    root.className='camera-popup';
    const title=document.createElement('strong');
    title.textContent=area.area_label;
    const qualifier=document.createElement('p');
    qualifier.textContent='Official documented deployment area, not a camera location. '+
      'No location inside the polygon is proven to contain an active reader.';
    const summary=document.createElement('p');
    summary.textContent=area.evidence_summary;
    const date=document.createElement('small');
    date.textContent='Original area geometry verified: '+shortDate(area.evidence_verified_at);
    root.append(title,qualifier,summary,date);
    const original=safeUrl(area.evidence_url);
    if(original){
      const link=document.createElement('a');
      link.href=original;
      link.target='_blank';link.rel='noopener noreferrer';
      link.textContent='Original government polygon source ↗';
      root.append(document.createElement('br'),link);
    }
    return root;
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
      state.areas = [];
      drawLocations();
      setText('coverageStatus', 'Move the map to a US location to inspect documented coverage.');
      return;
    }
    setText('coverageSpinner', 'Checking live sources…');
    try {
      // Camera points must remain available even if the optional government
      // polygon dataset is not yet reachable through the Data API.
      // Fail the approximate-area indicator separately, never silently
      // converting an unknown area status into a verified zero.
      const [rows,areasResult]=await Promise.all([
        cameraRows({south,north,west,east},state.abort.signal),
        loadOfficialAreas(state.abort.signal,{south,north,west,east}).then(
          value=>({value}),error=>({error}))
      ]);
      if (requestId !== state.requestNumber) return;
      state.visible = rows;
      state.areas = areasResult.value || [];
      updateJurisdictions();
      drawLocations();
      if(areasResult.error) setText('areaCount','Unknown');
      setText('coverageSpinner', 'Live data');
      const shown = state.visible.length + state.areas.length;
      const capped = state.visible.length >= MAX_VISIBLE;
      const areaWarning=areasResult.error
        ? ' Official deployment-area evidence is temporarily unavailable; area coverage is unknown.'
        : '';
      setText('coverageStatus', (shown
        ? String(shown) + (capped ? '+ records in current viewport. Zoom in to reduce the result limit.' :
           ' source-backed entries in the current map view; not an exhaustive camera census.')
        : 'No source-verified camera coordinates in this view yet. This is an evidence gap, NOT evidence that there are no cameras.') + areaWarning);
    } catch (error) {
      if (error.name === 'AbortError' || requestId !== state.requestNumber) return;
      state.visible = [];
      state.areas = [];
      updateJurisdictions();
      drawLocations();
      setText('coverageSpinner', 'Source unavailable');
      setText('coverageStatus', 'Unable to load camera evidence (' +
        error.message + '). Camera coverage is unknown; retry by moving the map.');
    }
  }
  function updateJurisdictions() {
    const select=$('jurisdictionFilter');
    const prior=select.value;
    const jurisdictions=[...new Set([...state.visible,...state.areas]
      .map(x=>x.jurisdiction_label)
      .filter(x=>typeof x==='string'&&x.length<=150))].sort();
    select.replaceChildren();
    const all=document.createElement('option');
    all.value='';all.textContent='All in current map view';
    select.append(all);
    for(const name of jurisdictions){
      const option=document.createElement('option');
      option.value=name;option.textContent=name;
      select.append(option);
    }
    select.value=jurisdictions.includes(prior)?prior:'';
  }
  function recordMatchesFilters(record) {
    const jurisdiction=$('jurisdictionFilter').value;
    const term=$('cameraTextFilter').value.trim().toLocaleLowerCase();
    const searchable=[record.label,record.area_label,record.jurisdiction_label,
      record.evidence_summary].filter(Boolean).join(' ');
    return (!jurisdiction || record.jurisdiction_label===jurisdiction) &&
      (!term || searchable.toLocaleLowerCase().includes(term));
  }
  function drawLocations() {
    if (!state.map) return;
    state.pointLayer.clearLayers();
    state.areaLayer.clearLayers();
    let exact = 0, areas = 0;
    for (const record of state.visible) {
      if (!recordMatchesFilters(record)) continue;
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
    if ($('showApprox').checked) {
      for(const area of state.areas){
        if(!recordMatchesFilters(area))continue;
        const geometry=area.outline_lonlat.map(([lon,lat])=>[Number(lat),Number(lon)]);
        const polygon=L.polygon(geometry,{
          color:'#e3ae62',weight:1.5,dashArray:'5 6',
          fillColor:'#e3ae62',fillOpacity:.13
        });
        // Display the ORIGINAL polygon rather than a fabricated
        // estimated radius around a city or government agency.
        polygon.bindPopup(officialAreaPopup(area));
        polygon.addTo(state.areaLayer);
        areas++;
      }
    }
    setText('exactCount', exact);
    setText('areaCount', areas);
    setText('filterStatus',exact+areas+' verified map entries displayed after filters. '+
      'Location precision is source-specific; zero displayed does not mean no cameras.');
    // Never apply map UI filters to the full-route evidence queries.
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
    return Geo.closestOnRoute(point,points);
  }
  function formatMinutes(value) { return 'T+' + Math.round(value) + ' min'; }
  function computeObservations() {
    if (!state.route || state.routeCoverage!=='complete') return;
    const points = state.route.points;
    let found = 0;
    const observations = [];
    for (const row of state.routeRecords) {
      if (row.location_accuracy !== 'exact') continue;
      const close = nearRoute([Number(row.latitude),Number(row.longitude)],points);
      if (close.distance > CAMERA_NEAR_ROUTE_M) continue;
      found += 1;
      const a=points[close.index],b=points[close.index+1];
      const point=[a[0]+close.fraction*(b[0]-a[0]),
        a[1]+close.fraction*(b[1]-a[1])];
      observations.push({kind:'verified',name:row.label,progress:close.progress,
        point,source:row.source_url});
    }
    const possibleAreas = state.routeRecords.filter(row =>
      row.location_accuracy === 'approximate' &&
      nearRoute([Number(row.latitude),Number(row.longitude)],points).distance <
        Number(row.uncertainty_radius_m) + 1000).length;
    if ($('hypothetical').checked) {
      [0.20,0.45,0.73].forEach((fraction,i)=>{
        observations.push({kind:'hypothetical',name:'Illustrative observation '+(i+1),
          progress:fraction,point:Geo.pointAtProgress(points,fraction),source:null});
      });
    }
    observations.sort((a,b)=>a.progress-b.progress);
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
      const mins=state.route.duration/60 * event.progress;
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
      $('reset').disabled=false;
      $('play').disabled=true;
      await loadRouteEvidence(trip);
      if (state.routeCoverage==='complete') $('play').disabled=false;
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
    state.routeRecords=[];
    state.routeCoverage='unchecked';
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
    $('programSearch').addEventListener('input',renderPrograms);
    $('agendaMapSearch').addEventListener('input',renderVerifiedAgendaMentions);
    $('mapSearchForm').addEventListener('submit',async event=>{
      event.preventDefault();
      const input=$('mapSearch').value.trim();
      if(!input)return;
      setText('mapSearchStatus','Searching US locations…');
      try {
        const result=await geocode(input);
        state.map.setView(result.point,12);
        setText('mapSearchStatus','Map centered on '+result.label+
          '. Camera coverage remains incomplete.');
      }catch(error){
        setText('mapSearchStatus','Map search unavailable: '+error.message);
      }
    });
    $('jurisdictionFilter').addEventListener('change',drawLocations);
    $('cameraTextFilter').addEventListener('input',drawLocations);
    $('showExact').addEventListener('change',drawLocations);
    $('showApprox').addEventListener('change',drawLocations);
    $('hypothetical').addEventListener('change',()=>{
      state.simLayer?.clearLayers();
      if (state.routeCoverage==='complete') computeObservations();
    });
    $('routeForm').addEventListener('submit',planRoute);
    $('sampleRoute').addEventListener('click',()=>{
      $('from').value='Sacramento, California';
      $('to').value='Folsom, California';
      planRoute();
    });
    $('play').addEventListener('click',replay);
    $('reset').addEventListener('click',reset);
    $('viewPilot').addEventListener('click',()=>{
      state.map?.setView([47.858,-121.973],13);
    });
    $('viewColorado').addEventListener('click',()=>{
      state.map?.setView([38.85,-104.75],11);
    });
    $('viewPeoria').addEventListener('click',()=>{
      // Extent from the municipality's published Peoria GIS camera inventory.
      state.map?.fitBounds([[33.54,-112.33],[33.81,-112.18]]);
    });
    $('viewLawrenceville').addEventListener('click',()=>{
      state.map?.fitBounds([[33.908,-84.054],[34.002,-83.94]]);
    });
    $('viewWebster').addEventListener('click',()=>{
      state.map?.fitBounds([[29.503,-95.16],[29.566,-95.088]]);
    });
    $('national').addEventListener('click',()=>{
      state.map?.setView(USA_CENTER,4);
    });
  }
  bind();
  setupMap();
})();
