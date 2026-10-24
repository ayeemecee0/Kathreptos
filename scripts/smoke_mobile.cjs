/* Narrow-screen mobile layout + map evidence smoke, no real plate data. */
const {chromium}=require('playwright');
const assert=require('node:assert/strict');
(async()=>{
  const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
  const page=await browser.newPage({viewport:{width:390,height:844},
                                   deviceScaleFactor:2,touchscreen:true,
                                   reducedMotion:'reduce'});
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  try {
    await page.goto(process.env.KATOPTRON_SMOKE_BASE ||
      'https://ayeemecee0.github.io/Katoptron/',
      {waitUntil:'domcontentloaded',timeout:45000});
    await page.waitForFunction(()=>document.querySelector('#coverageSpinner')?.textContent==='Live data',
      {timeout:30000});
    const base=await page.evaluate(()=>({
      width:window.innerWidth,
      documentWidth:document.documentElement.scrollWidth,
      map:(()=>{const r=document.querySelector('#map').getBoundingClientRect();
                 return {width:r.width,height:r.height};})()
    }));
    assert.ok(base.map.width>=250 && base.map.height>=200,
      'Mobile source map should retain a usable viewport: '+JSON.stringify(base));
    assert.ok(base.documentWidth<=base.width+3,
      'Mobile page must not force horizontal scrolling: '+JSON.stringify(base));
    assert.equal(await page.locator('#hypothetical').isChecked(),false,
      'Fictional observations must be opt-in on mobile too');
    await page.locator('#viewPeoria').click();
    await page.waitForFunction(()=>Number(document.querySelector('#exactCount')?.textContent)>=74,
      {timeout:25000});
    const jurisdiction=await page.locator('#jurisdictionFilter').locator('option').allTextContents();
    assert.ok(jurisdiction.includes('Peoria, AZ'),
      'Mobile controls must expose the actual verified camera jurisdiction');
    await page.locator('#jurisdictionFilter').selectOption('Peoria, AZ');
    assert.ok(Number(await page.locator('#exactCount').textContent())>=74);
    await page.locator('#mapSearch').fill('33.67,-112.29');
    await page.locator('#mapSearchForm button').click();
    await page.waitForFunction(()=>document.querySelector('#mapSearchStatus')?.textContent?.includes('Map centered'),
      {timeout:9000});
    await page.locator('#from').fill('33.65,-112.3');
    await page.locator('#to').fill('33.68,-112.28');
    assert.equal(await page.locator('#from').inputValue(),'33.65,-112.3');
    assert.equal(await page.locator('#to').inputValue(),'33.68,-112.28');
    assert.equal(await page.locator('#play').isDisabled(),true,
      'Replay must remain disabled until mobile route evidence is checked');
    assert.deepEqual(errors,[],'No uncaught mobile JavaScript errors');
    console.log('MOBILE BROWSER PASS: 390px viewport, responsive map, camera filters, search and route form');
  } catch(e) {
    console.error('MOBILE BROWSER FAIL',e.stack||e);
    await page.screenshot({path:'katoptron-mobile-smoke-failure.png',fullPage:true}).catch(()=>{});
    process.exitCode=1;
  } finally {await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
