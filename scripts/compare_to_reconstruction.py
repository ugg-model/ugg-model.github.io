"""Render the reconstruction cloud and text4d clouds through ONE renderer.

Same camera rule for both (observer target = that frame's robust centroid,
distance = radius/sin(halfAngle)*0.75, fov 48, 2px splat), so apparent size is
comparable — unlike screenshots of two different viewers with different defaults.
"""
import sys, os, json, gzip, math
import numpy as np
from PIL import Image

PC = "/n/lab_storage/ydu_lab/Lab/akiruga/world_model_4d/final-website/assets/pointcloud"
# the three scenes the reconstruction section actually publishes
RECON = {"scannetpp": PC + "/scannetpp_scene_44.npz",
         "bonn": PC + "/bonn_release_person_tracking2.npz",
         "kitti": PC + "/kitti_release_drive0095.npz"}
NPZ = RECON["scannetpp"]
T4D = "/n/lab_storage/ydu_lab/Lab/akiruga/world_model_4d/ugg-website/assets/text4d_indoor"


def draw(P, C, size):
    """Identical projection/splat for every cloud."""
    low, high = np.quantile(P, [0.02, 0.98], axis=0)
    target = (low + high) / 2
    radius = max(float(np.linalg.norm(high - low) / 2), 1e-6)
    fov = math.radians(48)
    half = min(fov / 2, math.atan(math.tan(fov / 2)))
    dist = radius / math.sin(half) * 0.75
    d = np.array([0.45, -0.55, -1.4])
    eye = target + d / np.linalg.norm(d) * dist
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
    f = (size / 2) / math.tan(fov / 2)
    u = (V[:, 0] / z * f + size / 2).astype(int)
    w = (-V[:, 1] / z * f + size / 2).astype(int)
    m = (u >= 0) & (u < size) & (w >= 0) & (w < size)
    u, w, z, C = u[m], w[m], z[m], C[m]
    img = np.full((size, size, 3), 255, np.uint8)
    zb = np.full((size, size), 1e18)
    for i in np.argsort(-z):
        for dy in (0, 1):
            for dx in (0, 1):
                yy, xx = w[i] + dy, u[i] + dx
                if 0 <= yy < size and 0 <= xx < size and z[i] < zb[yy, xx]:
                    zb[yy, xx] = z[i]
                    img[yy, xx] = C[i]
    return Image.fromarray(img), int(m.sum())


def recon_frame(frame, size, which="scannetpp"):
    z = np.load(RECON[which])
    cnt = z["counts"]
    off = np.concatenate([[0], np.cumsum(cnt)])
    s, e = off[frame], off[frame + 1]
    P = z["points"][s:e].astype(np.float64)
    C = z["colors"][s:e]
    if C.dtype != np.uint8:
        C = (np.clip(C, 0, 1) * 255).astype(np.uint8)
    return draw(P, C, size)


def t4d_frame(name, size):
    d = f"{T4D}/{name}"
    info = json.loads(open(d + "/scene.json").read())
    F, gh, gw = info["frame_count"], info["grid_height"], info["grid_width"]
    n = F * gh * gw
    raw = gzip.decompress(open(d + "/pointmaps.bin.gz", "rb").read())
    depth = np.frombuffer(raw, "<f4", count=n).reshape(F, gh, gw)
    cols = np.frombuffer(raw, np.uint8, count=n * 3, offset=n * 4).reshape(F, gh, gw, 3)
    f = F // 2
    K = np.asarray(info["intrinsics"])[f]
    c2w = np.asarray(info["c2w"])[f]
    st = info["stride"]
    yy, xx = np.mgrid[0:info["height"]:st, 0:info["width"]:st]
    px = np.stack([xx + 0.5, yy + 0.5, np.ones_like(xx)], -1).reshape(-1, 3)
    v = depth[f].reshape(-1)
    keep = np.isfinite(v) & (v > 0) & (v <= info.get("display_filter", {}).get("max_depth", np.inf))
    P = ((px[keep] @ np.linalg.inv(K).T) * v[keep, None]) @ c2w[:3, :3].T + c2w[:3, 3]
    return draw(P, cols[f].reshape(-1, 3)[keep], size)


if __name__ == "__main__":
    out, size = sys.argv[1], int(os.environ.get("CELL", 460))
    cells = []
    im, n = recon_frame(25, size)
    cells.append(("reconstruction ScanNet++", im, n))
    for nm in sys.argv[2:]:
        im, n = t4d_frame(nm, size)
        cells.append((f"text4d {nm}", im, n))
    for label, _, n in cells:
        print(f"{label}: {n:,} points on screen", flush=True)
    cols = int(os.environ.get("COLS", len(cells)))
    rows = (len(cells) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * size, rows * size), (255, 255, 255))
    for i, (_, im, _) in enumerate(cells):
        sheet.paste(im, (i % cols * size, i // cols * size))
    sheet.save(out)
    print("wrote", out, sheet.size)
