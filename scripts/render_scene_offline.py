"""Offline render replicating text4d-viewer.js framing exactly.

observer target = frame_centers[f]; distance = radius/sin(halfAngle)*0.75 with
fov 48 and aspect 1; eye direction (0.45,-0.55,-1.4) normalised; points filtered
at a legacy display_filter.max_depth, if present; new scenes are confidence-masked
in their payload. Cross-checked against a real browser capture of
sample_026 before being trusted for the rest.
"""
import sys, json, gzip, math
import numpy as np
from PIL import Image

import os
ROOT = os.environ.get("T4D_ROOT","/n/lab_storage/ydu_lab/Lab/akiruga/world_model_4d/ugg-website/assets/text4d_indoor")


def render(name, frame=None, size=460):
    d = f"{ROOT}/{name}"
    info = json.loads(open(d + "/scene.json").read())
    F, gh, gw = info["frame_count"], info["grid_height"], info["grid_width"]
    n = F * gh * gw
    raw = gzip.decompress(open(d + "/pointmaps.bin.gz", "rb").read())
    depth = np.frombuffer(raw, "<f4", count=n).reshape(F, gh, gw)
    cols = np.frombuffer(raw, np.uint8, count=n * 3, offset=n * 4).reshape(F, gh, gw, 3)
    f = F // 2 if frame is None else frame
    K = np.asarray(info["intrinsics"])[f]
    c2w = np.asarray(info["c2w"])[f]
    st = info["stride"]
    yy, xx = np.mgrid[0:info["height"]:st, 0:info["width"]:st]
    px = np.stack([xx + 0.5, yy + 0.5, np.ones_like(xx)], -1).reshape(-1, 3)
    v = depth[f].reshape(-1)
    cut = float(os.environ.get("T4D_MULT","0")) or info.get("display_filter", {}).get("max_depth", np.inf)
    if os.environ.get("T4D_MULT"): cut = float(os.environ["T4D_MULT"])*info.get("display_filter", {}).get("median_depth", float(np.median(depth[depth > 0])))
    keep = np.isfinite(v) & (v > 0) & (v <= cut)
    P = ((px[keep] @ np.linalg.inv(K).T) * v[keep, None]) @ c2w[:3, :3].T + c2w[:3, 3]
    C = cols[f].reshape(-1, 3)[keep]
    target = np.asarray(info["frame_centers"][f])
    radius = info["radius"]
    fov = math.radians(48)
    half = min(fov / 2, math.atan(math.tan(fov / 2)))
    dist = radius / math.sin(half) * 0.75
    direction = np.array([0.45, -0.55, -1.4])
    eye = target + direction / np.linalg.norm(direction) * dist
    fwd = target - eye
    fwd = fwd / np.linalg.norm(fwd)
    up = np.array([0.0, 1.0, 0.0])
    right = np.cross(fwd, up)
    right = right / np.linalg.norm(right)
    up = np.cross(right, fwd)
    R = np.stack([right, up, -fwd])
    V = (P - eye) @ R.T
    z = -V[:, 2]
    g = z > 1e-3
    V, z, C = V[g], z[g], C[g]
    fpx = (size / 2) / math.tan(fov / 2)
    u = (V[:, 0] / z * fpx + size / 2).astype(int)
    w = (-V[:, 1] / z * fpx + size / 2).astype(int)
    m = (u >= 0) & (u < size) & (w >= 0) & (w < size)
    u, w, z, C = u[m], w[m], z[m], C[m]
    # The viewer uses PointsMaterial({size:2, sizeAttenuation:false}): each point
    # covers 2 device pixels regardless of depth. Splat the same way, or an
    # offline render draws 1px dots and understates density.
    img = np.full((size, size, 3), 255, np.uint8)
    zb = np.full((size, size), 1e18)
    order = np.argsort(-z)
    for i in order:
        y0, x0 = w[i], u[i]
        for dy in (0, 1):
            for dx in (0, 1):
                yy, xx = y0 + dy, x0 + dx
                if 0 <= yy < size and 0 <= xx < size and z[i] < zb[yy, xx]:
                    zb[yy, xx] = z[i]
                    img[yy, xx] = C[i]
    return Image.fromarray(img), int(keep.sum()), int(m.sum())


def main():
    out = sys.argv[1]
    names = sys.argv[2:]
    cells = []
    for nm in names:
        im, kept, drawn = render(nm, size=int(os.environ.get("T4D_CELL",460)))
        cells.append((nm, im))
        print(f"{nm}: {kept} points after filter, {drawn} on screen", flush=True)
    cn = int(os.environ.get("T4D_COLS", 4)) if len(cells) > 1 else 1
    W = H = int(os.environ.get("T4D_CELL", 460))
    rows = (len(cells) + cn - 1) // cn
    sheet = Image.new("RGB", (cn * W, rows * H), (245, 245, 245))
    for i, (nm, im) in enumerate(cells):
        sheet.paste(im, (i % cn * W, i // cn * H))
    sheet.save(out)
    print("wrote", out, sheet.size)


if __name__ == "__main__":
    main()
