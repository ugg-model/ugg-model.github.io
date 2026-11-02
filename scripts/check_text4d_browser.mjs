// Run in the wan environment on a task CPU allocation with Playwright installed.
import assert from 'node:assert/strict';
import {mkdir,writeFile} from 'node:fs/promises';
import {pathToFileURL} from 'node:url';
import {TEXT4D_SHOWCASE_IDS} from '../assets/text4d-showcase.mjs';
const base=(process.argv[2]||'http://127.0.0.1:18284/UGG-website').replace(/\/$/,'');
const output=process.argv[3]||'outputs/indoor-selection/browser';
await mkdir(output,{recursive:true});
const {chromium}=await import(pathToFileURL(process.env.UGG_PLAYWRIGHT_MODULE).href);
const browser=await chromium.launch({headless:true,args:['--use-angle=swiftshader','--enable-unsafe-swiftshader']});
const evidence={base,checks:[],scenes:[],errors:[],passed:false};
try {
 const page=await browser.newPage({viewport:{width:1440,height:1080},reducedMotion:'reduce',colorScheme:'light'});
 page.on('pageerror',error=>evidence.errors.push(error.message));
 await page.goto(base+'/',{waitUntil:'domcontentloaded',timeout:90000});
 await page.waitForSelector('#generation .case-thumb',{timeout:90000});
 assert.deepEqual(await page.locator('#generation .case-thumb').evaluateAll(nodes=>nodes.map(n=>n.dataset.caseId)),TEXT4D_SHOWCASE_IDS);
 const labels=Array.from({length:24},(_,i)=>'Scene '+String(i+1).padStart(2,'0'));
 assert.deepEqual(await page.locator('#generation .thumb-label').allTextContents(),labels);
 for (const task of ['nvs','depth','camera']) assert.equal(await page.locator('#'+task+' .thumb-label').first().textContent(),'Scene 01');
 assert.equal(await page.locator('#generation [data-action=next-page]').isVisible(),false);
 const manifest=await (await page.request.get(base+'/examples.json')).json();
 assert.deepEqual(manifest.generation.cases.map(c=>c.id),TEXT4D_SHOWCASE_IDS);
 for (const retired of ['assets/text4d/sample_007/scene.json','assets/text4d_indoor/sample_001/scene.json']) {
  assert.equal((await page.request.get(base+'/'+retired)).status(),404,'Retired asset: '+retired);
 }
 await page.locator('#flow-task-generation').click();
 for (const kind of ['rgb','depth']) {
  const image=await page.locator('.flow-'+kind+'-frame').first().evaluate(n=>getComputedStyle(n).backgroundImage);
  assert.ok(image.includes('assets/text4d_indoor/sample_000/'+kind+'.jpg'),'Overview preview must use a retained scene');
  const url=image.match(/url\(["']?(.*?)["']?\)$/)[1];
  assert.equal((await page.request.get(url)).status(),200);
 }
 await page.locator('#results-flow').screenshot({path:output+'/overview.png'});
 const active='#generation .case-panel:not([hidden])';
 async function seek(frame) {
  await page.locator(active+' input[type=range]').evaluate((n,v)=>{n.value=String(v);n.dispatchEvent(new Event('input',{bubbles:true}));},frame);
  await page.waitForFunction(({active,frame})=>document.querySelector(active)?.uggPlayback?.snapshot().frame===frame,{active,frame});
  return page.locator(active).evaluate(n=>n.uggPlayback.snapshot());
 }
 for (let i=0;i<TEXT4D_SHOWCASE_IDS.length;i++) {
  const id=TEXT4D_SHOWCASE_IDS[i];
  await page.locator('#generation .case-thumb[data-case-id="'+id+'"]').click();
  await page.locator(active).scrollIntoViewIfNeeded();
  await page.waitForFunction(selector=>document.querySelector(selector)?.dataset.text4dReady==='true'||document.querySelector(selector)?.dataset.caseError==='true',active,{timeout:90000});
  assert.equal(await page.locator(active).getAttribute('data-case-error'),null,id);
  assert.equal(await page.locator(active+' input[type=checkbox]').count(),0);
  const info=await (await page.request.get(base+'/'+manifest.generation.cases[i].scene)).json();
  const frames=[];
  for (const frame of [0,25,49]) {
   const snap=await seek(frame);
   assert.equal(snap.points,info.confidence_filter.frame_counts[frame].retained,id+' '+frame);
   assert.equal(snap.point_clouds,1);
   assert.equal(snap.inset_frame,frame);
   assert.equal(snap.world_camera.frame,frame);
   assert.equal(snap.confidence_filter.retained_fraction,.95);
   assert.equal(snap.mode,'rgb');
   frames.push({frame,points:snap.points});
  }
  await seek(25);
  await page.locator(active+' .text4d-stage').screenshot({path:output+'/scene-'+String(i+1).padStart(2,'0')+'.png'});
  if ([0,11,23].includes(i)) {
   const selector=page.locator(active+' select[aria-label="Floating preview"]');
   for (const mode of ['depth','camera','rgb']) {
    await selector.selectOption(mode);
    const snap=await page.locator(active).evaluate(n=>n.uggPlayback.snapshot());
    assert.equal(snap.mode,mode);assert.equal(snap.inset_frame,25);
    if(mode==='camera') assert.equal(snap.camera.frame,25);
   }
   await page.locator(active+' button.reset-view').click();
   assert.equal((await page.locator(active).evaluate(n=>n.uggPlayback.snapshot())).frame,25);
  }
  assert.ok(await page.locator('#generation .case-panel').count()<=3);
  evidence.scenes.push({id,label:labels[i],frames});
  console.log('PASS',labels[i],id,frames.map(f=>f.points).join(','));
 }
 // Check active playback, rate control and synchronized inset on the last scene.
 await seek(0);
 await page.locator(active+' button[data-action=play]').click();
 await page.waitForFunction(selector=>document.querySelector(selector)?.uggPlayback.snapshot().frame>=4,active);
 await page.locator(active+' button[data-action=play]').click();
 await page.locator(active+' select[aria-label="Playback speed"]').selectOption('2');
 assert.equal((await page.locator(active).evaluate(n=>n.uggPlayback.snapshot())).speed,2);
 await seek(10);
 const paused=await page.locator(active).evaluate(n=>n.uggPlayback.snapshot());
 await page.waitForTimeout(250);
 assert.equal((await page.locator(active).evaluate(n=>n.uggPlayback.snapshot())).frame,paused.frame);
 // Mobile: first scene, all labels and controls, no horizontal document overflow.
 await page.setViewportSize({width:390,height:900});
 await page.locator('#generation .case-thumb').first().click();
 await page.locator(active).scrollIntoViewIfNeeded();
 await page.waitForFunction(selector=>document.querySelector(selector)?.dataset.text4dReady==='true',active,{timeout:90000});
 await seek(25);
 assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
 assert.equal(await page.locator(active+' select[aria-label="Floating preview"]').inputValue(),'rgb');
 await page.locator(active).screenshot({path:output+'/mobile.png'});
 assert.deepEqual(evidence.errors,[]);
 evidence.checks=['Exact 24 indoor scenes and Scene 01–24 labels','Overview RGB/depth previews load from a retained scene','All 24 render at frames 0,25,49 with exact retained counts','Original-color single current-frame cloud and synchronized RGB/camera frame','RGB/depth/camera selection, reset, playback, pause, speed, bounded cache','390px mobile layout and default RGB, no horizontal overflow','No JavaScript errors'];
 evidence.passed=true;
} finally {
 await writeFile(output+'/evidence.json',JSON.stringify(evidence,null,2));
 await browser.close();
}
console.log('PASS: all Text-to-4D browser checks');
