#!/usr/bin/env python
"""Per-frame point clouds for KITTI: predicted depth, predicted pose, GT RGB.

Two KITTI-specific caveats, both flagged in the output:
  - no calib file ships with this copy, so K uses the standard 2011_09_26
    rectified values; a focal sweep against road planarity checks them;
  - KITTI has no GT pose here (no pose spec), so frames are placed with our
    PREDICTED trajectory. Do not present this as GT-pose placement.
"""
import numpy as np, cv2, os, glob, sys, json, argparse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from decode import decode_depth, fit_affine_trimmed, edge_mask

ap = argparse.ArgumentParser()
ap.add_argument("--scene", default="/n/lab_storage/ydu_lab/Lab/akiruga/curated_oracle/depth/kitti__dense/2011_09_26_drive_0095_sync_02")
ap.add_argument("--stride", type=int, default=1)
ap.add_argument("--out", default="/n/lab_storage/ydu_lab/Lab/akiruga/world_model_4d/final-website/assets/pointcloud/kitti_drive_0095.npz")
a = ap.parse_args()
D = a.scene

gt   = np.load(f"{D}/gt_depth.npy"); F, Hg, Wg = gt.shape
pred = np.load(f"{D}/pred_depth_norm.npy")
c2w  = np.load(f"{D}/pred_c2w.npy")          # PREDICTED poses; KITTI has no GT pose here
print(f"{os.path.basename(D)}  gt{gt.shape} valid {(np.isfinite(gt)&(gt>1e-3)).mean()*100:.1f}%  (sparse LiDAR)")

# standard 2011_09_26 P_rect_02, then the recorded crop, then the resize
fx = fy = 721.5377; cx, cy = 609.5593, 172.854
top, bot, left, right = 0, 375, 371, 871
cx -= left; cy -= top
sx, sy = Wg/(right-left), Hg/(bot-top)
K = np.array([[fx*sx, 0, cx*sx], [0, fy*sy, cy*sy], [0, 0, 1.0]])
print("K (assumed calib, crop+resize applied):\n", np.round(K, 3))

rel = decode_depth(pred)
rel = np.stack([cv2.resize(r, (Wg, Hg), cv2.INTER_NEAREST) for r in rel])
v = np.isfinite(gt) & (gt > 1e-3) & np.isfinite(rel)
s, t = fit_affine_trimmed(rel[v], gt[v]); met = s*rel + t
print(f"affine fit: depth = {s:.5f}*rel + {t:.5f}")
print(f"abs_rel after fit: {(np.abs(met[v]-gt[v])/gt[v]).mean():.5f}   (manifest 0.05250)")

# --- gate: the road is planar, so the right focal should minimise plane residual
uu, vv = np.meshgrid(np.arange(Wg), np.arange(Hg))
def road_resid(f):
    d = met[0]; m = np.isfinite(d) & (d > 1e-3) & (vv > int(Hg*0.75)) & (d < 30)
    z = d[m]
    P = np.stack([(uu[m]-K[0,2])/f*z, (vv[m]-K[1,2])/f*z, z], 1)
    c = P - P.mean(0)
    return float(np.sqrt(np.linalg.svd(c, compute_uv=False)[2]**2 / len(c)))
fs = np.array([K[0,0]*k for k in (0.6,0.8,0.9,1.0,1.1,1.25,1.6)])
rs = [road_resid(f) for f in fs]
print("\nroad-plane residual vs focal (assumed f = %.1f):" % K[0,0])
for f, r in zip(fs, rs):
    print(f"   f={f:7.1f}  resid={r:.4f}{'   <-- assumed' if abs(f-K[0,0])<1e-6 else ''}")
print("   best:", f"f={fs[int(np.argmin(rs))]:.1f}")

rgbf = sorted(glob.glob(f"{D}/gt_rgb/*")); assert len(rgbf) == F
RGB = np.stack([cv2.cvtColor(cv2.resize(cv2.imread(f)[top:bot, left:right], (Wg,Hg),
                interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2RGB) for f in rgbf])

st = a.stride; ys, xs = np.mgrid[0:Hg:st, 0:Wg:st]
P, C, cnt = [], [], []
for i in range(F):
    d = met[i][ys, xs]
    m = np.isfinite(d) & (d > 1e-3) & (d < 60) & edge_mask(met[i])[ys, xs]
    z = d[m]
    cam = np.stack([(xs[m]-K[0,2])/K[0,0]*z, (ys[m]-K[1,2])/K[1,1]*z, z], 1)
    P.append(((c2w[i,:3,:3] @ cam.T).T + c2w[i,:3,3]).astype(np.float32))
    C.append(RGB[i][ys, xs][m].astype(np.uint8)); cnt.append(int(m.sum()))

os.makedirs(os.path.dirname(a.out), exist_ok=True)
np.savez_compressed(a.out, points=np.concatenate(P), colors=np.concatenate(C),
                    counts=np.array(cnt,np.int32), c2w=c2w.astype(np.float32),
                    K=np.repeat(K[None],F,0).astype(np.float32), scene=os.path.basename(D))
print(f"\npoints/frame ~{sum(cnt)//F}  total {sum(cnt)}  -> {a.out} ({os.path.getsize(a.out)/1e6:.1f} MB)")
