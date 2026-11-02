"""Preview the Pages site with video ranges and an optional project URL prefix."""
import argparse
import functools
import os
import re
import shutil
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

PUBLIC_FILES = {
    "index.html", "styles.css", "app.js", "sync-viewers.js",
    "camera-viewer.js", "examples.json", ".nojekyll",
    "viser-viewer.js", "text4d-viewer.js", "text4d-geometry.js", "results-flow.js",
}
PUBLIC_DIRECTORIES = {"assets", "vendor", "viser"}


class AssetHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, base_path="/", **kwargs):
        self.base_path = base_path
        super().__init__(*args, **kwargs)

    def translate_path(self, path):
        # send_head rejects requests outside this prefix before this is called.
        return super().translate_path("/" + path[len(self.base_path):])

    def list_directory(self, path):
        self.send_error(404, "Directory listings are disabled")
        return None

    def end_headers(self):
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Cache-Control", "no-cache")
        super().end_headers()

    def send_head(self):
        self.byte_count = None
        requested_url = urlsplit(self.path)
        if self.base_path != "/" and requested_url.path == self.base_path.rstrip("/"):
            self.send_response(301)
            location = self.base_path
            if requested_url.query:
                location += "?" + requested_url.query
            self.send_header("Location", location)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return None
        if not requested_url.path.startswith(self.base_path):
            self.send_error(404)
            return None
        root = Path(self.directory).resolve()
        asset = Path(self.translate_path(self.path)).resolve()
        if not asset.is_relative_to(root):
            self.send_error(403)
            return None
        relative = asset.relative_to(root)
        # The publishing root also contains local tools, logs and Git metadata.
        # Preview only the site's explicit public files/directories.
        if relative.parts and relative.parts[0] not in PUBLIC_DIRECTORIES and str(relative) not in PUBLIC_FILES:
            self.send_error(404)
            return None
        requested = self.headers.get("Range")
        if not requested or not asset.is_file():
            return super().send_head()
        match = re.fullmatch(r"bytes=(\d*)-(\d*)", requested)
        size = asset.stat().st_size
        if not match or not any(match.groups()) or size == 0:
            return self.reject_range(size)
        first, last = match.groups()
        start = int(first) if first else max(0, size - int(last))
        end = min(int(last), size - 1) if first and last else size - 1
        if start >= size or start > end or (not first and int(last) == 0):
            return self.reject_range(size)
        stream = asset.open("rb")
        stream.seek(start)
        self.byte_count = end - start + 1
        self.send_response(206)
        self.send_header("Content-Type", self.guess_type(str(asset)))
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.send_header("Content-Length", str(self.byte_count))
        self.end_headers()
        return stream

    def reject_range(self, size):
        self.send_response(416)
        self.send_header("Content-Range", f"bytes */{size}")
        self.send_header("Content-Length", "0")
        self.end_headers()
        return None

    def copyfile(self, source, outputfile):
        if self.byte_count is None:
            return shutil.copyfileobj(source, outputfile)
        remaining = self.byte_count
        while remaining:
            block = source.read(min(65536, remaining))
            if not block:
                break
            outputfile.write(block)
            remaining -= len(block)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--base-path", default="/", help="Preview a project path such as /UGG-website/")
    args = parser.parse_args()
    root = args.directory.resolve()
    base_path = "/" + args.base_path.strip("/") + "/" if args.base_path.strip("/") else "/"
    if not re.fullmatch(r"/(?:[A-Za-z0-9_-]+/)*", base_path):
        parser.error("The base path must contain only simple path segments")
    if not (root / "index.html").is_file():
        parser.error("The website directory must contain index.html")
    server = ThreadingHTTPServer(("127.0.0.1", args.port),
        functools.partial(AssetHandler, directory=str(root), base_path=base_path))
    print(f"Serving {root} at http://127.0.0.1:{args.port}{base_path}, Slurm job {os.environ.get('SLURM_JOB_ID', 'none')}", flush=True)
    server.serve_forever()
