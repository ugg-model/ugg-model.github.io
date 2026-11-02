"""One viser recording holding every cloud, so all of them share one camera.

Each cloud (the reconstruction section's three scenes, then every published
text-to-4D scene) contributes one frame. Each is translated to the origin and
scaled so its robust radius is 1, which makes a single fixed camera frame every
one of them identically. That is a same-viewer, camera-matched comparison for
all of them at once, instead of one page and one capture per scene.

Only the observer is affected: within a cloud nothing is changed but a rigid
translation and a uniform scale, so relative density and completeness are intact.
"""
import argparse
import gzip
import json
from pathlib import Path

import numpy as np

PC = Path("/n/lab_storage/ydu_lab/Lab/akiruga/world_model_4d/final-website/assets/pointcloud")
RECON = [("recon-scannetpp", PC / "scannetpp_scene_44.npz"),
         ("recon-bonn", PC / "bonn_release_person_tracking2.npz"),
         ("recon-kitti", PC / "kitti_release_drive0095.npz")]
FRAME = 25


# ScanNet++ frame 25, the pose the website's own reconstruction camera was chosen for
REF_CENTRE = np.array([-0.955, -0.037, 1.751])
REF_RADIUS = 2.2064


def normalise(points, colors):
    """Map a cloud onto the reference scene's centre and radius.

    Every cloud then sits where the reconstruction section's ScanNet++ cloud sits,
    at the same size, so the website's own `initial_camera` for that case frames all
    of them. Only a rigid translation and a uniform scale are applied, so nothing
    about a cloud's density or completeness changes.
    """
    low, high = np.quantile(points, [0.02, 0.98], axis=0)
    centre = (low + high) / 2
    radius = max(float(np.linalg.norm(high - low) / 2), 1e-9)
    moved = (points - centre) * (REF_RADIUS / radius) + REF_CENTRE
    return moved.astype(np.float32), colors


def from_recon(path):
    z = np.load(path)
    cnt = z["counts"]
    off = np.concatenate([[0], np.cumsum(cnt)])
    P = z["points"][off[FRAME]:off[FRAME + 1]].astype(np.float64)
    C = z["colors"][off[FRAME]:off[FRAME + 1]]
    if C.dtype != np.uint8:
        C = (np.clip(C, 0, 1) * 255).astype(np.uint8)
    return normalise(P, C)


def from_text4d(folder):
    info = json.loads((folder / "scene.json").read_text())
    F, gh, gw = info["frame_count"], info["grid_height"], info["grid_width"]
    n = F * gh * gw
    raw = gzip.decompress((folder / "pointmaps.bin.gz").read_bytes())
    depth = np.frombuffer(raw, "<f4", count=n).reshape(F, gh, gw)
    cols = np.frombuffer(raw, np.uint8, count=n * 3, offset=n * 4).reshape(F, gh, gw, 3)
    K = np.asarray(info["intrinsics"])[FRAME]
    c2w = np.asarray(info["c2w"])[FRAME]
    st = info["stride"]
    yy, xx = np.mgrid[0:info["height"]:st, 0:info["width"]:st]
    px = np.stack([xx + 0.5, yy + 0.5, np.ones_like(xx)], -1).reshape(-1, 3)
    v = depth[FRAME].reshape(-1)
    keep = np.isfinite(v) & (v > 0) & (v <= info.get("display_filter", {}).get("max_depth", np.inf))
    P = ((px[keep] @ np.linalg.inv(K).T) * v[keep, None]) @ c2w[:3, :3].T + c2w[:3, 3]
    return normalise(P, cols[FRAME].reshape(-1, 3)[keep])


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--tree", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()

    names, pts, cols, counts = [], [], [], []
    for name, path in RECON:
        P, C = from_recon(path)
        names.append(name); pts.append(P); cols.append(C); counts.append(len(P))
        print(f"{name}: {len(P):,}", flush=True)
    for folder in sorted(a.tree.glob("sample_[0-9][0-9][0-9]")):
        P, C = from_text4d(folder)
        names.append(folder.name); pts.append(P); cols.append(C); counts.append(len(P))
        print(f"{folder.name}: {len(P):,}", flush=True)

    F = len(counts)
    # a short straight dummy path: build_viser_scene wants a camera per frame, and a
    # degenerate spline would collapse
    c2w = np.tile(np.eye(4, dtype=np.float32), (F, 1, 1))
    c2w[:, 0, 3] = np.linspace(0, 1e-3, F)
    K = np.tile(np.array([[200., 0, 192.], [0, 200., 144.], [0, 0, 1.]], np.float32), (F, 1, 1))
    np.savez(a.out, points=np.concatenate(pts), colors=np.concatenate(cols),
             counts=np.asarray(counts), c2w=c2w, K=K)
    (a.out.with_suffix(".names.json")).write_text(json.dumps(names, indent=1) + "\n")
    print(f"\n{F} frames -> {a.out}  ({sum(counts):,} points)")


if __name__ == "__main__":
    main()
