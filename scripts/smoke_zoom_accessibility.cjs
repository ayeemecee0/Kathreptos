/* Additional browser accessibility regression: zoom, keyboard and form labels.
 * Does not certify WCAG or screen reader conformance.
 */
const {chromium}=require('playwright');
const assert=require('node:assert/strict');
(async()=>{
 const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
 const base=process.env.KATOPTRON_SMOKE_BASE||'http://127.0.0.1:8765/';
 try{
   for(const path of ['index.html','records.html','analytics.html','accountability.html','submit.html','community-review.html']){
     const page=await browser.newPage({viewport:{width:1280,height:860},reducedMotion:'reduce'});
     try{
       const response=await page.goto(new URL(path,base).href,{waitUntil:'domcontentloaded',timeout:45000});
       assert.equal(response?.status(),200,path+' not served');
       const initial=await page.evaluate(()=>document.documentElement.scrollWidth);
       await page.evaluate(()=>document.documentElement.style.zoom='200%');
       await page.waitForTimeout(100);
       const overflow=await page.evaluate(()=>document.documentElement.scrollWidth-window.innerWidth);
       assert.ok(overflow<=4,path+': at 200% CSS zoom, document overflow '+overflow+'px (before zoom '+initial+')');
       const skip=page.locator('a.skip-link[href="#main-content"]');
       assert.equal(await skip.count(),1);
       await page.keyboard.press('Tab');
       assert.equal(await page.evaluate(()=>document.activeElement?.getAttribute('href')),'#main-content');
       if(path==='submit.html'){
         assert.equal(await page.getByRole('textbox',{name:'Email'}).count(),1,'Signup email field lacks label');
         assert.equal(await page.getByRole('button',{name:'Create account'}).count(),1);
         await page.locator('#authForm button[type=submit]').click();
         const invalid=await page.locator('#email').evaluate(e=>e.validity.valueMissing);
         assert.equal(invalid,true,'Empty account form should reject submission natively');
       }
       if(path==='community-review.html'){
         assert.equal(await page.getByRole('textbox',{name:'Email'}).count(),1);
         assert.equal(await page.locator('#workspace').isHidden(),true,'Reviewer workspace visible anonymously');
       }
       console.log('ZOOM / FORMS PASS:',path);
     }finally{await page.close();}
   }
 }catch(e){console.error('ZOOM ACCESSIBILITY FAIL:',e.stack||e);process.exitCode=1;}
 finally{await browser.close();}
})().catch(e=>{console.error('Zoom smoke harness failure',e);process.exitCode=1});
