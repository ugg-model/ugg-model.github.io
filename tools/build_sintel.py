#!/usr/bin/env python
"""Per-frame point clouds for a Sintel scene: predicted depth, GT pose, GT RGB.

Sintel specifics:
  - GT depth stores ~1e11 as a sky sentinel; the spec caps it at 70 m.
  - Native frames are 1024x436 (2.35:1) but the eval grid is 4:3, so there is a
    real horizontal crop, recorded per scene in GT_RGB.txt.
  - Intrinsics come from the .cam files (read, not assumed), adjusted for that
    crop and the resize.
"""
import numpy as np, cv2, os, glob, re, sys, argparse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from decode import decode_depth, fit_affine_trimmed, edge_mask

ap = argparse.ArgumentParser()
ap.add_argument("--scene", default="/n/lab_storage/ydu_lab/Lab/akiruga/curated_oracle/depth/sintel__dense/sleeping_2")
ap.add_argument("--stride", type=int, default=1)
ap.add_argument("--out", default="/n/lab_storage/ydu_lab/Lab/akiruga/world_model_4d/final-website/assets/pointcloud/sintel_sleeping_2.npz")
a = ap.parse_args()
D, name = a.scene, os.path.basename(a.scene)
MAXD = 70.0
SIN = "/n/lab_storage/ydu_lab/Lab/akiruga/world_model_4d/pi3_eval/evaluation/Pi3_depthpose/data/sintel/training"

gt   = np.load(f"{D}/gt_depth.npy"); F, Hg, Wg = gt.shape
pred = np.load(f"{D}/pred_depth_norm.npy")
c2w  = np.load(f"{D}/gt_c2w.npy")
box  = tuple(int(v) for v in re.search(r"crop_box.*?\(([\d,\s]+)\)", open(f"{D}/GT_RGB.txt").read()).group(1).split(","))
top, bot, left, right = box
print(f"{name}  gt{gt.shape}  crop {box}")

# Sintel's virtual camera ZOOMS in some shots (cave_2 fx 841.9->379.5 over the 50-frame
# window, sleeping_1 640->690), so read ONE K PER FRAME. Using frame 0 for all frames
# was wrong by up to 2.2x on cave_2.
camf = sorted(glob.glob(f"{SIN}/camdata_left/{name}/*.cam"))
Ks = []
for cf in camf:
    with open(cf, "rb") as fh:
        assert abs(np.fromfile(fh, np.float32, 1)[0] - 202021.25) < 1e-2
        Kn = np.fromfile(fh, "float64", 9).reshape(3, 3)
    Ki = Kn.copy(); Ki[0, 2] -= left; Ki[1, 2] -= top
    Ki[0, :] *= Wg / (right - left); Ki[1, :] *= Hg / (bot - top)
    Ks.append(Ki)
Kall = np.stack(Ks)
K = Kall[0]
if float((Kall.max(0) - Kall.min(0)).max()) > 1e-6:
    print(f"K VARIES across frames (zoom): fx {Kall[:,0,0].min():.1f}..{Kall[:,0,0].max():.1f}")
print("K[0] (from .cam, crop+resize applied):\n", np.round(K, 2))

rel = decode_depth(pred)
rel = np.stack([cv2.resize(r, (Wg, Hg), cv2.INTER_NEAREST) for r in rel])
v = np.isfinite(gt) & (gt > 1e-3) & (gt < MAXD) & np.isfinite(rel)
s, t = fit_affine_trimmed(rel[v], gt[v]); met = s * rel + t
print(f"affine fit: depth = {s:.5f}*rel + {t:.5f}")
print(f"abs_rel after fit: {(np.abs(met[v]-gt[v])/gt[v]).mean():.5f}")

rgbf = sorted(glob.glob(f"{D}/gt_rgb/*")); assert len(rgbf) == F
RGB = np.stack([cv2.cvtColor(cv2.resize(cv2.imread(f)[top:bot, left:right], (Wg, Hg),
                interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2RGB) for f in rgbf])

st = a.stride; ys, xs = np.mgrid[0:Hg:st, 0:Wg:st]
P, C, cnt = [], [], []
for i in range(F):
    d = met[i][ys, xs]
    m = np.isfinite(d) & (d > 1e-3) & (d < MAXD) & edge_mask(met[i])[ys, xs]
    z = d[m]
    Ki = Kall[i] if i < len(Kall) else Kall[-1]          # per-frame intrinsics
    cam = np.stack([(xs[m]-Ki[0,2])/Ki[0,0]*z, (ys[m]-Ki[1,2])/Ki[1,1]*z, z], 1)
    P.append(((c2w[i,:3,:3] @ cam.T).T + c2w[i,:3,3]).astype(np.float32))
    C.append(RGB[i][ys, xs][m].astype(np.uint8)); cnt.append(int(m.sum()))

os.makedirs(os.path.dirname(a.out), exist_ok=True)
np.savez_compressed(a.out, points=np.concatenate(P), colors=np.concatenate(C),
                    counts=np.array(cnt, np.int32), c2w=c2w.astype(np.float32),
                    K=(Kall[:F] if len(Kall) >= F else
                       np.concatenate([Kall, np.repeat(Kall[-1][None], F-len(Kall), 0)])
                      ).astype(np.float32), scene=name)
print(f"points/frame ~{sum(cnt)//F}  total {sum(cnt)}  -> {a.out} ({os.path.getsize(a.out)/1e6:.1f} MB)")
