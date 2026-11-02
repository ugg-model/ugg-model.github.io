// Chromium QA for release results; run on a verified CPU allocation.
import assert from "node:assert/strict";
import {mkdir, writeFile} from "node:fs/promises";
import path from "node:path";
import {pathToFileURL} from "node:url";
import {applyDepthShowcase} from "../assets/depth-showcase.mjs";
import {CAMERA_SHOWCASE_IDS, applyCameraShowcase} from "../assets/camera-showcase.mjs";
import {NVS_SHOWCASE_IDS, applyNvsShowcase} from "../assets/nvs-showcase.mjs";
const options = Object.fromEntries(process.argv.slice(2).reduce((pairs,arg,index,all) => {
  if (arg.startsWith("--")) pairs.push([arg.slice(2),all[index+1]]); return pairs;
},[]));
const base = (options["base-url"] || "http://127.0.0.1:8080/UGG-website").replace(/\/+$/, ""), output = options["run-dir"];
const {chromium} = process.env.UGG_PLAYWRIGHT_MODULE
  ? await import(pathToFileURL(process.env.UGG_PLAYWRIGHT_MODULE).href) : await import("playwright");
await mkdir(output,{recursive:true});
const evidence = {base_url:base,checks:[],errors:[],failed_requests:[],samples:[],screenshots:[]};
const browser = await chromium.launch({headless:true,args:["--use-angle=swiftshader","--enable-unsafe-swiftshader"]});
let page;
try {
  const context = await browser.newContext({viewport:{width:1440,height:1000},colorScheme:"light"});
  page = await context.newPage();
  page.on("pageerror",error => evidence.errors.push(error.message));
  page.on("requestfailed",request => evidence.failed_requests.push({url:request.url(),reason:request.failure().errorText}));
  assert.equal((await page.goto(base+"/",{waitUntil:"domcontentloaded"})).status(),200);
  await page.waitForSelector("#nvs .case-panel[data-case-ready=true]",{state:"attached"});
  const manifest = applyNvsShowcase(applyCameraShowcase(applyDepthShowcase(await (await page.request.get(base+"/examples.json")).json())));
  assert.deepEqual(await page.locator('.authors a').evaluateAll(links=>links.map(link=>({text:link.textContent,href:link.href}))),[
    {text:"Amani Kiruga",href:"https://amanikiruga.github.io/"},
    {text:"Zhiyi Li",href:"https://sky-lzy.github.io/"},
    {text:"Ruojin Cai",href:"https://ruojincai.github.io/"},
    {text:"Hansen Lillemark",href:"https://hansenlillemark.com/"},
    {text:"Xiaoshan Wu",href:"https://candy-crusher.github.io/xiaoshanwu.github.io/"},
    {text:"Ayush Tewari",href:"https://ayushtewari.com/"},
    {text:"Yilun Du",href:"https://yilundu.github.io/"}
  ]);
  evidence.checks.push("All seven author names link to the user-supplied homepages");
  assert.deepEqual(await page.locator(".result-section").evaluateAll(nodes=>nodes.map(node=>node.dataset.resultTask)),["reconstruction","nvs","depth","camera","generation"]);
  assert.equal(await page.locator("#reconstruction .viser-frame").count(),1);
  assert.equal(manifest.generation.cases.length,24); // Published indoor selection.
  assert.equal(await page.locator("#generation .pending").count(),0);
  assert.equal(await page.locator("#method .placeholder").count(),0);
  await page.locator("#method").scrollIntoViewIfNeeded();
  await page.waitForFunction(()=>[...document.querySelectorAll("#method img")].every(image=>image.complete&&image.naturalWidth>0));
  assert.equal(await page.locator("#method .method-architecture").count(),1);
  assert.equal(await page.locator("#method img").count(),12);
  assert.equal(await page.locator("#method .method-mod").count(),3);
  assert.equal(await page.locator("#method a").count(),0);
  assert.equal(await page.locator("#method .method-card").count(),3);
  evidence.checks.push("Five sections, current-frame reconstruction, 24 indoor Text-to-4D cases, and native HTML method architecture with 12 original source previews");
  const active = task => "#"+task+" .case-panel:not([hidden])";
  async function choose(task,example) {
    const dataset = page.getByLabel("Dataset for "+task,{exact:true});
    const protocol = page.getByLabel("Protocol for "+task,{exact:true});
    if (await protocol.count()) await protocol.selectOption("");
    if (await dataset.count()) await dataset.selectOption(example.dataset);
    if (await protocol.count()) await protocol.selectOption(example.protocol);
    const selector = "#"+task+" .case-thumb[data-case-id='"+example.id+"']";
    for (let pageNumber=0; !(await page.locator(selector).count()); pageNumber++) {
      assert.ok(pageNumber<30,"Case must be accessible through pagination: "+example.id);
      const next = page.locator("#"+task+" [data-action=next-page]");
      assert.equal(await next.isEnabled(),true);
      await next.click();
    }
    await page.locator(selector).click();
    await page.waitForSelector(active(task)+"[data-case-ready=true]");
    assert.equal(await page.locator(active(task)).getAttribute("data-case-id"),example.id);
    assert.equal(await page.locator(active(task)).getAttribute("data-case-error"),null);
    await page.locator(active(task)+" .sync-stage, "+active(task)+" .media-stage").first().scrollIntoViewIfNeeded();
    assert.ok(await page.locator("#"+task+" .case-thumb").count()<=24);
    assert.ok(await page.locator("#"+task+" .case-panel").count()<=3);
  }
  async function ready(prefix) {
    await page.waitForFunction(selector=>document.querySelector(selector)?.readyState>=2,prefix+" video");
    assert.equal(await page.locator(prefix).getAttribute("data-media-error"),null);
  }
  async function pause(task) {
    if (task === "reconstruction") {
      const button = page.frameLocator(active(task)+" iframe").locator("button:has(.tabler-icon-player-pause-filled)");
      if (await button.count()) await button.click();
      return;
    }
    await page.locator(active(task)).evaluate(panel=>panel.uggSync ? panel.uggSync.pause() : panel.querySelector("video").pause());
    await page.waitForFunction(selector=>document.querySelector(selector).paused,active(task)+" video");
  }
  async function seek(task,frame) {
    const prefix=active(task);
    await page.locator(prefix+" .timeline input").evaluate((slider,value)=>{
      slider.value=String(value);slider.dispatchEvent(new Event("input",{bubbles:true}));
    },frame);
    await page.waitForFunction(({prefix,frame})=>{
      const panel=document.querySelector(prefix),video=panel.querySelector("video");
      return !video.seeking && Number(panel.dataset.frame)===frame;
    },{prefix,frame});
    return page.locator(prefix).evaluate(panel=>panel.uggSync.snapshot());
  }
  const matrix=pose=>[
    pose.rotation[0][0],pose.rotation[1][0],pose.rotation[2][0],0,
    pose.rotation[0][1],pose.rotation[1][1],pose.rotation[2][1],0,
    pose.rotation[0][2],pose.rotation[1][2],pose.rotation[2][2],0,...pose.position,1];
  async function screenshot(task,name) {
    await pause(task);
    await page.locator("#"+task).screenshot({path:path.join(output,name)});
    evidence.screenshots.push(name);
  }
  // NVS controls use the reviewed 24, never the 72-case candidate archive.
  const nvsIds = () => page.locator("#nvs .case-thumb").evaluateAll(nodes=>nodes.map(node=>node.dataset.caseId));
  const nvsDataset = page.getByLabel("Dataset for nvs",{exact:true});
  assert.deepEqual(await nvsIds(),NVS_SHOWCASE_IDS);
  assert.equal(await page.locator("#nvs .gallery-count").isVisible(),true);
  assert.equal(await page.locator("#nvs .gallery-count").textContent(),"Cases 1–24 of 24");
  assert.equal(await page.getByLabel("Protocol for nvs",{exact:true}).count(),0,"All approved NVS cases use ncf2");
  assert.equal(await nvsDataset.count(),0);
  assert.equal(await page.locator("#nvs .gallery-selection").count(),0);
  assert.equal(await page.locator("#nvs .gallery-pager").isVisible(),false);
  for (const example of manifest.nvs.cases) {
    await page.locator("#nvs .case-thumb[data-case-id='"+example.id+"']").click();
    await page.waitForSelector(active("nvs")+"[data-case-ready=true]");
    await ready(active("nvs")); await pause("nvs");
    assert.equal(await page.locator(active("nvs")).getAttribute("data-case-id"),example.id);
    assert.equal(await page.locator(active("nvs")+" .pose-inset canvas").count(),1);
    for (const frame of [0,Math.floor(example.frame_count/2),example.frame_count-1]) await seek("nvs",frame);
    assert.ok(await page.locator("#nvs .case-panel").count()<=3);
  }
  evidence.checks.push("NVS: exact 24 IDs/order, no dataset selector or selection caption, ncf2 only, no pagination, all 24 videos/target-camera overlays and first/middle/last frames, bounded cache");
  // Camera controls must operate on the allowlist, never on all 66 source cases.
  const cameraIds = () => page.locator("#camera .case-thumb").evaluateAll(nodes=>nodes.map(node=>node.dataset.caseId));
  const cameraDataset = page.getByLabel("Dataset for camera",{exact:true});
  assert.deepEqual(await cameraIds(),CAMERA_SHOWCASE_IDS);
  assert.equal(await page.locator("#camera .gallery-count").isVisible(),true);
  assert.equal(await page.locator("#camera .gallery-count").textContent(),"Cases 1–24 of 24");
  assert.equal(await page.locator("#camera .gallery-pager").isVisible(),false);
  assert.equal(await cameraDataset.count(),0);
  for (const example of manifest.camera.cases) {
    await page.locator("#camera .case-thumb[data-case-id='"+example.id+"']").click();
    await page.waitForSelector(active("camera")+"[data-case-ready=true]");
    await ready(active("camera"));
    assert.equal(await page.locator(active("camera")).getAttribute("data-case-id"),example.id);
    assert.equal(await page.locator(active("camera")+" .camera-cell canvas").count(),2);
    assert.ok(await page.locator("#camera .case-panel").count()<=3);
  }
  evidence.checks.push("Camera: exact approved 24/order, visible total, no dataset selector or pagination, all 24 media/WebGL viewers load, bounded cache");
  if (options["layout-only"] !== "true") {
    for (const example of manifest.reconstruction.cases) {
      evidence.active_case={task:"reconstruction",id:example.id};
      console.log("Checking reconstruction "+example.id);
      await choose("reconstruction",example);
      const prefix=active("reconstruction"), iframe=page.frameLocator(prefix+" iframe");
      await page.waitForSelector(prefix+"[data-rgb-ready=true]",{timeout:90000});
      assert.equal(await page.locator(prefix).getAttribute("data-rgb-error"),null);
      const timeInput=iframe.locator('input[type=text]:not([role=combobox])').first();
      await pause("reconstruction");
      for (const index of [0,25,49]) {
        evidence.reconstruction_active_frame=index;
        await timeInput.fill(String(example.input_rgb.frame_times[index]+.001));
        await page.waitForFunction(({prefix,index})=>Number(document.querySelector(prefix+" .rgb-inset canvas").dataset.frame)===index,{prefix,index});
        const matches=await page.locator(prefix).evaluate(async (panel,{data,index})=>{
          const actual=panel.querySelector(".rgb-inset canvas"), sprite=new Image();
          sprite.src=data.src; await sprite.decode();
          const expected=document.createElement("canvas"); expected.width=data.width; expected.height=data.height;
          expected.getContext("2d").drawImage(sprite,(index%data.columns)*data.width,Math.floor(index/data.columns)*data.height,data.width,data.height,0,0,data.width,data.height);
          const a=actual.getContext("2d").getImageData(0,0,data.width,data.height).data;
          const b=expected.getContext("2d").getImageData(0,0,data.width,data.height).data;
          const firstDifference=a.findIndex((value,i)=>value!==b[i]);
          let maxDifference=0;
          for (let i=0;i<a.length;i++) maxDifference=Math.max(maxDifference,Math.abs(a[i]-b[i]));
          // The persistent and fresh Canvas raster paths can round a decoded
          // JPEG channel by one level. Keep the frame/crop comparison strict
          // enough to reject a different image, with this rounding allowance.
          return {matches:maxDifference<=1,max_difference:maxDifference,frame:actual.dataset.frame,state:panel.uggPlayback.snapshot(),first_difference:firstDifference,
            actual:[...a.slice(Math.max(0,firstDifference-4),firstDifference+8)],expected:[...b.slice(Math.max(0,firstDifference-4),firstDifference+8)]};
        },{data:example.input_rgb,index});
        assert.equal(matches.matches,true,"Reconstruction inset must show the matching RGB sprite frame: "+JSON.stringify(matches));
        evidence.reconstruction_pixels ??= [];
        evidence.reconstruction_pixels.push({id:example.id,frame:index,max_channel_difference:matches.max_difference});
      }
      const boundaryIndex=example.input_rgb.frame_times.findLastIndex(time=>time<=2.5+1e-9);
      await timeInput.fill("2.5");
      await page.waitForFunction(({prefix,index})=>Number(document.querySelector(prefix+" .rgb-inset canvas").dataset.frame)===index,{prefix,index:boundaryIndex});
      await timeInput.fill(String(example.input_rgb.frame_times[49]+.001));
      await page.waitForFunction(prefix=>Number(document.querySelector(prefix+" .rgb-inset canvas").dataset.frame)===49,prefix);
      await iframe.locator("button:has(.tabler-icon-player-play-filled)").click();
      await page.waitForFunction(prefix=>Number(document.querySelector(prefix+" .rgb-inset canvas").dataset.frame)<10,prefix);
      await iframe.getByRole("combobox").click();
      await iframe.getByRole("option",{name:"4x",exact:true}).click();
      await page.waitForTimeout(250);
      const moving=await page.locator(prefix).evaluate(panel=>panel.uggPlayback.snapshot());
      assert.equal(moving.frame,example.input_rgb.frame_times.findLastIndex(time=>time<=moving.time+1e-9));
      await pause("reconstruction");
      const paused=await page.locator(prefix).evaluate(panel=>panel.uggPlayback.snapshot());
      await page.waitForTimeout(150);
      assert.deepEqual(await page.locator(prefix).evaluate(panel=>panel.uggPlayback.snapshot()),paused);
      await iframe.getByRole("combobox").click(); await iframe.getByRole("option",{name:"1x",exact:true}).click();
      const toggle=page.locator(prefix).getByLabel("Show input",{exact:true});
      await toggle.uncheck(); assert.equal(await page.locator(prefix+" .rgb-inset").isVisible(),false);
      await toggle.check(); assert.equal(await page.locator(prefix+" .rgb-inset").isVisible(),true);
      evidence.reconstruction ??= [];
      evidence.reconstruction.push({id:example.id,frames:example.input_rgb.frame_times.length,scrubbed_frames:[0,25,49],boundary_time:2.5,boundary_frame:boundaryIndex,speed:"4x",loop:true,rgb_pixels_match:true});
    }
    evidence.checks.push("All three reconstruction RGB insets: decoded sprite pixels within one channel level at frames 0/25/49, shared timeline, pause/scrub/loop/speed and Show input toggle");
  }
  const speedChecks = new Set();
  async function checkSpeeds(task, example) {
    const prefix = active(task), control = page.locator(prefix).getByLabel("Playback speed", {exact:true});
    const key = task + "/" + example.fps;
    if (speedChecks.has(key)) return;
    speedChecks.add(key);
    for (const multiplier of [0.5, 1, 2, 4, 8]) {
      await seek(task, 0);
      const before = await page.locator(prefix).evaluate(panel=>panel.uggSync.snapshot());
      await control.selectOption(String(multiplier));
      const changed = await page.locator(prefix).evaluate(panel=>panel.uggSync.snapshot());
      assert.equal(changed.paused, true, "Changing speed must preserve a manual pause");
      assert.equal(changed.frame, before.frame, "Changing speed must preserve the frame");
      assert.ok(Math.abs(changed.time-before.time)<.001);
      const observation = await page.locator(prefix+" video").evaluate(async (video, waitMs)=>{
        await video.play();
        const start=performance.now(), mediaStart=video.currentTime;
        await new Promise(resolve=>setTimeout(resolve,waitMs));
        const rawAdvance=video.currentTime-mediaStart;
        const result={wall_seconds:(performance.now()-start)/1000,media_seconds:(rawAdvance+video.duration)%video.duration,
          media_start:mediaStart,media_end:video.currentTime,wrapped:rawAdvance<0,rate:video.playbackRate,duration:video.duration};
        video.pause(); return result;
      },Math.min(1000, example.frame_count / (10 * multiplier) * 400));
      const measuredFps = observation.media_seconds * example.fps / observation.wall_seconds;
      evidence.playback_speeds ??= [];
      evidence.playback_speeds.push({task,id:example.id,source_fps:example.fps,multiplier,measured_fps:measuredFps,loop_seconds:observation.duration/observation.rate,observation});
      assert.ok(Math.abs(measuredFps-10*multiplier)<=Math.max(1,10*multiplier*.2), "Measured playback speed must follow the selected multiplier: "+JSON.stringify(evidence.playback_speeds.at(-1)));
      assert.ok(Math.abs(observation.duration/observation.rate-example.frame_count/(10*multiplier))<.05);
    }
    await control.selectOption("1"); await seek(task,0);
    await page.locator(prefix+" [data-action=play]").click();
    await page.waitForFunction(selector=>!document.querySelector(selector).paused,prefix+" video");
    await control.selectOption("2");
    const playing = await page.locator(prefix).evaluate(panel=>panel.uggSync.snapshot());
    assert.equal(playing.paused,false,"Changing speed must preserve ongoing playback");
    assert.equal(playing.wanted,true);
    assert.ok(Math.abs(playing.playback_fps-20)<1e-9);
    await pause(task); await control.selectOption("1"); await seek(task,0);
  }
  if (options["layout-only"] !== "true") {
    for (const task of ["nvs","depth","camera"]) {
      const gallery=manifest[task], policy=gallery.selection;
      if (!policy) continue;
      assert.equal(gallery.cases.length,policy.selected);
      assert.equal(gallery.cases.length,24);
      assert.equal(await page.locator("#"+task+" .gallery-selection").count(),0);
      const pageCount=Math.max(1,Math.ceil(gallery.cases.length/24));
      assert.equal(policy.page_datasets.length,pageCount);
      assert.equal(await page.locator("#"+task+" .gallery-pager").isVisible(),pageCount>1);
      for (let index=0;index<pageCount;index++) {
        const ids=await page.locator("#"+task+" .case-thumb").evaluateAll(thumbs=>thumbs.map(thumb=>thumb.dataset.caseId));
        assert.deepEqual(ids,gallery.cases.slice(index*24,(index+1)*24).map(example=>example.id));
        assert.deepEqual([...new Set(ids.map(id=>gallery.cases.find(example=>example.id===id).dataset))].sort(),Object.keys(policy.dataset_quotas).sort());
        if (index<pageCount-1) await page.locator("#"+task+" [data-action=next-page]").click();
      }
      assert.equal(await page.locator("#"+task+" [data-action=next-page]").isEnabled(),false);
      for (let index=0;index<pageCount-1;index++) await page.locator("#"+task+" [data-action=previous-page]").click();
      evidence.checks.push(task+": "+pageCount+" page(s), exact selected thumbnail IDs, and every dataset represented on every page");
    }
  }
  for (const task of options["layout-only"] === "true" ? [] : options.tasks ? options.tasks.split(",") : ["nvs","depth","camera"]) {
    const groups = new Map();
    for (const example of manifest[task].cases) {
      const key=example.dataset+"/"+example.protocol;
      if (!groups.has(key)) groups.set(key,[]);
      groups.get(key).push(example);
    }
    for (const [group,cases] of groups) {
      const samples=[cases[0],cases.at(-1)].filter((example,index,all)=>index===0 || example.id!==all[0].id);
      for (const example of samples) {
        evidence.active_case={task,id:example.id};
        console.log("Checking "+task+" "+example.id);
        await choose(task,example);
        const prefix=active(task);
        await ready(prefix);
        assert.equal(await page.locator(prefix+" .oracle-note, "+prefix+" .display-note").count(),0);
        if (task === "depth") assert.equal(await page.locator(prefix+" .caption").count(),0);
        if (example.kind==="synchronized") {
          const speed = page.locator(prefix).getByLabel("Playback speed",{exact:true});
          assert.deepEqual(await speed.locator("option").evaluateAll(options=>options.map(option=>option.value)),["0.5","1","2","4","8"]);
          assert.equal(await speed.inputValue(),"1");
          assert.ok(Math.abs((await page.locator(prefix).evaluate(panel=>panel.uggSync.snapshot())).playback_fps-10)<1e-9);
          assert.equal(await page.locator(prefix+" .rgb-inset").count(),example.has_input?1:0);
          assert.equal(await page.locator(prefix+" .pose-inset").count(),task==="nvs" && example.poses?1:0);
          if (task!=="camera") assert.equal(await page.locator(prefix+" .seg button").count(),0,"One comparison view needs no view tabs");
          // Every fresh result starts automatically on entering the viewport.
          await page.waitForFunction(selector=>!document.querySelector(selector).paused,prefix+" video");
          await pause(task);
          await checkSpeeds(task,example);
          const poses=example.poses ? await (await page.request.get(base+"/"+example.poses)).json() : null;
          for (const frame of [0,Math.floor(example.frame_count/2),example.frame_count-1]) {
            const state=await seek(task,frame);
            if (poses) {
              assert.equal(await page.locator(prefix).getAttribute("data-viewer-error"),null);
              for (const [index,key] of (task==="nvs" ? ["reference"] : ["prediction","reference"]).entries()) {
                assert.ok(state.camera.views[index].active_matrix.every((value,i)=>Math.abs(value-matrix(poses[key][frame])[i])<1e-9));
                assert.equal(state.camera.views[index].frame_points,example.frame_count);
              }
              if (task==="camera") assert.ok(state.camera.views[0].observer_position.every((value,index)=>Math.abs(value-state.camera.views[1].observer_position[index])<1e-9));
            }
            if (task!=="camera" || example.has_input) {
              const matches=await page.locator(prefix).evaluate(panel=>{
                const video=panel.querySelector("video"),main=panel.querySelector(".depth-canvas,.comparison-canvas"),rgb=panel.querySelector(".rgb-inset canvas");
                return [main,rgb].filter(Boolean).every(canvas=>{
                  const expected=document.createElement("canvas");expected.width=canvas.width;expected.height=canvas.height;
                  expected.getContext("2d").drawImage(video,canvas===rgb && main ? main.width : 0,0,canvas.width,canvas.height,0,0,canvas.width,canvas.height);
                  const a=canvas.getContext("2d").getImageData(0,0,canvas.width,canvas.height).data;
                  const b=expected.getContext("2d").getImageData(0,0,canvas.width,canvas.height).data;
                  return a.every((value,i)=>value===b[i]);
                });
              });
              assert.equal(matches,true,"Comparison/RGB must match the same decoded frame");
            }
          }
          await seek(task,0);
          await page.locator(prefix+" [data-action=play]").click();
          await page.waitForFunction(selector=>document.querySelector(selector).currentTime>.25,prefix+" video");
          await pause(task);
        } else {
          for (const key of Object.keys(example.views)) {
            await page.locator(prefix+" button[data-view='"+key+"']").click(); await ready(prefix);
            if (!example.autoplay) await page.locator(prefix+" video").evaluate(video=>video.play());
            await page.waitForFunction(selector=>!document.querySelector(selector).paused,prefix+" video");
          }
          await pause(task);
        }
        const pausedTime=await page.locator(prefix+" video").evaluate(video=>video.currentTime);
        await page.locator("#abstract").scrollIntoViewIfNeeded();
        await page.locator(prefix+" .sync-stage, "+prefix+" .media-stage").first().scrollIntoViewIfNeeded();
        await page.waitForTimeout(200);
        assert.equal(await page.locator(prefix+" video").evaluate(video=>video.paused),true,"Manual pause must survive leaving/reentering the viewport");
        assert.ok(Math.abs((await page.locator(prefix+" video").evaluate(video=>video.currentTime))-pausedTime)<.1);
        await page.locator(prefix+" video").evaluate(video=>video.play());
        await page.locator("#abstract").scrollIntoViewIfNeeded();
        await page.waitForFunction(selector=>document.querySelector(selector).paused,prefix+" video");
        evidence.samples.push({task,group,id:example.id,has_input:!!example.has_input,views:Object.keys(example.views)});
      }
    }
    evidence.checks.push(task+": first/last case of every dataset/protocol; all sampled views, bounded pagination/cache, playback and offscreen/manual pause");
  }
  if (speedChecks.size) evidence.checks.push("10 FPS default and all five measured speed choices across source FPS variants; speed changes preserve paused frames and expected loop durations");
  if (speedChecks.size) {
    const first=manifest.nvs.cases[0], second=manifest.nvs.cases.find(example=>example.dataset===first.dataset && example.protocol===first.protocol && example.id!==first.id);
    await choose("nvs",first); await ready(active("nvs")); await pause("nvs");
    await page.locator(active("nvs")).getByLabel("Playback speed",{exact:true}).selectOption("2");
    await seek("nvs",17);
    await choose("nvs",second); await ready(active("nvs"));
    await choose("nvs",first); await ready(active("nvs"));
    const restored=await page.locator(active("nvs")).evaluate(panel=>panel.uggSync.snapshot());
    assert.equal(restored.speed,2); assert.equal(restored.frame,17); assert.equal(restored.paused,true);
    await page.locator(active("nvs")).getByLabel("Playback speed",{exact:true}).selectOption("1");
    evidence.checks.push("Changing speed preserves ongoing playback; cached case restores chosen speed, frame and manual pause");
  }
  const cameraCase=manifest.camera.cases.find(example=>example.kind==="synchronized" && example.has_input);
  const depthCase=manifest.depth.cases.find(example=>example.kind==="synchronized" && example.has_input);
  const nvsCase=manifest.nvs.cases.find(example=>example.poses);
  assert.ok(cameraCase && depthCase,"Release should include cases with matching input RGB");
  await choose("camera",cameraCase);await ready(active("camera"));await pause("camera");
  const canvas=page.locator(active("camera")+" .camera-cell canvas").first(), bounds=await canvas.boundingBox();
  const before=await page.locator(active("camera")).evaluate(panel=>panel.uggSync.snapshot());
  await page.mouse.move(bounds.x+bounds.width*.5,bounds.y+bounds.height*.5);await page.mouse.down();
  await page.mouse.move(bounds.x+bounds.width*.65,bounds.y+bounds.height*.55,{steps:6});await page.mouse.up();
  const after=await page.locator(active("camera")).evaluate(panel=>panel.uggSync.snapshot());
  assert.notDeepEqual(after.camera.views[0].observer_position,before.camera.views[0].observer_position);
  assert.ok(after.camera.views[0].observer_position.every((value,index)=>Math.abs(value-after.camera.views[1].observer_position[index])<1e-9));
  await page.locator(active("camera")+" .reset-view").click();
  evidence.checks.push("Linked camera orbit and reset");
  for (const width of options.widths ? options.widths.split(",").map(Number) : [375,768,1440]) {
    await page.setViewportSize({width,height:1000});
    for (const [task,example] of [["depth",depthCase],["camera",cameraCase],...(nvsCase ? [["nvs",nvsCase]] : [])]) {
      await choose(task,example);await ready(active(task));await pause(task);
      const position=await page.locator(active(task)).evaluate(panel=>{
        const stage=panel.querySelector(".sync-stage").getBoundingClientRect(),inset=panel.querySelector(".rgb-inset,.pose-inset"),rgb=inset.getBoundingClientRect();
        const overlap=[...panel.querySelectorAll(".camera-view-label,.comparison-labels span")].filter(label=>!inset.contains(label)).some(label=>{
          const r=label.getBoundingClientRect();return r.left<rgb.right && r.right>rgb.left && r.top<rgb.bottom && r.bottom>rgb.top;
        });
        return {top:rgb.top-stage.top,right:stage.right-rgb.right,width:rgb.width,overlap};
      });
      assert.ok(position.top>=0 && position.top<=9 && position.right>=0 && position.right<=9 && position.width<=(task==="nvs"?211:129));
      assert.equal(position.overlap,false,"Upper-right overlay must not cover comparison labels");
      assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>window.innerWidth+1),false);
      await screenshot(task,task+"-"+width+".png");
    }
    await page.locator("#method").scrollIntoViewIfNeeded();
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>window.innerWidth+1),false);
    evidence.checks.push("Upper-right overlays, label separation, and no overflow at "+width+"px");
    const reconstruction=manifest.reconstruction.cases[0];
    await choose("reconstruction",reconstruction);
    await page.waitForSelector(active("reconstruction")+"[data-rgb-ready=true]",{timeout:90000});
    await pause("reconstruction");
    const insetPosition=await page.locator(active("reconstruction")).evaluate(panel=>{
      const stage=panel.querySelector(".viser-stage").getBoundingClientRect(), inset=panel.querySelector(".rgb-inset").getBoundingClientRect();
      return {top:inset.top-stage.top,right:stage.right-inset.right,width:inset.width};
    });
    assert.ok(insetPosition.top>=0 && insetPosition.top<=9 && insetPosition.right>=0 && insetPosition.right<=9 && insetPosition.width<=129);
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>window.innerWidth+1),false);
    await screenshot("reconstruction","reconstruction-"+width+".png");
  }
  await page.locator("#nvs .case-thumb").first().focus();
  await page.locator("#nvs .case-thumb").first().press("ArrowRight");
  assert.equal(await page.locator("#nvs .case-thumb").nth(1).getAttribute("aria-pressed"),"true");
  await page.locator("#nvs .case-thumb").nth(1).press("Home");
  assert.equal(await page.locator("#nvs .case-thumb").first().getAttribute("aria-pressed"),"true");
  await context.grantPermissions(["clipboard-read","clipboard-write"]);
  await page.locator("#copy-citation").click();
  assert.match(await page.evaluate(()=>navigator.clipboard.readText()),/Advances in Neural Information Processing Systems/);
  const reduced=await browser.newContext({viewport:{width:375,height:900},reducedMotion:"reduce",colorScheme:"dark"});
  const reducedPage=await reduced.newPage();await reducedPage.goto(base+"/",{waitUntil:"domcontentloaded"});
  await reducedPage.waitForSelector("#depth .case-panel[data-sync-ready=true]",{state:"attached"});
  await reducedPage.locator("#depth .sync-stage").scrollIntoViewIfNeeded();
  await reducedPage.waitForTimeout(300);
  assert.equal(await reducedPage.locator("#depth video").evaluate(video=>video.paused),true);
  await reducedPage.locator("#nvs .sync-stage").scrollIntoViewIfNeeded();await reducedPage.waitForTimeout(300);
  assert.equal(await reducedPage.locator("#nvs video").evaluate(video=>video.paused),true);
  await reducedPage.waitForSelector("#camera .case-panel[data-sync-ready=true]",{state:"attached"});
  await reducedPage.locator("#camera .sync-stage").scrollIntoViewIfNeeded();await reducedPage.waitForTimeout(300);
  assert.equal(await reducedPage.locator("#camera video").evaluate(video=>video.paused),true);
  await reduced.close();
  evidence.checks.push("Keyboard thumbnails, citation copy, and reduced-motion initial playback");
  assert.deepEqual(evidence.errors,[]);
  evidence.status="passed";
  console.log(JSON.stringify({status:evidence.status,samples:evidence.samples.length,checks:evidence.checks},null,2));
} catch(error) {
  evidence.status="failed";evidence.failure=String(error.stack||error);console.error(evidence.failure);process.exitCode=1;
  if (page) evidence.viewer_states=await page.locator('.case-panel:not([hidden])').evaluateAll(panels=>panels.map(panel=>{
    const stage=panel.querySelector('.sync-stage'), rect=stage?.getBoundingClientRect();
    return {id:panel.id,state:panel.uggSync?.snapshot(),error:panel.dataset.viewerError,
      stage:rect ? {top:rect.top,bottom:rect.bottom,height:rect.height} : null,viewport:innerHeight};
  })).catch(()=>[]);
} finally {
  await writeFile(path.join(output,"browser-evidence.json"),JSON.stringify(evidence,null,2)+"\n");await browser.close();
}
