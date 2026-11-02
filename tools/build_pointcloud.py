#!/usr/bin/env python
"""Per-frame point clouds for the viewer: PREDICTED depth, GT camera pose.

pred_depth_norm.npy is normalized DISPARITY in [-1,1], so it carries no metric
scale. To place it in the GT trajectory we fit one global affine (s,t) of the
decoded depth to GT depth over the whole scene -- the same family of alignment
the depth metrics use. One fit for the scene, never per frame, so relative
motion between frames is the model's, not the fit's.
"""
import numpy as np, json, os, argparse, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from decode import decode_depth, fit_affine_trimmed as _fit, edge_mask

def decode(norm):
    return decode_depth(norm)

fit_affine_trimmed = _fit

def turbo(x):
    """Compact turbo-like colormap; x in [0,1] -> uint8 RGB."""
    import matplotlib
    return (matplotlib.colormaps["turbo"](np.clip(x, 0, 1))[:, :3] * 255).astype(np.uint8)

ap = argparse.ArgumentParser()
ap.add_argument("--scene", default="/n/lab_storage/ydu_lab/Lab/akiruga/curated_oracle/depth/scannetpp__dense/scene_44")
ap.add_argument("--stride", type=int, default=2, help="pixel stride per frame")
ap.add_argument("--rgb", default="/n/lab_storage/ydu_lab/Lab/akiruga/world_model_4d/final-website/assets/pointcloud/scene_44_rgb.npz",
                help="GT RGB npz; falls back to depth colouring when absent")
ap.add_argument("--out", default="/n/lab_storage/ydu_lab/Lab/akiruga/world_model_4d/final-website/assets/pointcloud/scannetpp_scene_44.npz")
a = ap.parse_args()

D = a.scene
pred = np.load(f"{D}/pred_depth_norm.npy")
gt   = np.load(f"{D}/gt_depth.npy")
K    = np.load(f"{D}/pred_intrinsics.npy")
c2w  = np.load(f"{D}/gt_c2w.npy")
F, H, W = pred.shape
print(f"scene {os.path.basename(D)}  frames={F} {H}x{W}")

rel = decode(pred)
valid = np.isfinite(gt) & (gt > 1e-3) & np.isfinite(rel)
s, t = fit_affine_trimmed(rel[valid], gt[valid])
met = s * rel + t
print(f"affine fit: depth = {s:.5f} * rel + {t:.5f}")
err = np.abs(met[valid] - gt[valid]) / gt[valid]
print(f"abs_rel after fit: {err.mean():.5f}   (manifest says 0.03117)")

RGB = None
if a.rgb and os.path.exists(a.rgb):
    rz = np.load(a.rgb); RGB = rz["rgb"]
    assert RGB.shape[:3] == pred.shape[:3], f"rgb {RGB.shape} vs depth {pred.shape}"
    print(f"colouring from GT RGB {RGB.shape} (scene {rz['scene']})")
else:
    print("no RGB found - colouring by depth")

st = a.stride
ys, xs = np.mgrid[0:H:st, 0:W:st]
P, C, counts = [], [], []
dlo, dhi = np.percentile(met[valid], [2, 98])
for i in range(F):
    d = met[i][ys, xs]
    k = K[i]
    m = np.isfinite(d) & (d > 1e-3) & edge_mask(met[i])[ys, xs]
    z = d[m]
    x = (xs[m] - k[0, 2]) / k[0, 0] * z
    y = (ys[m] - k[1, 2]) / k[1, 1] * z
    cam = np.stack([x, y, z], 1)                       # OpenCV: y down, z forward
    world = (c2w[i, :3, :3] @ cam.T).T + c2w[i, :3, 3]
    P.append(world.astype(np.float32))
    if RGB is not None:
        C.append(RGB[i][ys, xs][m].astype(np.uint8))
    else:
        C.append(turbo((z - dlo) / max(dhi - dlo, 1e-6)))
    counts.append(len(world))

os.makedirs(os.path.dirname(a.out), exist_ok=True)
np.savez_compressed(
    a.out,
    points=np.concatenate(P), colors=np.concatenate(C),
    counts=np.array(counts, np.int32), c2w=c2w.astype(np.float32),
    K=K.astype(np.float32), scene=os.path.basename(D),
)
tot = sum(counts)
print(f"points/frame ~{tot//F}  total {tot}  -> {a.out}")
print(f"file size: {os.path.getsize(a.out)/1e6:.1f} MB")
