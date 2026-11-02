#!/usr/bin/env python
"""Pick the 3D Reconstruction gallery from the frozen release-model oracle.

The rule the three published scenes already follow: rank every scene of a benchmark
by the AbsRel of its oracle pool pick and take the best. scene_44 (0.0312), KITTI
drive 0095 (0.0359) and Bonn person_tracking2 (0.0419) are each their benchmark's
rank 1. This extends that to 24 with a fixed per-benchmark quota so one dataset
cannot take over the gallery, and records every gate it applied.

Gates, applied before ranking:
  * 50 frames        -- a short scene (Sintel ambush_6 has 18) breaks the shared timeline
  * GT pose on disk  -- except KITTI, which has no pose spec here and is placed with
                        our predicted trajectory (recorded as pose_source=pred)
  * GT RGB on disk   -- the cloud is coloured from it, never from a depth colormap
  * camera travel    -- a scene whose camera barely moves is a still, not a reconstruction

Writes tools/reconstruction_selection.json.
"""
import csv, json, os
import numpy as np

ORACLE = "/n/lab_storage/ydu_lab/Lab/akiruga/release-oracle-chosen/depth"
CURATED = "/n/lab_storage/ydu_lab/Lab/akiruga/curated_oracle/depth"
PREDS = "/n/lab_storage/ydu_lab/Lab/akiruga/world_model_4d/standardized_eval/preds/ours"
POOL7SC = "/n/lab_storage/ydu_lab/Lab/akiruga/world_model_4d/tab/pool7sc_rows.csv"
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "reconstruction_selection.json")

QUOTA = {"scannetpp": 8, "7scenes": 5, "kitti": 4, "bonn": 4, "sintel": 3}
TOTAL = 24   # quotas are targets; a benchmark that cannot fill its share (Bonn has only
             # five scenes, two of them static) hands the slot to the next best scene anywhere
MIN_TRAVEL_M = 0.10
CURATED_SUB = {"scannetpp": "scannetpp__dense", "bonn": "bonn__dense", "sintel": "sintel__dense"}


def travel(c2w):
    return float(np.abs(np.diff(c2w[:, :3, 3], axis=0)).sum(0).max())


def candidates():
    rows = []
    for ds in ("scannetpp", "bonn", "kitti", "sintel"):
        for scene in sorted(os.listdir(f"{ORACLE}/{ds}")):
            d = f"{ORACLE}/{ds}/{scene}"
            m = json.load(open(f"{d}/metrics.json"))
            skip = []
            if m["n_frames"] != 50:
                skip.append(f"{m['n_frames']} frames")
            if not os.path.exists(f"{d}/gt_rgb.mp4"):
                skip.append("no gt_rgb.mp4")
            pose = None
            if ds == "kitti":
                pose, pose_source = f"{d}/pred_c2w.npy", "pred"
            else:
                pose, pose_source = f"{CURATED}/{CURATED_SUB[ds]}/{scene}/gt_c2w.npy", "gt"
                if not os.path.exists(pose):
                    skip.append("no gt_c2w")
            t = travel(np.load(pose)) if os.path.exists(pose) else 0.0
            if t < MIN_TRAVEL_M:
                skip.append(f"camera travels {t:.2f} m")
            rows.append(dict(dataset=ds, scene=scene, abs_rel=m["abs_rel"], delta1=m["delta1"],
                             member=m["member"], pose_source=pose_source, travel_m=round(t, 3),
                             frames=m["n_frames"], skip=skip))

    # 7-Scenes has no frozen oracle folder: rank its dense pool here, over the members
    # whose prediction trees survived the netscratch purge (8 of 69: s5_*, s10_*, which
    # pool7sc_pc10.py records as sample_steps 5/10 runs of the same w_2250 release ckpt).
    best = {}
    for r in csv.DictReader(open(POOL7SC)):
        d = f"{PREDS}/{r['member']}/7scenes"
        if not os.path.exists(f"{d}/scene_{r['scene']}_pred_depth_norm.npy"):
            continue
        v = float(r["absrel"])
        if r["scene"] not in best or v < best[r["scene"]][0]:
            best[r["scene"]] = (v, r["member"], float(r["d1"]))
    for sc, (v, member, d1) in best.items():
        scene = f"scene_{sc}"
        d = f"{PREDS}/{member}/7scenes"
        skip = []
        gt_c2w = f"{d}/{scene}_gt_c2w.npy"
        if not os.path.exists(gt_c2w):
            skip.append("no gt_c2w")
        t = travel(np.load(gt_c2w)) if os.path.exists(gt_c2w) else 0.0
        if t < MIN_TRAVEL_M:
            skip.append(f"camera travels {t:.2f} m")
        rows.append(dict(dataset="7scenes", scene=scene, abs_rel=v, delta1=d1, member=member,
                         pose_source="gt", travel_m=round(t, 3), frames=50, skip=skip))
    return rows


def main():
    rows = candidates()
    picked = []
    for ds, n in QUOTA.items():
        ok = sorted([r for r in rows if r["dataset"] == ds and not r["skip"]],
                    key=lambda r: r["abs_rel"])
        for rank, r in enumerate(ok[:n], 1):
            picked.append(dict(r, rank_in_dataset=rank))
        print(f"{ds:10s} {len(ok):3d} eligible of "
              f"{sum(1 for r in rows if r['dataset']==ds):3d} -> took {min(n,len(ok))}")
        for r in rows:
            if r["dataset"] == ds and r["skip"]:
                print(f"            gated out {r['scene']:34s} {'; '.join(r['skip'])}")
    if len(picked) < TOTAL:
        taken = {(r["dataset"], r["scene"]) for r in picked}
        spare = sorted([r for r in rows if not r["skip"] and (r["dataset"], r["scene"]) not in taken],
                       key=lambda r: r["abs_rel"])
        for r in spare[:TOTAL - len(picked)]:
            rank = sum(1 for q in picked if q["dataset"] == r["dataset"]) + 1
            picked.append(dict(r, rank_in_dataset=rank))
            print(f"  fill       {r['dataset']}/{r['scene']} (abs_rel {r['abs_rel']:.5f})")
    picked.sort(key=lambda r: (r["dataset"], r["abs_rel"]))
    json.dump({"quota": QUOTA, "min_travel_m": MIN_TRAVEL_M,
               "selected": picked, "candidates": rows}, open(OUT, "w"), indent=1)
    print(f"\nselected {len(picked)} scenes -> {OUT}")
    for r in picked:
        print(f"  {r['dataset']:10s} {r['scene']:34s} abs_rel {r['abs_rel']:.5f} "
              f"d1 {r['delta1']:.4f} travel {r['travel_m']:5.2f} m  pose={r['pose_source']}")


if __name__ == "__main__":
    main()
