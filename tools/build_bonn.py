#!/usr/bin/env python
"""Per-frame point clouds for a Bonn scene: predicted depth, GT pose, GT RGB.

Bonn differs from ScanNet++ in three ways:
  - pred_depth_norm is 288x384 but gt_depth/K are 240x320, so predictions are
    resampled onto the eval grid first;
  - intrinsics are not stored, but Bonn's are known and the crop is full-frame
    (640x480 is already 4:3), so K just halves;
  - GT RGB is already linked in the curated tree, so no scene identification.

NOTE: Bonn GT poses fail the cross-frame fusion gate (identity beats them at
every baseline), consistent with the groundtruth being a mocap BODY frame
rather than the camera optical frame. The camera only travels ~0.19 m, so
per-frame clouds are nearly co-located and this is visually immaterial -- but
do not present the Bonn cloud as evidence of multi-frame consistency.
"""
import numpy as np, cv2, os, glob, argparse, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from decode import decode_depth, fit_affine_trimmed, edge_mask

ap = argparse.ArgumentParser()
ap.add_argument("--scene", default="/n/lab_storage/ydu_lab/Lab/akiruga/curated_oracle/depth/bonn__dense/rgbd_bonn_person_tracking2")
ap.add_argument("--stride", type=int, default=2)
ap.add_argument("--pred", default=None,
                help="explicit pred_depth_norm.npy (e.g. a pool member outside the index)")
ap.add_argument("--member", default=None,
                help="use this member's prediction instead of the curated oracle pick")
ap.add_argument("--out", default="/n/lab_storage/ydu_lab/Lab/akiruga/world_model_4d/final-website/assets/pointcloud/bonn_person_tracking2.npz")
a = ap.parse_args()
D = a.scene

if a.pred:
    pred=np.load(a.pred); print(f"using pred {a.pred}")
elif a.member:
    import json
    IDX="/n/lab_storage/ydu_lab/Lab/akiruga/world_model_4d/video_world_model_new/tab/curate/curate_index.json"
    PRE="/n/netscratch/ydu_lab/Lab/akiruga/"
    RESC="/n/lab_storage/ydu_lab/Lab/akiruga/world_model_4d/netscratch_rescue_20261011/"
    sc=os.path.basename(D)
    hit=[r for r in json.load(open(IDX))["depth_pose"]
         if r["bench"]=="bonn" and r["scene"]==sc and r["member"]==a.member]
    assert hit, f"member {a.member} not found for {sc}"
    pp=hit[0]["files"]["pred_depth_norm.npy"]
    pp=pp if os.path.exists(pp) else RESC+pp[len(PRE):]
    pred=np.load(pp); print(f"using member {a.member}")
else:
    pred = np.load(f"{D}/pred_depth_norm.npy")
gt   = np.load(f"{D}/gt_depth.npy")               # (50,240,320) metres
c2w  = np.load(f"{D}/gt_c2w.npy")
F, Hg, Wg = gt.shape
K = np.array([[542.822841,0,315.593520],[0,542.576870,237.756098],[0,0,1.0]]); K[:2,:] *= 0.5
print(f"{os.path.basename(D)}  pred{pred.shape} -> gt grid {Hg}x{Wg}")

rel = decode_depth(pred)
# INTER_LINEAR blends across depth discontinuities and manufactures flying pixels
rel = np.stack([cv2.resize(r,(Wg,Hg),interpolation=cv2.INTER_NEAREST) for r in rel])

v = np.isfinite(gt) & (gt>1e-3) & np.isfinite(rel)
s, t = fit_affine_trimmed(rel[v], gt[v])
met = s*rel+t
print(f"affine fit: depth = {s:.5f}*rel + {t:.5f}")
print(f"abs_rel after fit: {(np.abs(met[v]-gt[v])/gt[v]).mean():.5f}")

rgbf = sorted(glob.glob(f"{D}/gt_rgb/*"))
assert len(rgbf) == F, f"{len(rgbf)} rgb vs {F} frames"
RGB = np.stack([cv2.cvtColor(cv2.resize(cv2.imread(f),(Wg,Hg),interpolation=cv2.INTER_AREA),
                             cv2.COLOR_BGR2RGB) for f in rgbf])
print(f"GT RGB {RGB.shape} from {D}/gt_rgb")

st = a.stride
ys, xs = np.mgrid[0:Hg:st, 0:Wg:st]
fx,fy,cx,cy = K[0,0],K[1,1],K[0,2],K[1,2]
P,C,cnt = [],[],[]
for i in range(F):
    keep = edge_mask(met[i])[ys,xs]
    d = met[i][ys,xs]; msk = np.isfinite(d)&(d>1e-3)&keep
    z = d[msk]
    cam = np.stack([(xs[msk]-cx)/fx*z, (ys[msk]-cy)/fy*z, z],1)   # OpenCV
    P.append(((c2w[i,:3,:3]@cam.T).T + c2w[i,:3,3]).astype(np.float32))
    C.append(RGB[i][ys,xs][msk].astype(np.uint8)); cnt.append(len(z))

os.makedirs(os.path.dirname(a.out), exist_ok=True)
np.savez_compressed(a.out, points=np.concatenate(P), colors=np.concatenate(C),
                    counts=np.array(cnt,np.int32), c2w=c2w.astype(np.float32),
                    K=np.repeat(K[None],F,0).astype(np.float32),
                    scene=os.path.basename(D))
print(f"points/frame ~{sum(cnt)//F}  total {sum(cnt)}  -> {a.out} ({os.path.getsize(a.out)/1e6:.1f} MB)")
