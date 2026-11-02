"""Check local HTML/CSS resources before publishing or removing scene assets."""
from html.parser import HTMLParser
from pathlib import Path
import re
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
references = []


class Resources(HTMLParser):
    def handle_starttag(self, tag, attrs):
        for key, value in attrs:
            if value and key in {'src', 'href', 'poster'}:
                references.append((ROOT/'index.html', value))


Resources().feed((ROOT/'index.html').read_text())
for path in [ROOT/'styles.css', ROOT/'assets/method/method.css']:
    for value in re.findall(r'url\(\s*[\'\"]?([^\)\'\"]+)[\'\"]?\s*\)',path.read_text()):
        references.append((path,value))
checked = 0
for source, value in references:
    url = urlsplit(value)
    if url.scheme or url.netloc or not url.path:
        continue
    target = (source.parent/unquote(url.path)).resolve()
    assert target.is_relative_to(ROOT), f'Unexpected asset outside repo: {value}'
    assert target.is_file(), f'Missing resource in {source.relative_to(ROOT)}: {value}'
    checked += 1
print(f'PASS: {checked} local HTML/CSS resource references exist')
