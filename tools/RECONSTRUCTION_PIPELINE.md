# How the 3D Reconstruction gallery is built

Everything in the `#reconstruction` section — which scenes appear, how each point cloud is
made, how it reaches the browser — is reproducible from this file plus four scripts:

| step | script |
|---|---|
| 1. choose the scenes | `tools/select_reconstruction_scenes.py` → `tools/reconstruction_selection.json` |
| 2. build each cloud | `tools/build_reconstruction_scene.py` → `…/recon24/<dataset>__<scene>.npz` |
| 3. serialize + frame it | `tools/build_reconstruction_gallery.py` → `assets/viser/recon/<id>.viser` |
| 4. wire it into the page | `tools/wire_reconstruction_gallery.py` → `examples.json` |

7-Scenes needs one extra step first: `tools/add_7sc_gt_rgb.py`.

---

## 1. What a cloud actually is

**Predicted depth, GT camera pose, GT RGB colour.** Nothing in the cloud is a mesh, a
fusion, or a post-optimised reconstruction — each frame is that frame's predicted depth
map back-projected through the GT camera, and the viewer shows **one frame at a time**
(the site tried accumulating history and reverted; see README).

The model's native output is `pred_depth_norm.npy`: normalised **disparity** in `[-1,1]`,
at 288×384, carrying no metric scale. Turning that into metric points takes three steps,
each of which has a wrong-looking variant that was tried and rejected:

1. **Decode** `disp = (norm+1)/2`, floor it at its `pc`-th percentile over the whole
   video, then `depth = 1/disp - 1`. Without the percentile floor, near-zero disparities
   explode to ~1e6 and swamp the fit (on Bonn it collapsed the slope to zero).
   `pc = 2.0` everywhere **except 7-Scenes, which is 10.0** — that is what each benchmark's
   published score used (`tab/pool7sc_pc10.py` exists specifically to fix 7-Scenes from
   2.0 to 10.0, and the pool CSV records `pc=10.0` per row).
2. **Align** to GT depth with **LADS** (L1-robust affine via IRLS,
   `tools/lads_align.py`, copied from the published scorer). **One global (s,t) for the
   whole scene, never per frame**, so the relative motion between frames stays the
   model's and not the fit's. Trimmed least squares looks equivalent and is not: it
   reproduces ScanNet++/Bonn/Sintel to 4e-4 but misses KITTI by 0.004.
3. **Back-project** with the eval-grid intrinsics and place with the pose.

### The gate that keeps this honest
`build_reconstruction_scene.py` recomputes AbsRel after the fit and **refuses to write**
unless it matches the frozen `metrics.json` within 3e-3. A wrong GT array, a wrong grid,
a wrong decode or a wrong cap all fail here instead of silently producing a plausible,
wrong cloud. Measured agreement on the four scenes that were already published:

| scene | rebuilt AbsRel | frozen AbsRel |
|---|---|---|
| ScanNet++ scene_44 | 0.03117 | 0.031165 |
| Bonn person_tracking2 | 0.04158 | 0.041935 |
| Sintel sleeping_2 | 0.05803 | 0.057708 |
| KITTI drive 0095 | 0.03667 | 0.035934 |

### Per-dataset rules (all verified, do not "simplify" them away)

| | eval grid | intrinsics | pose | fit cap | render cap |
|---|---|---|---|---|---|
| ScanNet++ | 288×384 | `pred_intrinsics.npy` (the model's own K — no GT K ships) | GT | — | — |
| 7-Scenes | 288×384 | `pred_intrinsics.npy` | GT | — | — |
| Bonn | 240×320 | `K.npy` | GT | 70 m | — |
| Sintel | 240×320 | `K.npy`, **per frame** | GT | 70 m | 70 m |
| KITTI | 240×320 | `K.npy` | **predicted** | — | 60 m |

`K.npy` in `release-oracle-chosen` is the GT eval-grid K and equals, to the digit, what
the old bespoke builders derived by hand: Bonn `542.822841/2 = 271.41`; KITTI
`721.5377 × 320/500 = 461.78` with the `[0:375, 371:871]` crop; Sintel read from the
`.cam` files. It is stored **per frame**, which matters because Sintel's virtual camera
zooms (`cave_2` goes 841.9 → 379.5 over the 50-frame window; using frame 0's K for the
whole clip was wrong by up to 2.2×).

Two caveats that must never be dressed up:
* **KITTI has no pose spec in this eval**, so its frames are placed with **our predicted
  trajectory**. Never present a KITTI cloud as GT-pose placement.
* **Bonn's GT poses fail the cross-frame fusion gate** (identity beats them at every
  baseline), consistent with the ground truth being a mocap *body* frame rather than the
  camera optical frame. The camera only travels ~0.13 m, so per-frame clouds are nearly
  co-located and it is visually immaterial — but do not present Bonn as evidence of
  multi-frame consistency.

### Two cosmetic steps that do most of the visual work
* **Edge mask** (`decode.py::edge_mask`, `rel_thresh=0.04`): a pixel straddling an object
  boundary gets a depth between foreground and background and renders as a "skirt" of
  points stretching back to the wall. Pixels whose local depth gradient is large relative
  to their own depth are dropped. This is why the clouds have clean silhouettes.
* **Nearest-neighbour** resampling when the prediction grid differs from the eval grid.
  `INTER_LINEAR` blends across depth discontinuities and manufactures flying pixels.

### Density
`--stride 1`: every pixel of the eval grid becomes a point — ~107k points/frame on
288×384, ~45–74k on 240×320, 50 frames each, which is **~25 MB per scene** as a `.viser`.
This is the single biggest driver of how good the clouds look. Measured on scene_44 at a
matched camera and timestamp, `--stride 2` is visibly gappy at the published point size
and blobby/dark at a larger one, for 9.4 MB. Stride 1 is the standard; only trade it away
against a hard size limit.

---

## 2. How the scenes are chosen

The rule the first three published scenes already followed: **rank every scene of a
benchmark by the AbsRel of its oracle pool pick, take the best.** ScanNet++ scene_44
(0.0312), KITTI drive 0095 (0.0359) and Bonn person_tracking2 (0.0419) are each their
benchmark's rank 1.

`select_reconstruction_scenes.py` extends that to 24 with a per-benchmark quota
(ScanNet++ 8, 7-Scenes 5, KITTI 4, Bonn 4, Sintel 3; a benchmark that cannot fill its
share hands the slot to the next best scene anywhere, which is how ScanNet++ got a 9th).

Gates applied **before** ranking:
* **50 frames** — a short clip breaks the shared timeline (Sintel `ambush_6` has 18,
  `ambush_4` 30, `market_6` 38: all excluded).
* **GT pose on disk** — except KITTI, as above.
* **GT RGB on disk** — the cloud is coloured from real pixels, never a depth colormap.
* **camera travel ≥ 0.10 m** — a scene whose camera never moves is a still, not a
  reconstruction. This is what removes Bonn `crowd3` (0.06 m) and `synchronous` (0.01 m)
  despite their good AbsRel, and is why Bonn contributes 3 scenes rather than 4.
* **a human looks at every cloud before it ships** (step 5 below). Metrics pick the
  candidates; they do not get the last word.

Where the numbers come from:
* ScanNet++ / Bonn / KITTI / Sintel: `release-oracle-chosen/depth/<ds>/<scene>/metrics.json`
  — the frozen 16-seed release-model oracle campaign.
* 7-Scenes has **no frozen oracle folder**, so it is ranked from `tab/pool7sc_rows.csv`
  over the members whose prediction trees survived the netscratch purge — 8 of 69
  (`s5_*`, `s10_*`, which `pool7sc_pc10.py` records as sample_steps 5/10 runs of the same
  `w_2250` release checkpoint). The purged `x47_*` and `7sc_sd*` trees held the per-scene
  winners for some scenes, so 7-Scenes is ranked over a smaller pool than the others.

## 3. GT RGB, and the range bug that crushed it

Bonn, KITTI and Sintel colour from PNG frame dirs in the curated tree. ScanNet++ and
7-Scenes have no RGB beside their predictions, so both come from the loader the eval
used, GATED: the loader's depth for that index must equal the stored gt_depth
bit-for-bit before its RGB is allowed to colour anything (48/48 and 18/18 passed).

**The loader returns `videos` in [-1, 1], not [0, 1].** The original
`add_spp_gt_rgb.py` converted it with `rgb * 255 if rgb.max() <= 1.001`, which
multiplies by 255 and clips every negative -- everything below mid-grey -- to black.
ScanNet++ came out at mean 63 with its 5th percentile pinned at 0, against mean 137 for
the same frames read from the source .mkv. Every `gt_rgb.mp4` under
`release-oracle-chosen/depth/scannetpp/` and `release-oracle-chosen/pose/scannetpp/`
was written by that code and is **still dark**; this gallery no longer reads them.

`tools/add_7sc_gt_rgb.py`, with `DATASET=7scenes` or `DATASET=scannetpp`, does the
correct `(x + 1) / 2` conversion, asserts the result is not still dark, and writes
`_7scenes_rgb/` and `_scannetpp_rgb/`. Check: corrected scene_44 has mean 149.1 against
150.6 for the independent .mkv extraction -- a mean absolute difference of 2.22/255.

The cloud and the sprite read the SAME array, so the inset can never disagree with the
colours in the 3D view.

## 4. 7-Scenes specifics

7-Scenes is the one benchmark whose RGB is not already sitting beside the predictions.
`add_7sc_gt_rgb.py` pulls it from the same loader the eval used (`7scenes_5b`, 288×384,
50 frames, `no_augmentations=true`) and **gates** it: the loader's depth for that index
must equal the stored `scene_<i>_gt_depth.npy` bit-for-bit before its RGB is allowed to
colour anything. 18 of 18 scenes passed. This mirrors `add_spp_gt_rgb.py`, which did the
same for ScanNet++.

## 5. Serving

Each scene ships as a `.viser` recording played by **one shared client** at
`viser/viser-client/index.html?playbackPath=…`, rather than as a self-contained
`as_html()` page per scene. Same pixels, but the 2.9 MB client is downloaded once instead
of being inlined 24 times, and the recording avoids base64's 1.37× inflation (35 MB of
payload became a 48 MB HTML file).

**The client build and the recordings must come from the same viser version.** The
previously vendored client could not read a 1.0.27 recording at all — viser 1.0.27 writes
zstd-compressed msgpack behind an 8-byte little-endian length header, and the older
client gunzipped it and then failed to decode (`Extra 48110818 of 48110836 bytes found at
buffer[18]`). The vendored client is now copied from the installed
`viser/client/build/index.html` of the same environment that writes the recordings.

The opening view keeps the first-frame camera's forward direction and roll, with
an axial setback of 40% of that frame's median positive camera-space depth.
`tools/first_frame_camera.py` computes this view; the gallery builder uses it for
new scenes. `tools/set_first_frame_cameras.py --evidence outputs/camera-views.json`
updates existing manifest camera metadata without rebuilding recordings. It
updates both `examples.json` and `tools/reconstruction_cases.json`. The viewer
passes the calibrated up vector and field of view to the shared client and fits
the field of view to its viewport. The older oblique-camera utility remains for
historical comparisons, rather than for the published default.

## 6. Looking at them

Metrics choose candidates; eyes decide. `tools/shoot_reconstruction_thumbs.py` loads every
scene in the real client, pauses it at a fixed timestamp and screenshots it, and those
frames double as the gallery thumbnails. Every scene in the gallery was inspected in that
render before shipping, and anything that looked wrong was dropped in favour of the next
ranked candidate — the record of what was rejected and why is in
`tools/reconstruction_selection.json` and in the notes below.

## 7. Adding another scene later

```bash
PY=/n/lab_storage/ydu_lab/akiruga/.conda/envs/test2/bin/python3
OUT=/n/lab_storage/ydu_lab/Lab/akiruga/world_model_4d/final-website/assets/pointcloud

# 1. cloud (the AbsRel gate will refuse a mismatched GT/grid/decode)
$PY tools/build_reconstruction_scene.py --dataset sintel --scene alley_2 \
    --stride 1 --out $OUT/recon24/sintel__alley_2.npz
# 2. recording + opening camera
$PY tools/build_reconstruction_gallery.py --npz $OUT/recon24/sintel__alley_2.npz \
    --out assets/viser/recon/sintel-alley-2.viser --meta $OUT/recon24_viser/sintel__alley_2.json
# 3. manifest + RGB sprite + thumbnail
$PY tools/wire_reconstruction_gallery.py
$PY tools/shoot_reconstruction_thumbs.py --only sintel-alley-2
```

`python3` on these nodes has no numpy; use the conda interpreter above for everything.
