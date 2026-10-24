/* Live acceptance check: fixed, public Sacramento/Folsom fixtures only.
 * Runs against hosted GitHub Pages so Geoapify's allowed-origin restriction
 * can be checked in the same browser context as real visitors.
 * No key/query strings are emitted into logs. Maximum one route planning
 * action (2 free-plan routing requests) + one geocoding request. */
const {chromium}=require('playwright');
const assert=require('node:assert/strict');
(async()=>{
 const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
 const page=await browser.newPage({viewport:{width:1365,height:900}});
 const results={geocoding:[],routing:[]};
 try{
  page.on('response',response=>{
   const url=new URL(response.url());
   if(url.hostname!=='api.geoapify.com')return;
   const kind=url.pathname.startsWith('/v1/routing')?'routing':
     url.pathname.startsWith('/v1/geocode/')?'geocoding':null;
   if(kind)results[kind].push(response.status());
  });
  const base=process.env.KATOPTRON_SMOKE_BASE||
    'https://ayeemecee0.github.io/Katoptron/';
  if(!base.startsWith('https://ayeemecee0.github.io/'))
    throw Error('Live key test requires authorized hosted origin');
  await page.goto(base,{waitUntil:'domcontentloaded',timeout:45000});
  await page.waitForFunction(()=>window.KATOPTRON_CONFIG?.locationProvider==='geoapify',
    {timeout:10000});
  // Exact coordinate inputs skip geocoding so only two real route credits
  // can be consumed during this check.
  await page.locator('#from').fill('38.5816,-121.4944');
  await page.locator('#to').fill('38.6779,-121.1761');
  await page.locator('#planRoute').click();
  await page.waitForFunction(()=>{
    const t=document.querySelector('#routeStatus')?.textContent||'';
    return t.startsWith('Checked ')||t.startsWith('Route unavailable:');
  },{timeout:60000});
  const status=await page.locator('#routeStatus').textContent();
  if(!status.startsWith('Checked '))
    throw Error('Geoapify route request did not complete successfully');
  assert.ok(results.routing.length>=1 && results.routing.length<=2,
    'Expected at most two route HTTP calls');
  assert.ok(results.routing.every(x=>x===200),'Geoapify route HTTP failure');
  assert.ok(await page.locator('#routeComparisonList li').count()>=1);
  assert.equal(await page.locator('#geoapifyAttribution').isVisible(),true);

  // One fixed geocoding query verifies the key's origin restriction for both
  // APIs. Never log the request URL or key, even on failure.
  await page.locator('#mapSearch').fill('Folsom, California');
  await page.locator('#mapSearchForm button').click();
  await page.waitForFunction(()=>{
    const t=document.querySelector('#mapSearchStatus')?.textContent||'';
    return t.startsWith('Map centered on ')||t.startsWith('Map search unavailable:');
  },{timeout:25000});
  assert.ok((await page.locator('#mapSearchStatus').textContent())
    .startsWith('Map centered on '),'Geoapify US geocoding failed');
  assert.deepEqual(results.geocoding,[200]);
  console.log('LIVE GEOAPIFY PASS: authorized origin, US geocode, drive route, evidence check, attribution. Requests: routing='+
    results.routing.length+' geocoding='+results.geocoding.length);
 }catch(err){
  console.error('LIVE GEOAPIFY FAILED (no provider URL or credentials printed): '+
    String(err.message||'acceptance failure').replace(/8c54de2386764931baa0f9aef9033ef3/gi,'[redacted]').slice(0,240));
  console.error('Geoapify status codes: '+JSON.stringify(results));
  process.exitCode=1;
 }finally{await browser.close();}
})().catch(err=>{console.error('Geoapify acceptance harness failure',err.name);process.exitCode=1;});
