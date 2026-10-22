/* Browser release check; OSRM mocked only for deterministic route geometry. */
const {chromium}=require('playwright');
const assert=require('node:assert/strict');
(async()=>{
 const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
 const page=await browser.newPage({viewport:{width:1440,height:960}});
 const errors=[];page.on('pageerror',e=>errors.push(e.message));
 try{
  await page.goto('https://ayeemecee0.github.io/Katoptron/',{waitUntil:'domcontentloaded',timeout:45000});
  await page.waitForFunction(()=>document.querySelector('#coverageSpinner')?.textContent==='Live data',{timeout:30000});
  await page.getByRole('button',{name:/Explore Monroe/}).click();
  await page.waitForFunction(()=>Number(document.querySelector('#exactCount')?.textContent)>=18,{timeout:25000});
  await page.getByRole('button',{name:/Explore El Paso County/}).click();
  await page.waitForFunction(()=>Number(document.querySelector('#exactCount')?.textContent)>=16,{timeout:25000});
  await page.getByRole('button',{name:/Explore Peoria/}).click();
  await page.waitForFunction(()=>Number(document.querySelector('#exactCount')?.textContent)>=74,{timeout:25000});
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
      geometry:{type:'LineString',coordinates:[[lon-.01,lat],[lon,lat],[lon+.01,lat]]}}]})});
  });
  await page.locator('#from').fill(String(lat)+','+String(lon-.01));
  await page.locator('#to').fill(String(lat)+','+String(lon+.01));
  await page.locator('#planRoute').click();
  await page.waitForFunction(()=>Number(document.querySelector('#nearbyCount')?.textContent)>=1,{timeout:25000});
  assert.ok(Number(await page.locator('#observationCount').textContent())>=1);
  assert.equal(await page.locator('#hypothetical').isChecked(),false);
  const intro=await page.locator('#timelineIntro').textContent();
  assert.ok(intro.includes('NOT a camera read-range'),intro);
  assert.equal(await page.locator('#play').isDisabled(),false);
  await page.locator('#play').click();
  await page.waitForTimeout(250);
  await page.locator('#reset').click();
  assert.equal(await page.locator('#play').isDisabled(),true);
  assert.equal((await page.locator('#observationCount').textContent()).trim(),'—');
  assert.deepEqual(errors,[]);
  console.log('BROWSER SMOKE PASSED: 3 real municipal GIS datasets, route evidence, replay and reset');
 }catch(e){
  console.error('BROWSER SMOKE FAILED',e.stack||e);
  await page.screenshot({path:'katoptron-smoke-failure.png',fullPage:true}).catch(()=>{});
  process.exitCode=1;
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
