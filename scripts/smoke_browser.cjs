/* Browser release check; OSRM mocked only for deterministic route geometry. */
const {chromium}=require('playwright');
const assert=require('node:assert/strict');
(async()=>{
 const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
 const page=await browser.newPage({viewport:{width:1440,height:960}});
 const errors=[];page.on('pageerror',e=>errors.push(e.message));
 try{
  // The legacy smoke intentionally mocks demo endpoints, independent of
  // which real provider production uses. No real Geoapify credits are spent.
  await page.route('**/config.js',async route=>{
    const response=await route.fetch();
    let body=await response.text();
    body=body.replace(/locationProvider:\s*'[^']+'/,
      "locationProvider: 'demo'");
    body=body.replace(/geoapifyPublicKey:\s*'[^']*'/,
      "geoapifyPublicKey: ''");
    await route.fulfill({status:200,contentType:'application/javascript',body});
  });
  await page.goto(process.env.KATOPTRON_SMOKE_BASE||'https://ayeemecee0.github.io/Katoptron/',{waitUntil:'domcontentloaded',timeout:45000});
  await page.waitForFunction(()=>document.querySelector('#coverageSpinner')?.textContent==='Live data',{timeout:30000});
  await page.waitForFunction(()=>document.querySelector('#nationalStats')?.textContent?.includes('verified camera points in'),{timeout:20000});
  assert.ok((await page.locator('#nationalStats').textContent()).includes('Coverage is incomplete'));
  // The new corroborated tier is opt-in and must be RLS-filtered in the
  // browser. Candidate sources themselves remain inaccessible publicly.
  assert.equal(await page.locator('#showProvisional').isChecked(),false);
  const tierSecurity=await page.evaluate(async()=>{
    const c=window.KATOPTRON_CONFIG;
    const h={apikey:c.supabasePublishableKey};
    const view=await fetch(c.supabaseUrl+'/rest/v1/flock_public_tiered_camera_points?select=case_key,evidence_tier&limit=20',
      {headers:h,cache:'no-store'});
    if(!view.ok)throw Error('Tiered public read HTTP '+view.status);
    const items=await view.json();
    const privateEvidence=await fetch(c.supabaseUrl+
      '/rest/v1/flock_point_evidence_attestations?select=evidence_key&limit=1',
      {headers:h,cache:'no-store'});
    return {items,privateEvidenceStatus:privateEvidence.status};
  });
  assert.ok(Array.isArray(tierSecurity.items));
  assert.ok(tierSecurity.items.every(item=>
    item.evidence_tier==='government_verified' ||
    item.evidence_tier==='independently_corroborated'));
  assert.ok(tierSecurity.privateEvidenceStatus===401 || tierSecurity.privateEvidenceStatus===403);
  await page.locator('#showProvisional').check();
  await page.locator('#showProvisional').uncheck();
  await page.waitForFunction(()=>document.querySelector('#stateEvidenceStatus')?.textContent?.includes('states with published'),{timeout:20000});
  assert.ok((await page.locator('#stateEvidenceStatus').textContent()).includes('evidence unknown'));
  assert.ok(await page.locator('#stateEvidenceList > li').count()>=12);
  const states=await page.locator('#stateEvidenceList').textContent();
  assert.ok(states.includes('CA')&&states.includes('MN')&&states.includes('ME')&&states.includes('NC')&&states.includes('NM')&&states.includes('VA')&&states.includes('FL')&&states.includes('NY'));
  assert.ok(states.includes('actual coverage unknown'));
  assert.ok(states.includes('reported terminated'));
  await page.getByRole('button',{name:/Explore Monroe/}).click();
  await page.waitForFunction(()=>Number(document.querySelector('#exactCount')?.textContent)>=18,{timeout:25000});
  await page.getByRole('button',{name:/Explore El Paso County/}).click();
  await page.waitForFunction(()=>Number(document.querySelector('#exactCount')?.textContent)>=16,{timeout:25000});
  await page.getByRole('button',{name:/Explore Peoria/}).click();
  await page.waitForFunction(()=>Number(document.querySelector('#exactCount')?.textContent)>=74,{timeout:25000});
  // Independently verified council agenda mentions are NOT camera installations.
  await page.waitForFunction(()=>document.querySelector('#agendaMapStatus')?.textContent?.includes('agenda mention'),{timeout:20000});
  await page.locator('#agenda-map-heading').click();
  assert.ok(await page.locator('#agendaMapList > li').count()>=1);
  await page.locator('#agendaMapSearch').fill('Oakland');
  assert.ok((await page.locator('#agendaMapList').textContent()).includes('Oakland'));
  await page.locator('#agendaMapSearch').fill('');
  // Public programs are dated records, never synthetic/official GIS camera pins.
  await page.waitForFunction(()=>document.querySelector('#programStatus')?.textContent?.includes('record(s)'),{timeout:18000});
  assert.ok(Number(await page.locator('#programList > li').count())>=20);
  await page.locator('#programSearch').fill('Los Altos Hills');
  assert.equal(await page.locator('#programList > li').count(),1);
  assert.ok((await page.locator('#programList').textContent()).includes('terminated'));
  await page.locator('#programSearch').fill('Leander');
  assert.equal(await page.locator('#programList > li').count(),1);
  assert.ok((await page.locator('#programList').textContent()).includes('terminated'));
  await page.locator('#programSearch').fill('Shakopee');
  assert.equal(await page.locator('#programList > li').count(),1);
  assert.ok((await page.locator('#programList').textContent()).includes('offline'));
  await page.locator('#programSearch').fill('Asheville');
  assert.equal(await page.locator('#programList > li').count(),1);
  assert.ok((await page.locator('#programList').textContent()).includes('terminated'));
  await page.locator('#programSearch').fill('Seabrook');
  assert.equal(await page.locator('#programList > li').count(),1);
  assert.ok((await page.locator('#programList').textContent()).includes('eight'));
  await page.locator('#programSearch').fill('Liberty Hill');
  assert.equal(await page.locator('#programList > li').count(),1);
  assert.ok((await page.locator('#programList').textContent()).includes('removed all cameras'));
  await page.locator('#programSearch').fill('Panama City');
  assert.equal(await page.locator('#programList > li').count(),1);
  assert.ok((await page.locator('#programList').textContent()).includes('remaining city cameras'));
  await page.locator('#programSearch').fill('Poughkeepsie');
  assert.equal(await page.locator('#programList > li').count(),1);
  assert.ok((await page.locator('#programList').textContent()).includes('intended to veto'));
  await page.locator('#programSearch').fill('');
  // Jurisdiction and label filters apply only to map display, not source data.
  await page.locator('#jurisdictionFilter').selectOption('Peoria, AZ');
  await page.waitForFunction(()=>Number(document.querySelector('#exactCount')?.textContent)>=74,{timeout:25000});
  await page.locator('#cameraTextFilter').fill('not-a-valid-government-camera-label');
  await page.waitForFunction(()=>document.querySelector('#exactCount')?.textContent==='0',{timeout:6000});
  await page.locator('#cameraTextFilter').fill('');
  await page.locator('#jurisdictionFilter').selectOption('');
  await page.locator('#mapSearch').fill('33.67,-112.29');
  await page.locator('#mapSearchForm button').click();
  await page.waitForFunction(()=>document.querySelector('#mapSearchStatus')?.textContent?.includes('Map centered'),{timeout:8000});
  // Public evidence history exposes verified records, not unpublished candidates.
  const audit=await page.evaluate(async()=>{
    const c=window.KATOPTRON_CONFIG;
    const url=c.supabaseUrl+'/rest/v1/flock_camera_evidence_history?select=event_type,recorded_at&limit=3';
    const res=await fetch(url,{headers:{apikey:c.supabasePublishableKey}});
    if(!res.ok)throw Error('Evidence history HTTP '+res.status);
    return res.json();
  });
  assert.ok(audit.length>0 && audit.every(x=>x.event_type==='published'||x.event_type==='source_rechecked'));
  await page.getByRole('button',{name:/Explore Lawrenceville/}).click();
  await page.waitForFunction(()=>Number(document.querySelector('#exactCount')?.textContent)>=45,{timeout:25000});
  await page.getByRole('button',{name:/Explore Webster/}).click();
  await page.waitForFunction(()=>Number(document.querySelector('#exactCount')?.textContent)>=53,{timeout:25000});
  await page.getByRole('button',{name:/Explore Newport Beach/}).click();
  await page.waitForFunction(()=>Number(document.querySelector('#exactCount')?.textContent)>=69,{timeout:25000});
  const point=await page.evaluate(async()=>{
   const c=window.KATOPTRON_CONFIG;
   const url=c.supabaseUrl+'/rest/v1/flock_camera_locations?select=latitude,longitude&jurisdiction_label=eq.El%20Paso%20County%2C%20CO&verification_status=eq.verified&limit=1';
   const res=await fetch(url,{headers:{apikey:c.supabasePublishableKey}});
   if(!res.ok)throw Error('Public API HTTP '+res.status);
   const rows=await res.json();
   if(!rows.length)throw Error('No El Paso public camera point');
   return rows[0];
  });
  const lat=Number(point.latitude),lon=Number(point.longitude);
  assert.ok(Number.isFinite(lat)&&Number.isFinite(lon));
  await page.route('https://router.project-osrm.org/**',async route=>{
   await route.fulfill({status:200,contentType:'application/json',headers:{'access-control-allow-origin':'*'},
    body:JSON.stringify({code:'Ok',routes:[{distance:2000,duration:160,
      geometry:{type:'LineString',coordinates:[[lon-.01,lat],[lon,lat],[lon+.01,lat]]}},
      {distance:3200,duration:260,
      geometry:{type:'LineString',coordinates:[[lon-.01,lat],[lon,lat+.025],[lon+.01,lat]]}}]})});
  });
  await page.locator('#from').fill(String(lat)+','+String(lon-.01));
  await page.locator('#to').fill(String(lat)+','+String(lon+.01));
  await page.locator('#planRoute').click();
  await page.waitForFunction(()=>Number(document.querySelector('#nearbyCount')?.textContent)>=1,{timeout:25000});
  assert.ok(Number(await page.locator('#observationCount').textContent())>=1);
  assert.equal(await page.locator('#routeChoice option').count(),2);
  assert.equal(await page.locator('#routeChoice').isDisabled(),false);
  await page.waitForFunction(()=>document.querySelector('#comparisonStatus')?.textContent?.includes('2/2 driving routes completely checked'),{timeout:30000});
  assert.equal(await page.locator('#routeComparisonList li').count(),2);
  const compared=await page.locator('#routeComparisonList li button').allTextContents();
  assert.ok(compared.every(s=>s.includes('documented camera point(s)')));
  assert.ok(compared.every(s=>s.includes('approximate area(s)')));
  assert.ok((await page.locator('#comparisonStatus').textContent()).includes('do not predict detection'));
  const firstRouteCount=(await page.locator('#nearbyCount').textContent()).trim();
  await page.locator('#routeChoice').selectOption('1');
  await page.waitForFunction(()=>document.querySelector('#routeStatus')?.textContent?.startsWith('Checked '),{timeout:25000});
  assert.ok((await page.locator('#routeDistance').textContent()).includes('3.2 km'));
  assert.equal(await page.locator('#routeComparisonList li button[aria-pressed="true"]').count(),1);
  assert.ok((await page.locator('#routeComparisonList li:nth-child(2)').textContent()).includes('Selected'));
  assert.notEqual((await page.locator('#nearbyCount').textContent()).trim(),'Unknown');
  await page.locator('#routeChoice').selectOption('0');
  await page.waitForFunction(()=>document.querySelector('#routeStatus')?.textContent?.startsWith('Checked '),{timeout:25000});
  assert.ok(Number(await page.locator('#nearbyCount').textContent())>=1);
  // A -> B -> A before either replacement evidence fetch necessarily finishes:
  // no canceled response may overwrite the active A timeline.
  await page.locator('#routeChoice').selectOption('1');
  await page.locator('#routeChoice').selectOption('0');
  await page.waitForFunction(()=>document.querySelector('#routeStatus')?.textContent?.startsWith('Checked '),{timeout:25000});
  assert.ok(Number(await page.locator('#nearbyCount').textContent())>=1);
  assert.equal(await page.locator('#play').isDisabled(),false);
  assert.equal(await page.locator('#hypothetical').isChecked(),false);
  const intro=await page.locator('#timelineIntro').textContent();
  assert.ok(intro.includes('NOT a camera read-range'),intro);
  assert.equal(await page.locator('#play').isDisabled(),false);
  await page.locator('#play').click();
  await page.waitForTimeout(250);
  // Second attempt fails. First route's drawn evidence must not remain
  // associated with the newly entered start/destination.
  await page.route('https://router.project-osrm.org/**',async route=>{
    await route.fulfill({status:200,contentType:'application/json',
      headers:{'access-control-allow-origin':'*'},
      body:JSON.stringify({code:'NoRoute',routes:[]})});
  });
  await page.locator('#from').fill('38.5816,-121.4944');
  await page.locator('#to').fill('38.6779,-121.1761');
  await page.locator('#planRoute').click();
  await page.waitForFunction(()=>
    document.querySelector('#routeStatus')?.textContent?.startsWith('Route unavailable:'),
    {timeout:12000});
  assert.equal(await page.locator('#routeComparisonList li').count(),0,
    'Failed second trip reused first trip evidence');
  assert.equal(await page.locator('#play').isDisabled(),true,
    'Old simulated detections could still be replayed');
  assert.equal((await page.locator('#routeDistance').textContent()).trim(),'—',
    'Old route distance was shown for a failed second trip');
  assert.equal((await page.locator('#nearbyCount').textContent()).trim(),'Unknown');
  await page.locator('#reset').click();
  assert.equal(await page.locator('#play').isDisabled(),true);
  assert.equal((await page.locator('#observationCount').textContent()).trim(),'—');
  assert.equal(await page.locator('#routeComparisonList li').count(),0);
  assert.ok((await page.locator('#comparisonStatus').textContent()).includes('Plan a route'));
  // Ambiguous city names never silently select Photon result #1.
  await page.route('https://photon.komoot.io/api/**',async route=>{
    await route.fulfill({status:200,contentType:'application/json',
      headers:{'access-control-allow-origin':'*'},
      body:JSON.stringify({features:[
        {geometry:{type:'Point',coordinates:[-89.64,39.78]},
         properties:{name:'Springfield',state:'Illinois',countrycode:'US'}},
        {geometry:{type:'Point',coordinates:[-93.29,37.21]},
         properties:{name:'Springfield',state:'Missouri',countrycode:'US'}}
      ]})});
  });
  await page.locator('#from').fill('Springfield');
  await page.locator('#to').fill('37.21,-93.28');
  await page.locator('#planRoute').click();
  await page.waitForFunction(()=>document.querySelector('#routeStatus')?.textContent?.includes('No location was guessed'),
    {timeout:14000});
  assert.equal(await page.locator('#fromMatch').isVisible(),true);
  assert.equal(await page.locator('#fromMatch option').count(),3);
  assert.equal(await page.locator('#routeComparisonList li').count(),0);
  assert.equal(await page.locator('#play').isDisabled(),true);
  await page.locator('#fromMatch').selectOption('1');
  assert.ok((await page.locator('#fromMatch option:checked').textContent()).includes('Missouri'));
  let selectedRouteRequest='';
  await page.route('https://router.project-osrm.org/**',async route=>{
    selectedRouteRequest=route.request().url();
    await route.fulfill({status:200,contentType:'application/json',
      headers:{'access-control-allow-origin':'*'},
      body:JSON.stringify({code:'NoRoute',routes:[]})});
  });
  await page.locator('#planRoute').click();
  await page.waitForFunction(()=>document.querySelector('#routeStatus')?.textContent?.startsWith('Route unavailable:'),
    {timeout:11000});
  assert.ok(selectedRouteRequest.includes('-93.29,37.21;'),selectedRouteRequest);
  await page.locator('#from').fill('Springfield, Illinois');
  assert.equal(await page.locator('#fromMatch').isVisible(),false);
  let throttledCalls=0;
  await page.route('https://router.project-osrm.org/**',async route=>{
    throttledCalls++;
    await route.fulfill({status:429,contentType:'application/json',
      headers:{'access-control-allow-origin':'*'},body:'{"error":"rate limited"}'});
  });
  await page.locator('#from').fill('38.5816,-121.4944');
  await page.locator('#to').fill('38.6779,-121.1761');
  await page.locator('#planRoute').click();
  await page.waitForFunction(()=>document.querySelector('#routeStatus')?.textContent?.includes('rate limited'),{timeout:12000});
  assert.ok((await page.locator('#providerStatus').textContent()).includes('DEGRADED'));
  assert.equal(await page.locator('#routeComparisonList li').count(),0);
  await page.locator('#planRoute').click();
  await page.waitForFunction(()=>document.querySelector('#routeStatus')?.textContent?.includes('temporarily unavailable'),{timeout:12000});
  assert.equal(throttledCalls,1,'Cooldown must not hammer shared demos');
  assert.deepEqual(errors,[]);
  console.log('BROWSER SMOKE PASSED: 6 GIS sources, sourced programs, map filters/search, public history, route evidence, replay and reset');
 }catch(e){
  console.error('BROWSER SMOKE FAILED',e.stack||e);
  await page.screenshot({path:'katoptron-smoke-failure.png',fullPage:true}).catch(()=>{});
  process.exitCode=1;
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
