import sys, json, os
from playwright.sync_api import sync_playwright
SP, OUT = sys.argv[1], sys.argv[2]
NAMES = sys.argv[3:]
CAM = json.load(open(SP + "/nat/cameras.json"))
A = ["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"]
with sync_playwright() as p:
    b = p.chromium.launch(args=A)
    for nm in NAMES:
        dest = f"{OUT}/{nm}.png"
        if os.path.exists(dest):
            print("skip", nm, flush=True); continue
        eye, look = CAM[nm]
        page = f"nat/{nm}_standalone.html"
        url = (f"http://127.0.0.1:8731/viser/{page}"
               f"?initialCameraPosition={','.join(f'{v:.4f}' for v in eye)}"
               f"&initialCameraLookAt={','.join(f'{v:.4f}' for v in look)}"
               "&initialCameraUp=0,-1,0")
        try:
            pg = b.new_page(viewport={"width": 520, "height": 470})
            pg.goto(url, timeout=200000)
            pg.wait_for_timeout(42000)
            pg.evaluate("()=>{const x=document.querySelectorAll('button')[0]; if(x) x.click();}")
            pg.wait_for_timeout(600)
            pg.evaluate("""()=>{const t=[...document.querySelectorAll('input')].filter(i=>i.type==='text')[0];
              const s=Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype,'value').set;
              s.call(t,'2.5'); t.dispatchEvent(new Event('input',{bubbles:true}));
              t.dispatchEvent(new Event('change',{bubbles:true}));
              t.dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',bubbles:true})); t.blur();}""")
            pg.wait_for_timeout(3500)
            c = pg.query_selector("canvas")
            pg.screenshot(path=dest, clip=c.bounding_box())
            print("captured", nm, flush=True)
            pg.close()
        except Exception as e:
            print("FAILED", nm, type(e).__name__, str(e)[:50], flush=True)
    b.close()
print("batch done", flush=True)
