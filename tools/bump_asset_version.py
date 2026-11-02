#!/usr/bin/env python
"""Stamp one cache-busting version onto every local script and stylesheet.

Why this exists: the site is previewed over `python -m http.server`, which sends no
cache headers, and GitHub Pages caches aggressively too. A reader who reloads gets the
new index.html and the new CSS but keeps the OLD JavaScript, so a fix that touches a
viewer appears not to have shipped -- which is exactly what happened on 2026-10-27,
when the removed per-viewer sample row kept rendering from a cached app.js.

app.js imports the viewers dynamically, so the query has to reach those too; a fresh
app.js importing a cached ./sync-viewers.js has the same symptom.

Run after changing any JS or CSS, then commit the result.
"""
import datetime, re, io, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.dirname(HERE)
TAGGED = ("styles.css", "assets/benchmarks/benchmarks.css", "assets/method/method.css",
          "app.js", "results-flow.js", "assets/benchmarks/data.js",
          "assets/benchmarks/benchmarks.js", "assets/method/uggfig-scale.js")

version = sys.argv[1] if len(sys.argv) > 1 else datetime.datetime.now().strftime("%Y%m%d-%H%M")

p = os.path.join(SITE, "index.html")
html = io.open(p, encoding="utf-8").read()
for asset in TAGGED:
    html = re.sub(rf'(href|src)="{re.escape(asset)}(\?v=[^"]*)?"',
                  lambda m: f'{m.group(1)}="{asset}?v={version}"', html)
io.open(p, "w", encoding="utf-8").write(html)

p = os.path.join(SITE, "app.js")
js = io.open(p, encoding="utf-8").read()
if "const ASSET_VERSION" not in js:
    js = re.sub(r'^("use strict";\n)',
                rf'\1// Cache-busting token, stamped by tools/bump_asset_version.py.\n'
                rf'const ASSET_VERSION = "{version}";\n', js, count=1)
else:
    js = re.sub(r'const ASSET_VERSION = "[^"]*";', f'const ASSET_VERSION = "{version}";', js)
js = re.sub(r'import\("\./([a-z0-9-]+\.js)(\?v=\$\{ASSET_VERSION\})?"\)',
            r'import(`./\1?v=${ASSET_VERSION}`)', js)
js = re.sub(r'import\(`\./([a-z0-9-]+\.js)(\?v=\$\{ASSET_VERSION\})?`\)',
            r'import(`./\1?v=${ASSET_VERSION}`)', js)
io.open(p, "w", encoding="utf-8").write(js)
print(f"stamped v={version} on {len(TAGGED)} tags and the dynamic viewer imports")
