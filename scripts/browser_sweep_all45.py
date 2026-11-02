"""Capture every indoor text4d scene from the real viewer, one browser session.

Writes each cell as it goes so partial progress survives, then tiles a contact
sheet from whatever landed.
"""
import sys, os, glob
from playwright.sync_api import sync_playwright
from PIL import Image

OUT = sys.argv[1]
CELLS = os.path.join(OUT, "sweep")
os.makedirs(CELLS, exist_ok=True)
# canvas rect inside .case-viewer, measured earlier and stable
REL = dict(x=0.027083333333333334, y=0.03420208830058374,
           w=0.9458333333333333, h=0.602482940064129)
ARGS = ["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--no-zygote", "--single-process", "--disable-dev-shm-usage"]
NAMES = [f"sample_{i:03d}" for i in range(45)]

with sync_playwright() as p:
    b = p.chromium.launch(args=ARGS)
    pg = b.new_page(viewport={"width": 1180, "height": 1000})
    pg.goto("http://127.0.0.1:8731/index.html", timeout=180000)
    pg.wait_for_timeout(4000)
    sec = pg.evaluate_handle("()=>document.querySelector('[data-result-task=\"generation\"]')")
    pg.evaluate("s=>s.scrollIntoView()", sec)
    pg.wait_for_timeout(800)
    current_page = 0
    for idx, name in enumerate(NAMES):
        dest = os.path.join(CELLS, f"{name}.png")
        if os.path.exists(dest):
            continue
        want_page = (22 + idx) // 24
        while current_page < want_page:
            pg.evaluate("""s=>{const b=[...s.querySelectorAll('button')]
                .find(x=>/Next cases/i.test(x.textContent)); if(b&&!b.disabled)b.click();}""", sec)
            current_page += 1
            pg.wait_for_timeout(500)
        while current_page > want_page:
            pg.evaluate("""s=>{const b=[...s.querySelectorAll('button')]
                .find(x=>/Previous cases/i.test(x.textContent)); if(b&&!b.disabled)b.click();}""", sec)
            current_page -= 1
            pg.wait_for_timeout(500)
        frag = f"text4d_indoor/{name}/"
        ok = pg.evaluate("""([s,f])=>{const b=[...s.querySelectorAll('button')].find(x=>{
            const i=x.querySelector('img'); return i&&(i.getAttribute('src')||'').includes(f);});
            if(b){b.click();return true;} return false;}""", [sec, frag])
        if not ok:
            print("MISS", name, flush=True)
            continue
        pg.wait_for_timeout(9000)
        el = pg.query_selector("[data-result-task='generation'] .case-viewer")
        el.screenshot(path=dest)
        print("captured", name, flush=True)
    b.close()

paths = sorted(glob.glob(os.path.join(CELLS, "sample_*.png")))
W = H = 300
cols = 7
rows = (len(paths) + cols - 1) // cols
sheet = Image.new("RGB", (cols * W, rows * H), (250, 250, 250))
for i, path in enumerate(paths):
    im = Image.open(path).convert("RGB")
    iw, ih = im.size
    im = im.crop((int(REL["x"] * iw), int(REL["y"] * ih),
                  int((REL["x"] + REL["w"]) * iw), int((REL["y"] + REL["h"]) * ih)))
    im.thumbnail((W - 4, H - 4))
    sheet.paste(im, (i % cols * W + 2, i // cols * H + 2))
sheet.save(os.path.join(OUT, "sweep45.png"))
print("SHEET", len(paths), "cells ->", os.path.join(OUT, "sweep45.png"), flush=True)
