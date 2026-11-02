import sys, json, os
from playwright.sync_api import sync_playwright
SP, OUT = sys.argv[1], sys.argv[2]
KEYS = sys.argv[3:]
CAM = json.load(open(SP + "/rec/cameras.json"))
A = ["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"]
with sync_playwright() as p:
    b = p.chromium.launch(args=A)
    for key in KEYS:
        dest = f"{OUT}/{key}.png"
        if os.path.exists(dest):
            print("skip", key, flush=True); continue
        eye, look, fr = CAM[key]
        scene = key.split("_f")[0]
        url = (f"http://127.0.0.1:8731/viser/rec/{scene}_standalone.html"
               f"?initialCameraPosition={','.join(f'{v:.4f}' for v in eye)}"
               f"&initialCameraLookAt={','.join(f'{v:.4f}' for v in look)}"
               "&initialCameraUp=0,-1,0")
        try:
            pg = b.new_page(viewport={"width": 520, "height": 470})
            pg.goto(url, timeout=200000)
            pg.wait_for_timeout(42000)
            pg.evaluate("()=>{const x=document.querySelectorAll('button')[0]; if(x) x.click();}")
            pg.wait_for_timeout(600)
            pg.evaluate("""(t)=>{const i=[...document.querySelectorAll('input')].filter(x=>x.type==='text')[0];
              const s=Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype,'value').set;
              s.call(i,t); i.dispatchEvent(new Event('input',{bubbles:true}));
              i.dispatchEvent(new Event('change',{bubbles:true}));
              i.dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',bubbles:true})); i.blur();}""",
              f"{fr/10:.1f}")
            pg.wait_for_timeout(3500)
            c = pg.query_selector("canvas")
            pg.screenshot(path=dest, clip=c.bounding_box())
            print("captured", key, flush=True)
            pg.close()
        except Exception as e:
            print("FAILED", key, type(e).__name__, str(e)[:50], flush=True)
    b.close()
print("batch done", flush=True)
