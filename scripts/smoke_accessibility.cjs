/* Milestone 8 keyboard/screen-size accessibility regression (not a WCAG audit). */
const {chromium}=require('playwright');
const assert=require('node:assert/strict');
(async()=>{
 const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
 const base=process.env.KATOPTRON_SMOKE_BASE||'http://127.0.0.1:8765/';
 try{
  for(const width of [390,1280]){
   const page=await browser.newPage({viewport:{width,height:850},reducedMotion:'reduce'});
   for(const path of ['index.html','accountability.html','analytics.html','records.html']){
    const response=await page.goto(new URL(path,base).href,{waitUntil:'domcontentloaded',timeout:45000});
    assert.equal(response.status(),200,path+' not deployed');
    assert.equal(await page.locator('main#main-content').count(),1);
    assert.equal(await page.locator('a.skip-link[href="#main-content"]').count(),1);
    await page.keyboard.press('Tab');
    assert.equal(await page.evaluate(()=>document.activeElement?.getAttribute('href')),
      '#main-content',path+' has no keyboard-accessible skip link');
    if(path==='index.html'){
      assert.equal(await page.locator('#map').getAttribute('tabindex'),'0',
        'Interactive map not keyboard-focusable');
      assert.equal(await page.locator('#map').getAttribute('aria-describedby'),'mapKeyboardHelp');
      assert.ok((await page.locator('#mapKeyboardHelp').textContent()).includes('arrow keys'),
        'Map keyboard controls not explained');
      await page.locator('#map').focus();
      assert.equal(await page.evaluate(()=>document.activeElement?.id),'map',
        'Keyboard navigation cannot focus map');
    }
    const overflow=await page.evaluate(()=>document.documentElement.scrollWidth-innerWidth);
    assert.ok(overflow<=4,path+' unexpectedly overflows '+width+'px viewport: '+overflow);
   }
   await page.close();
  }
  console.log('ACCESSIBILITY SHELL PASS: navigation bypass and mobile/desktop width');
 }catch(e){console.error('ACCESSIBILITY SHELL FAIL:',e.message);process.exitCode=1;}
 finally{await browser.close();}
})().catch(e=>{console.error('Accessibility smoke harness failed:',e.message);process.exitCode=1});
