#!/usr/bin/env python
"""Per-scene ours-vs-Geo4D under IDENTICAL treatment.

Both predictions are relative, so both get the same trimmed affine fit to the
same GT on the same pixel mask and the same grid. Using a different aligner for
ours than for the baseline would flatter us.
"""
import numpy as np, cv2, json, glob, os, sys, csv
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from decode import decode_depth, fit_affine_trimmed

# Sintel stores ~1e11 as a sky sentinel and Bonn caps at 70 m; without this the
# fit is dominated by non-surfaces and the numbers are meaningless.
MAXD = {"sintel": 70.0, "bonn": 70.0, "kitti": None}
CUR = "/n/lab_storage/ydu_lab/Lab/akiruga/curated_oracle/depth"
G4  = "/n/netscratch/ydu_lab/Lab/akiruga/vwm_raw_outputs/video_world_model_new/eval_pi3/preds_baselines/geo4d"
RES = "/n/lab_storage/ydu_lab/Lab/akiruga/world_model_4d/netscratch_rescue_20261011/vwm_raw_outputs/video_world_model_new/eval_pi3/preds_baselines/geo4d"

def resolve(p): return p if os.path.exists(p) else p.replace(G4, RES)

def absrel(pred, gt, mask):
    p, g = pred[mask], gt[mask]
    s, t = fit_affine_trimmed(p, g)
    return float((np.abs(s*p + t - g)/g).mean())

rows = []
for cell in ("bonn__dense", "kitti__dense", "sintel__dense"):
    bench = cell.split("__")[0]
    for scene in sorted(os.listdir(f"{CUR}/{cell}")):
        d = f"{CUR}/{cell}/{scene}"
        gp = f"{d}/gt_depth.npy"
        if not os.path.exists(gp): continue
        gt = np.load(gp); Hg, Wg = gt.shape[1:]
        m = np.isfinite(gt) & (gt > 1e-3)
        if MAXD[bench]: m &= gt < MAXD[bench]

        rel = decode_depth(np.load(f"{d}/pred_depth_norm.npy"))
        rel = np.stack([cv2.resize(r, (Wg, Hg), cv2.INTER_NEAREST) for r in rel])

        gd = resolve(f"{G4}/{bench}/{scene}/pred_depth_metric.npy")
        if not os.path.exists(gd): continue
        gg = np.load(gd).astype(np.float32)
        if gg.shape[0] != gt.shape[0]: continue
        gg = np.stack([cv2.resize(x, (Wg, Hg), cv2.INTER_NEAREST) for x in gg])

        mm = m & np.isfinite(rel) & np.isfinite(gg)
        if mm.sum() < 5000: continue
        ours = absrel(rel, gt, mm); geo = absrel(gg, gt, mm)
        rows.append(dict(bench=bench, scene=scene, ours=ours, geo4d=geo,
                         win=geo-ours, rel_gain=(geo-ours)/geo))

rows.sort(key=lambda r: -r["rel_gain"])
print(f"{'bench':8s} {'scene':30s} {'ours':>8s} {'geo4d':>8s} {'gain':>8s} {'rel':>7s}")
for r in rows:
    flag = "  <-- WE WIN" if r["win"] > 0 else ""
    print(f"{r['bench']:8s} {r['scene'][:30]:30s} {r['ours']:8.4f} {r['geo4d']:8.4f} "
          f"{r['win']:+8.4f} {r['rel_gain']*100:+6.1f}%{flag}")
w = sum(1 for r in rows if r["win"] > 0)
print(f"\nwe win {w}/{len(rows)} scenes")
with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "ours_vs_geo4d.csv"), "w", newline="") as fh:
    cw = csv.DictWriter(fh, fieldnames=list(rows[0].keys())); cw.writeheader(); cw.writerows(rows)
