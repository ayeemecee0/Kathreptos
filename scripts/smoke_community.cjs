/* Milestone 5: no-credential browser smoke for the public and private portals.
 * This does not generate reports or consume provider credits. */
const {chromium}=require('playwright');
const assert=require('node:assert/strict');
(async()=>{
 const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
 const base=process.env.KATOPTRON_SMOKE_BASE||'http://127.0.0.1:8765/';
 try{
   const page=await browser.newPage({viewport:{width:1100,height:860}});
   const failures=[];
   page.on('pageerror',e=>failures.push(e.message));
   const submitResponse=await page.goto(new URL('submit.html',base).href,
     {waitUntil:'domcontentloaded',timeout:45000});
   assert.equal(submitResponse.status(),200,'Submission page missing from deployment');
   await page.locator('#authForm').waitFor();
   assert.equal(await page.locator('#reportPanel').isHidden(),true,
     'Report form must not be shown without a valid session');
   assert.equal(await page.locator('#photo').count(),1);
   assert.equal(await page.locator('#myReports').count(),1);
   assert.equal(await page.locator('#consent').count(),1);
   await page.goto(new URL('community-review.html',base).href,
     {waitUntil:'domcontentloaded',timeout:45000});
   await page.locator('#login').waitFor();
   assert.equal(await page.locator('#workspace').isHidden(),true,
     'Private report queue visible before reviewer authentication');
   assert.equal(failures.length,0,'Client JavaScript errors: '+failures.join('; '));
   console.log('COMMUNITY PORTALS PASS: authenticated gateways, privacy controls and deployed HTML');
 }catch(error){
   console.error('COMMUNITY PORTALS FAIL:',error.message);
   process.exitCode=1;
 }finally{await browser.close();}
})().catch(e=>{console.error('Community smoke harness failed',e.message);process.exitCode=1});
