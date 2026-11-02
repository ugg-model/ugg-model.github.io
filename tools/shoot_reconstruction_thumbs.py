#!/usr/bin/env python
"""Render every reconstruction scene in the real client and screenshot it.

Two jobs in one pass: the frames are the gallery thumbnails, and they are how the
clouds get looked at before they ship. Metrics choose the candidates; this is where a
candidate that looks wrong gets caught. Pass --contact-sheet to tile them for review.

Needs a local preview server (scripts/serve.py) already running.
"""
import argparse, json, math, os, sys
from playwright.sync_api import sync_playwright

ARGS = ["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader",
        "--no-zygote", "--single-process", "--disable-dev-shm-usage"]


def shoot(pg, base, case, out_png, seconds, settle):
    view = case['initial_camera']
    src = (f"{base}/viser/viser-client/index.html?playbackPath=/{case['src']}"
           f"&initialCameraPosition={','.join(str(v) for v in case['initial_camera']['position'])}"
           f"&initialCameraLookAt={','.join(str(v) for v in case['initial_camera']['look_at'])}"
           f"&initialCameraUp={','.join(str(v) for v in view.get('up', [0,-1,0]))}")
    if view.get('fov'):
        aspect = pg.viewport_size['width'] / pg.viewport_size['height']
        fov = 2 * math.atan(max(math.tan(view['fov']/2),
            math.tan(view.get('horizontal_fov', view['fov'])/2)/aspect))
        src += f"&initialCameraFov={fov}"
    pg.goto(src, timeout=240000)
    pg.wait_for_timeout(settle)
    # The software-WebGL warning toast sits over the top-left of every render.
    for sel in ("button[aria-label='Close']", ".mantine-Notification-closeButton",
                "[class*=closeButton]"):
        try:
            pg.click(sel, timeout=1200); break
        except Exception:
            pass
    try:                                   # pause, then land on an exact timestamp
        pg.click("button:has(svg)", timeout=4000)
    except Exception:
        pass
    inp = pg.query_selector("input[type=number]")
    if inp:
        inp.fill(str(seconds)); inp.press("Enter"); pg.wait_for_timeout(2500)
    pg.screenshot(path=out_png)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--cases", default=os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                                    "reconstruction_cases.json"))
    ap.add_argument("--base", default="http://127.0.0.1:8137")
    ap.add_argument("--out", required=True)
    ap.add_argument("--only", default=None, help="one case id")
    ap.add_argument("--seconds", type=float, default=2.0)
    ap.add_argument("--settle", type=int, default=22000, help="ms to wait for the recording")
    ap.add_argument("--width", type=int, default=900)
    ap.add_argument("--height", type=int, default=700)
    ap.add_argument("--contact-sheet", default=None)
    a = ap.parse_args()

    cases = json.load(open(a.cases))["cases"]
    if a.only:
        cases = [c for c in cases if c["id"] == a.only]
    os.makedirs(a.out, exist_ok=True)
    done = []
    with sync_playwright() as p:
        b = p.chromium.launch(args=ARGS, executable_path="/usr/bin/chromium-browser")
        # One page, reused: this Chromium runs --single-process, where a page per
        # scene tears the whole browser down after the first close.
        pg = b.new_page(viewport={"width": a.width, "height": a.height})
        errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        for c in cases:
            png = f"{a.out}/{c['id']}.png"
            del errs[:]
            try:
                shoot(pg, a.base, c, png, a.seconds, a.settle)
                done.append(png)
                print(f"  {c['id']:34s} -> {png}{'  ERRORS: ' + '; '.join(errs[:1]) if errs else ''}",
                      flush=True)
            except Exception as e:
                print(f"  {c['id']:34s} FAILED {type(e).__name__}: {e}", flush=True)
        b.close()

    if a.contact_sheet and done:
        from PIL import Image, ImageDraw
        cols, cell = 4, (450, 350)
        rows = (len(done) + cols - 1) // cols
        sheet = Image.new("RGB", (cols * cell[0], rows * (cell[1] + 18)), "white")
        d = ImageDraw.Draw(sheet)
        for i, png in enumerate(done):
            im = Image.open(png).convert("RGB").resize(cell)
            x, y = (i % cols) * cell[0], (i // cols) * (cell[1] + 18)
            sheet.paste(im, (x, y + 18))
            d.text((x + 4, y + 4), os.path.basename(png)[:-4], fill="black")
        sheet.save(a.contact_sheet)
        print(f"contact sheet -> {a.contact_sheet}")


if __name__ == "__main__":
    main()
