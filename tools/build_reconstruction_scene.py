#!/usr/bin/env python
"""Per-frame point clouds for the 3D Reconstruction gallery: PREDICTED depth, GT pose, GT RGB.

One builder for every benchmark, replacing the four divergent per-dataset scripts
(build_pointcloud / build_bonn / build_kitti / build_sintel). Their dataset-specific
rules are preserved exactly; see tools/RECONSTRUCTION_PIPELINE.md for the derivation
and for the evidence that the shared K.npy equals each script's hand-derived K.

The model emits normalised DISPARITY in [-1,1], so it carries no metric scale. One
global affine (s,t) of the decoded depth to GT depth is fitted over the WHOLE scene --
never per frame, so the relative motion between frames stays the model's. Every build
re-derives abs_rel after that fit and refuses to write unless it matches the frozen
metrics.json, which makes a wrong GT, a wrong grid or a wrong decode fail loudly.
"""
import argparse, csv, json, os, sys
import numpy as np, cv2

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from decode import decode_depth, edge_mask
from lads_align import fit_affine_lads_capped, metrics as lads_metrics

ORACLE = "/n/lab_storage/ydu_lab/Lab/akiruga/release-oracle-chosen/depth"
CURATED = "/n/lab_storage/ydu_lab/Lab/akiruga/curated_oracle/depth"
PREDS = "/n/lab_storage/ydu_lab/Lab/akiruga/world_model_4d/standardized_eval/preds/ours"
POOL7SC = "/n/lab_storage/ydu_lab/Lab/akiruga/world_model_4d/tab/pool7sc_rows.csv"
_PC = "/n/lab_storage/ydu_lab/Lab/akiruga/world_model_4d/final-website/assets/pointcloud"
# GT RGB pulled from the loader with the correct [-1,1] -> [0,255] range. ScanNet++'s
# shipped gt_rgb.mp4 was written with that range treated as [0,1], so it is crushed dark
# (mean 63 against 137 for the same frames off the source .mkv); prefer these.
RGB_NPZ = {"7scenes": f"{_PC}/_7scenes_rgb", "scannetpp": f"{_PC}/_scannetpp_rgb"}

# Far caps. FIT_MAXD is the published evaluation spec -- it decides which GT pixels
# score, so it must match or the rebuilt abs_rel will not reproduce (KITTI's LiDAR is
# scored uncapped; capping it at 60 m moves abs_rel 0.0359 -> 0.0397). RENDER_MAXD only
# trims far points out of the cloud, where KITTI's horizon is noise.
FIT_MAXD = {"sintel": 70.0, "bonn": 70.0}
# Decode percentile clip, per the scorer that produced each frozen number. 7-Scenes dense
# was re-scored at pc=10 (tab/pool7sc_pc10.py: "fix the pc=2.0 -> pc=10 understatement").
FIT_PC = {"7scenes": 10.0}
RENDER_MAXD = {"sintel": 70.0, "kitti": 60.0}


def load_scene(dataset, scene, member=None):
    """Return (pred_norm, gt, K, c2w, rgb, target_abs_rel, pose_source)."""
    if dataset == "7scenes":
        assert member, "7-Scenes needs an explicit --member (no frozen oracle folder)"
        d = f"{PREDS}/{member}/7scenes"
        pred = np.load(f"{d}/{scene}_pred_depth_norm.npy")
        gt = np.load(f"{d}/{scene}_gt_depth.npy")
        K = np.load(f"{d}/{scene}_pred_intrinsics.npy")
        c2w = np.load(f"{d}/{scene}_gt_c2w.npy")
        rgb = np.load(f"{RGB_NPZ['7scenes']}/{scene}.npz")["rgb"]
        # The frozen number lives in the pool CSV, not beside the prediction.
        # The CSV carries a few duplicated (member, scene) rows; take the same
        # value the selector ranked on, which is the minimum.
        hits = [float(r["absrel"]) for r in csv.DictReader(open(POOL7SC))
                if r["member"] == member and f"scene_{r['scene']}" == scene]
        target = min(hits) if hits else None
        return pred, gt, K, c2w, rgb, target, "gt"

    d = f"{ORACLE}/{dataset}/{scene}"
    meta = json.load(open(f"{d}/metrics.json"))
    pred = np.load(f"{d}/pred_depth_norm.npy")
    gt = np.load(f"{d}/gt_depth.npy")
    # K.npy is the GT eval-grid intrinsics (per frame, so Sintel's zoom is carried).
    # ScanNet++ ships no K.npy, and the published cloud used the model's own K.
    K = np.load(f"{d}/K.npy") if os.path.exists(f"{d}/K.npy") else np.load(f"{d}/pred_intrinsics.npy")
    if dataset == "kitti":
        # KITTI has no pose spec in this eval, so frames are placed with OUR predicted
        # trajectory. Never present a KITTI cloud as GT-pose placement.
        c2w, pose_source = np.load(f"{d}/pred_c2w.npy"), "pred"
    else:
        sub = {"scannetpp": "scannetpp__dense", "bonn": "bonn__dense", "sintel": "sintel__dense"}[dataset]
        c2w, pose_source = np.load(f"{CURATED}/{sub}/{scene}/gt_c2w.npy"), "gt"
    fixed = f"{RGB_NPZ.get(dataset, '')}/{scene}.npz"
    rgb = np.load(fixed)["rgb"] if os.path.exists(fixed) else read_video(f"{d}/gt_rgb.mp4")
    return pred, gt, K, c2w, rgb, meta["abs_rel"], pose_source


def read_video(path):
    cap = cv2.VideoCapture(path)
    frames = []
    while True:
        ok, f = cap.read()
        if not ok:
            break
        frames.append(cv2.cvtColor(f, cv2.COLOR_BGR2RGB))
    cap.release()
    assert frames, f"no frames decoded from {path}"
    return np.stack(frames)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dataset", required=True,
                    choices=["scannetpp", "bonn", "kitti", "sintel", "7scenes"])
    ap.add_argument("--scene", required=True)
    ap.add_argument("--member", default=None, help="7-Scenes only: which pool member to render")
    ap.add_argument("--stride", type=int, default=2, help="pixel stride; 1 is the full eval grid")
    ap.add_argument("--tolerance", type=float, default=3e-3,
                    help="allowed |rebuilt abs_rel - frozen abs_rel| before the build is refused")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    pred, gt, K, c2w, RGB, target, pose_source = load_scene(a.dataset, a.scene, a.member)
    F, Hg, Wg = gt.shape
    fit_maxd, render_maxd = FIT_MAXD.get(a.dataset), RENDER_MAXD.get(a.dataset)
    print(f"{a.dataset}/{a.scene}: pred{pred.shape} gt{gt.shape} rgb{RGB.shape} pose={pose_source}")
    assert len(c2w) == F and len(K) == F, f"c2w {len(c2w)} / K {len(K)} vs {F} frames"

    rel = decode_depth(pred, percentile_clip=FIT_PC.get(a.dataset, 2.0))
    if rel.shape[1:] != (Hg, Wg):
        # INTER_LINEAR blends across depth discontinuities and manufactures flying pixels.
        rel = np.stack([cv2.resize(r, (Wg, Hg), interpolation=cv2.INTER_NEAREST) for r in rel])
    if RGB.shape[1:3] != (Hg, Wg):
        RGB = np.stack([cv2.resize(r, (Wg, Hg), interpolation=cv2.INTER_AREA) for r in RGB])
    assert len(RGB) == F, f"{len(RGB)} rgb frames vs {F}"

    v = np.isfinite(gt) & (gt > 1e-3) & np.isfinite(rel)
    if fit_maxd:
        v &= gt < fit_maxd
    # LADS, the published alignment -- not a look-alike. Fitting with trimmed least
    # squares instead reproduces ScanNet++/Bonn/Sintel to 4e-4 but misses KITTI by
    # 0.004, which is the whole point of gating on the frozen number.
    s, t = fit_affine_lads_capped(rel[v], gt[v])
    met = s * rel + t
    abs_rel, delta1 = lads_metrics(met[v], gt[v])
    print(f"  lads: depth = {s:.5f}*rel + {t:.5f}   abs_rel {abs_rel:.5f} d1 {delta1:.4f}  (frozen {target})")
    if target is not None and abs(abs_rel - target) > a.tolerance:
        raise SystemExit(f"REFUSED: abs_rel {abs_rel:.5f} != frozen {target:.5f}; "
                         "the GT, the grid or the decode does not match the published cell")

    ys, xs = np.mgrid[0:Hg:a.stride, 0:Wg:a.stride]
    P, C, cnt = [], [], []
    for i in range(F):
        d = met[i][ys, xs]
        m = np.isfinite(d) & (d > 1e-3) & edge_mask(met[i])[ys, xs]
        if render_maxd:
            m &= d < render_maxd
        z = d[m]
        k = K[i]
        cam = np.stack([(xs[m] - k[0, 2]) / k[0, 0] * z, (ys[m] - k[1, 2]) / k[1, 1] * z, z], 1)
        P.append(((c2w[i, :3, :3] @ cam.T).T + c2w[i, :3, 3]).astype(np.float32))
        C.append(RGB[i][ys, xs][m].astype(np.uint8))
        cnt.append(int(m.sum()))

    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    np.savez_compressed(a.out, points=np.concatenate(P), colors=np.concatenate(C),
                        counts=np.array(cnt, np.int32), c2w=c2w.astype(np.float32),
                        K=np.asarray(K, np.float32), scene=a.scene, dataset=a.dataset,
                        pose_source=pose_source, stride=a.stride, abs_rel=abs_rel, delta1=delta1,
                        frozen_abs_rel=(target if target is not None else np.nan),
                        affine=np.array([s, t], np.float64))
    print(f"  points/frame ~{sum(cnt)//F}  total {sum(cnt)}  -> {a.out} "
          f"({os.path.getsize(a.out)/1e6:.1f} MB)")


if __name__ == "__main__":
    main()
