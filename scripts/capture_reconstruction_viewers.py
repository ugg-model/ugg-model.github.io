"""Capture the reconstruction section's viewers from within the site itself.

The standalone viser HTML pages do not render headless; the site embeds them
through viser-viewer.js, which is a different init path and is what the
reconstruction section actually shows.
"""
import sys
from playwright.sync_api import sync_playwright

OUT = sys.argv[1]
WANT = sys.argv[2:]
ARGS = ["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"]

with sync_playwright() as p:
    b = p.chromium.launch(args=ARGS)
    pg = b.new_page(viewport={"width": 1180, "height": 1000})
    pg.goto("http://127.0.0.1:8731/index.html", timeout=180000)
    pg.wait_for_timeout(4000)
    sec = pg.evaluate_handle("()=>document.querySelector('[data-result-task=\"reconstruction\"]')")
    pg.evaluate("s=>s.scrollIntoView()", sec)
    pg.wait_for_timeout(1500)
    labels = pg.evaluate("""s=>[...s.querySelectorAll('button')].map(b=>b.textContent.trim()).slice(0,10)""", sec)
    print("buttons:", labels, flush=True)
    for name in WANT:
        ok = pg.evaluate("""([s,n])=>{const b=[...s.querySelectorAll('button')].find(x=>
            (x.textContent||'').toLowerCase().includes(n) ||
            ((x.querySelector('img')||{}).getAttribute?.('src')||'').toLowerCase().includes(n));
            if(b){b.click();return true;} return false;}""", [sec, name])
        print("selected", name, ok, flush=True)
        if not ok:
            continue
        pg.wait_for_timeout(120000)
        el = pg.query_selector("[data-result-task='reconstruction'] .case-viewer")
        if el is None:
            el = sec
        el.screenshot(path=f"{OUT}/site_recon_{name}.png")
        print("captured", name, flush=True)
    b.close()
print("done", flush=True)
