"""Capture every frame of the comparison reel under ONE fixed camera."""
import sys, json, math
import numpy as np
from playwright.sync_api import sync_playwright

OUT = sys.argv[1]
NAMES = json.load(open(sys.argv[2]))
N = len(NAMES)
DIR = np.array([0.45, -0.55, -1.4])
EYE = np.array([1.705, -1.95, -0.67])   # the websites own camera for ScanNet++
URL = ("http://127.0.0.1:8731/viser/reel2_standalone.html"
       f"?initialCameraPosition={','.join(f'{v:.4f}' for v in EYE)}"
       "&initialCameraLookAt=-0.7,0,1.8&initialCameraUp=0,-1,0")
ARGS = ["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"]

with sync_playwright() as p:
    b = p.chromium.launch(args=ARGS)
    pg = b.new_page(viewport={"width": 620, "height": 560})
    pg.goto(URL, timeout=240000)
    pg.wait_for_timeout(75000)
    # pause playback, then drive the time slider frame by frame
    info = pg.evaluate("""()=>{
      const inputs=[...document.querySelectorAll('input')].map(i=>({type:i.type,
        min:i.min,max:i.max,step:i.step,value:i.value}));
      const btns=[...document.querySelectorAll('button')].length;
      return {inputs, btns};
    }""")
    print("inputs:", info["inputs"][:4], "buttons:", info["btns"], flush=True)
    pg.evaluate("""()=>{const b=document.querySelectorAll('button')[0]; if(b) b.click();}""")
    pg.wait_for_timeout(1500)
    done = 0
    for i, name in enumerate(NAMES):
        t = i / 10.0   # recording is 10 fps, so frame i sits at i/10 seconds
        ok = pg.evaluate("""(t)=>{
          const txt=[...document.querySelectorAll('input')].filter(x=>x.type==='text');
          const r=txt[0];
          if(!r) return false;
          const setter=Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype,'value').set;
          setter.call(r, t.toFixed(1));
          r.dispatchEvent(new Event('input',{bubbles:true}));
          r.dispatchEvent(new Event('change',{bubbles:true}));
          r.dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',bubbles:true}));
          r.blur();
          return true;}""", t)
        if not ok:
            print("no range input; aborting", flush=True)
            break
        pg.wait_for_timeout(2200)
        c = pg.query_selector("canvas")
        pg.screenshot(path=f"{OUT}/ref_{i:02d}_{name}.png", clip=c.bounding_box())
        done += 1
        if i % 8 == 0:
            print("captured", i, name, flush=True)
    print("captured frames:", done, flush=True)
    b.close()
