#!/usr/bin/env python
"""Extract GT RGB straight from the loader, for the benchmarks that have no RGB on disk.

7-Scenes has no frozen oracle folder, and ScanNet++'s shipped gt_rgb.mp4 is unusable
(see below), so both are pulled from the same loader the eval used and GATED: the
loader's depth for that index must equal the stored gt_depth bit-for-bit before its RGB
is allowed to colour anything. A scene that fails is skipped loudly rather than coloured
with someone else's pixels.

THE RANGE BUG, which is the reason this script exists in this form: the loader returns
`videos` in [-1, 1], not [0, 1]. final-website/tools/add_spp_gt_rgb.py converted it with
`rgb * 255 if rgb.max() <= 1.001`, which multiplies by 255 and clips every negative --
i.e. everything below mid-grey -- to black. ScanNet++ RGB came out at mean 63 against
137 for the same frames read from the source .mkv, with the 5th percentile pinned at 0.
The fix is (x + 1) / 2. Any gt_rgb.mp4 under release-oracle-chosen/depth/scannetpp/ was
written by the old code and is still dark.
"""
import os, sys
import numpy as np

REPO = "/n/lab_storage/ydu_lab/Lab/akiruga/world_model_4d/video_world_model_new"
PREDS = "/n/lab_storage/ydu_lab/Lab/akiruga/world_model_4d/standardized_eval/preds/ours"
DATASET = os.environ.get("DATASET", "7scenes")             # 7scenes | scannetpp
REF_MEMBER = os.environ.get("REF_MEMBER", "s10_sd4")      # any surviving member: GT is shared
SPP_REF = ("/n/lab_storage/ydu_lab/Lab/akiruga/world_model_4d/netscratch_rescue_20261011/"
           "vwm_spp_overflow/hedge_spdepth_2250_sd74_st40/scannetpp")
OUT = os.environ.get("OUT", "/n/lab_storage/ydu_lab/Lab/akiruga/world_model_4d/"
                            "final-website/assets/pointcloud/_7scenes_rgb")

sys.path.insert(0, REPO); os.chdir(REPO)
from hydra import compose
from hydra.initialize import initialize_config_dir
from omegaconf import OmegaConf
if DATASET == "7scenes":
    from datasets.sevenscenes import SevenScenesDataset as Loader
    CFG, REF = "7scenes_5b", lambda n: f"{PREDS}/{REF_MEMBER}/7scenes/{n}_gt_depth.npy"
else:
    from datasets.scannetpp import ScanNetppDataset as Loader
    CFG, REF = "scannetpp_full_5b", lambda n: f"{SPP_REF}/{n}_gt_depth.npy"

# Same grid and frame rule as gpu1_7sc.sh: 7scenes_5b at 288x384, 50 frames, no augmentation.
with initialize_config_dir(version_base=None, config_dir=f"{REPO}/configurations"):
    cfg = compose(config_name="config", overrides=[
        "experiment=exp_video", f"dataset={CFG}", "experiment.tasks=[test]",
        "dataset.n_frames=50", "dataset.height=288", "dataset.width=384",
        "dataset.raymap_height=36", "dataset.raymap_width=48",
        "++dataset.use_sky_mask=false", "++dataset.no_augmentations=true",
    ])
    OmegaConf.resolve(cfg)

ds = Loader(cfg.dataset, split="test")
os.makedirs(OUT, exist_ok=True)
print(f"dataset: {len(ds)} scenes -> {OUT}", flush=True)

ok = fail = 0
for i in range(len(ds)):
    name = f"scene_{i}"
    ref = REF(name)
    if not os.path.exists(ref):
        print(f"  {name}: no reference gt_depth -> skip", flush=True); fail += 1; continue
    b = ds[i]
    gt_ref = np.load(ref)
    d = b.get("depths_raw", b.get("depths"))
    d = np.squeeze(d.numpy() if hasattr(d, "numpy") else np.asarray(d))
    if d.shape != gt_ref.shape or not np.array_equal(d, gt_ref):
        print(f"  {name}: DEPTH GATE FAILED (loader {d.shape} vs stored {gt_ref.shape}) -> skip",
              flush=True); fail += 1; continue
    rgb = b["frames"] if "frames" in b else b["videos"]
    rgb = rgb.numpy() if hasattr(rgb, "numpy") else np.asarray(rgb)
    if rgb.ndim == 4 and rgb.shape[1] in (1, 3):           # (T,C,H,W) -> (T,H,W,C)
        rgb = np.transpose(rgb, (0, 2, 3, 1))
    # [-1,1] -> [0,255]. Scaling by 255 and clipping instead crushes every pixel
    # below mid-grey to black; that is the bug this script was written to undo.
    if rgb.min() < -0.01:
        rgb = (rgb + 1.0) * 0.5 * 255.0
    elif rgb.max() <= 1.001:
        rgb = rgb * 255.0
    rgb = np.clip(rgb, 0, 255).astype(np.uint8)
    assert rgb.mean() > 50, f"{name}: mean {rgb.mean():.1f} is still too dark"
    np.savez_compressed(f"{OUT}/{name}.npz", rgb=rgb[:len(gt_ref)], scene=name,
                        gate=f"depth equals {ref}")
    ok += 1
    print(f"  {name}: gate ok, rgb {rgb.shape} -> {OUT}/{name}.npz", flush=True)
print(f"gate passed {ok}, failed {fail}")
