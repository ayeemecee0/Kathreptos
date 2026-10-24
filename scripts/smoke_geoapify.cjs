/* No real Geoapify requests or credentials. Verify opt-in free provider
 * works end to end with mocked US geocoder and real-shape road geometries. */
const {chromium}=require('playwright');
const assert=require('node:assert/strict');
(async()=>{
 const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
 const page=await browser.newPage({viewport:{width:1280,height:900}});
 const errors=[];
 page.on('pageerror',e=>errors.push(e.message));
 const fake='a'.repeat(32);
 const calls={geocoding:0,routing:0};
 try{
  await page.route('**/config.js',async route=>{
   const response=await route.fetch();
   let body=await response.text();
   if(!/locationProvider:\s*'(demo|geoapify)'/.test(body))
     throw Error('Location provider config switch missing');
   // Supply a fake client key, even if the deployed site has a real one.
   // All Geoapify URLs below are intercepted and no credits are consumed.
   body=body.replace(/locationProvider:\s*'[^']+'/,
     "locationProvider: 'geoapify'")
     .replace(/geoapifyPublicKey:\s*'[^']*'/,
       "geoapifyPublicKey: '"+fake+"'");
   await route.fulfill({status:200,contentType:'application/javascript',body});
  });
  await page.route('https://api.geoapify.com/v1/geocode/search**',async route=>{
   calls.geocoding++;
   const url=new URL(route.request().url());
   assert.equal(url.searchParams.get('apiKey'),fake);
   const query=String(url.searchParams.get('text')).toLowerCase();
   const isFrom=query.includes('sacramento');
   const p=isFrom?{lat:38.5816,lon:-121.4944,name:'Sacramento'}
                 :{lat:38.6779,lon:-121.1761,name:'Folsom'};
   await route.fulfill({status:200,contentType:'application/json',
    headers:{'access-control-allow-origin':'*'},
    body:JSON.stringify({results:[{...p,country_code:'us',state:'California'}]})});
  });
  await page.route('https://api.geoapify.com/v1/routing**',async route=>{
   calls.routing++;
   const u=new URL(route.request().url());
   assert.equal(u.searchParams.get('apiKey'),fake);
   const type=u.searchParams.get('type');
   const intermediate=type==='balanced'?[-121.34,38.61]:[-121.30,38.65];
   await route.fulfill({status:200,contentType:'application/json',
    headers:{'access-control-allow-origin':'*'},
    body:JSON.stringify({type:'FeatureCollection',features:[{
      type:'Feature',geometry:{type:'MultiLineString',coordinates:[
      [[-121.4944,38.5816],intermediate,[-121.1761,38.6779]]]},
      properties:{distance:type==='balanced'?31500:33100,
       time:type==='balanced'?1850:1990}}]})});
  });
  await page.goto(process.env.KATOPTRON_SMOKE_BASE||
    'https://ayeemecee0.github.io/Katoptron/',
    {waitUntil:'domcontentloaded',timeout:45000});
  await page.waitForFunction(()=>window.KATOPTRON_CONFIG?.locationProvider==='geoapify');
  assert.equal(await page.locator('#geoapifyAttribution').isVisible(),true);
  await page.locator('#from').fill('Sacramento');
  await page.locator('#to').fill('Folsom');
  await page.locator('#planRoute').click();
  await page.waitForFunction(()=>document.querySelector('#routeChoice')?.options.length===2,
    {timeout:30000});
  assert.equal(calls.geocoding,2);
  assert.equal(calls.routing,2);
  assert.ok((await page.locator('#routeChoiceStatus').textContent())
    .includes('2 real driving alternatives'));
  assert.deepEqual(errors,[]);
  console.log('FREE GEOAPIFY ADAPTER BROWSER SMOKE PASSED');
 }catch(e){
  console.error('FREE GEOAPIFY ADAPTER BROWSER SMOKE FAILED',e.stack||e);
  process.exitCode=1;
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
