/* Read-only Milestone 7 browser acceptance: no tracking or write actions. */
const {chromium}=require('playwright');
const assert=require('node:assert/strict');
(async()=>{
 const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
 const page=await browser.newPage({viewport:{width:1120,height:900}});
 try{
  const base=process.env.KATOPTRON_SMOKE_BASE||'https://ayeemecee0.github.io/Katoptron/';
  const response=await page.goto(new URL('analytics.html',base).href,{waitUntil:'domcontentloaded',timeout:45000});
  assert.equal(response.status(),200,'Evidence analytics missing from public site');
  await page.waitForFunction(()=>/Loaded current published evidence|analytics unavailable/.test(
    document.querySelector('#status')?.textContent||''),{timeout:45000});
  assert.match(await page.locator('#status').textContent(),/Loaded current published evidence/);
  assert.ok(Number((await page.locator('#exact').textContent()).replaceAll(',',''))>=1,
    'Published exact camera inventory unavailable');
  assert.ok((await page.locator('#stateRows tr').count())>=1,'State source breakdown unavailable');
  assert.ok((await page.locator('#timeChart [role="listitem"]').count())>=1,
    'Source-dated chronological evidence unavailable');
  await page.locator('#sort').selectOption('name');
  await page.locator('#category').selectOption('government_program');
  assert.equal(await page.locator('#download').isEnabled(),true);
  console.log('ANALYTICS PASS: public evidence, state table, dated trend chart, filters, export');
 }catch(error){console.error('ANALYTICS FAIL:',error.message);process.exitCode=1;}
 finally{await browser.close();}
})().catch(error=>{console.error('Analytics smoke failed:',error.message);process.exitCode=1});
