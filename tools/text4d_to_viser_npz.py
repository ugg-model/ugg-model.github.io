"""Convert a published text-to-4D scene into the reconstruction section's npz format.

Lets the same cloud be shown in the reconstruction viewer (viser), so a comparison
between the two sections can be made inside ONE viewer with ONE camera rule,
rather than across two viewers whose default cameras are unrelated.

Output keys match tools/build_viser_scene.py: points, colors, counts, c2w, K.
"""
import argparse
import gzip
import json
from pathlib import Path

import numpy as np


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--scene", type=Path, required=True, help="a published sample_XXX directory")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--filter", action="store_true",
                    help="apply a legacy scene's far-depth cutoff if present; confidence-masked scenes need no extra filter")
    a = ap.parse_args()

    info = json.loads((a.scene / "scene.json").read_text())
    F, gh, gw = info["frame_count"], info["grid_height"], info["grid_width"]
    n = F * gh * gw
    raw = gzip.decompress((a.scene / "pointmaps.bin.gz").read_bytes())
    assert len(raw) == n * 7, "payload size mismatch"
    depth = np.frombuffer(raw, "<f4", count=n).reshape(F, gh, gw)
    colors = np.frombuffer(raw, np.uint8, count=n * 3, offset=n * 4).reshape(F, gh, gw, 3)
    K = np.asarray(info["intrinsics"])
    c2w = np.asarray(info["c2w"])
    stride = info["stride"]
    cutoff = info.get("display_filter", {}).get("max_depth", np.inf) if a.filter else np.inf

    yy, xx = np.mgrid[0:info["height"]:stride, 0:info["width"]:stride]
    px = np.stack([xx + 0.5, yy + 0.5, np.ones_like(xx)], -1).reshape(-1, 3)

    pts, cols, counts = [], [], []
    for f in range(F):
        v = depth[f].reshape(-1)
        keep = np.isfinite(v) & (v > 0) & (v <= cutoff)
        cam = (px[keep] @ np.linalg.inv(K[f]).T) * v[keep, None]
        world = cam @ c2w[f, :3, :3].T + c2w[f, :3, 3]
        pts.append(world.astype(np.float32))
        cols.append(colors[f].reshape(-1, 3)[keep])
        counts.append(len(world))
    np.savez(a.out, points=np.concatenate(pts), colors=np.concatenate(cols),
             counts=np.asarray(counts), c2w=c2w.astype(np.float32), K=K.astype(np.float32))
    print(f"{a.scene.name}: {F} frames, {sum(counts):,} points, "
          f"median {int(np.median(counts)):,}/frame -> {a.out}")


if __name__ == "__main__":
    main()
