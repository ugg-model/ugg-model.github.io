#!/usr/bin/env python
"""Identify curated `scene_44` by its MOTION SIGNATURE.

Our GT poses are gauged (frame 0 == identity), so absolute poses can't be
matched. Inter-frame step distances and rotation angles are invariant to that
gauge, so we search every val scene over (start frame, stride) for a 50-frame
window whose motion pattern matches ours.
"""
import numpy as np, json, os

SPP = "/n/netscratch/ydu_lab/Everyone/datasets/scannetpp"
D   = "/n/lab_storage/ydu_lab/Lab/akiruga/curated_oracle/depth/scannetpp__dense/scene_44"
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "scene44_identity.json")

ours = np.load(f"{D}/gt_c2w.npy")
T, R = ours[:, :3, 3], ours[:, :3, :3]
d_ours = np.linalg.norm(np.diff(T, axis=0), axis=1)                      # 49 steps
cos = np.clip((np.einsum('nij,nij->n', R[:-1], R[1:]) - 1) / 2, -1, 1)
a_ours = np.degrees(np.arccos(cos))                                      # 49 angles
print(f"ours: {len(ours)} frames, path {d_ours.sum():.4f} m, "
      f"step {d_ours.mean():.4f}+-{d_ours.std():.4f} m, rot {a_ours.mean():.3f} deg/step")

scenes = [l.strip() for l in open(f"{SPP}/splits/nvs_sem_val.txt") if l.strip()]
M = len(ours)
best = []
for si, sc in enumerate(scenes):
    p = f"{SPP}/data/{sc}/iphone/pose_intrinsic_imu.json"
    if not os.path.exists(p): continue
    try: j = json.load(open(p))
    except Exception: continue
    keys = sorted(j.keys())
    P = np.array([j[k]["aligned_pose"] for k in keys], dtype=np.float64)
    t, r = P[:, :3, 3], P[:, :3, :3]
    N = len(P)
    for s in range(1, 25):
        if N < M * s + 2: break
        step = np.linalg.norm(t[s:] - t[:-s], axis=1)                    # ||t[f+s]-t[f]||
        c = np.clip((np.einsum('nij,nij->n', r[:-s], r[s:]) - 1) / 2, -1, 1)
        ang = np.degrees(np.arccos(c))
        last = N - (M - 1) * s - 1
        if last <= 0: continue
        idx = np.arange(0, last)[:, None] + np.arange(M - 1)[None, :] * s
        err = (np.abs(step[idx] - d_ours).mean(1) / max(d_ours.mean(), 1e-9)
               + np.abs(ang[idx] - a_ours).mean(1) / max(a_ours.mean(), 1e-9))
        f = int(np.argmin(err))
        best.append((float(err[f]), sc, s, f, N))
    if (si + 1) % 10 == 0: print(f"  ...{si+1}/{len(scenes)}", flush=True)

best.sort()
print("\ntop matches (relative motion error; 0 = identical):")
for e, sc, s, f, N in best[:6]:
    print(f"  {e:10.6f}  {sc}  stride={s:3d} start={f:5d}  (N={N})")

e, sc, s, f, N = best[0]
if e < 0.02:
    print(f"\nIDENTIFIED: scene_44 = {sc}, frames {f}..{f+(M-1)*s} step {s}")
    json.dump({"curated":"scene_44","scannetpp_scene":sc,"start":f,"stride":s,
               "n_frames":M,"motion_err":e}, open(OUT,"w"), indent=1)
else:
    print(f"\nNO CONFIDENT MATCH (best {e:.4f}) -- not guessing.")
