# Selected indoor Text-to-4D scenes

The website publishes exactly 24 indoor scenes, labelled Scene 01–24 in order.
The user's choices referred to the previous website labels:

    22 24 30 31 33 36 37 38 39 40 43 46
    47 48 49 50 52 53 56 57 58 60 65 66

Subtract 22 to obtain the original `sample_XXX` ID. Former Scene 22 is
`sample_000`, the kitchen-and-dining prompt. The ordered allowlist is
`assets/text4d-showcase.mjs`; `cases.json` and the generation section of
`examples.json` contain only those cases. Original non-indoor examples and the
21 unused indoor candidates have been removed from the published repository.
The source collections in lab storage are unchanged.

## Point-cloud protocol

Source: `/n/lab_storage/ydu_lab/Lab/akiruga/text4d_indoor45/samples`.

- Read `depth_vae_depth.npy` directly (three channels, frames, height, width).
  Average its three signed-disparity channels, then decode camera-space depth as
  `(1 / ((mean + 1) / 2) - 1) * depth_scale` for finite disparity in (0,1).
  The previous per-clip depth/pose scale is retained, with provenance. Neither
  channel is metric; no ground truth is used.
- Rank valid positive finite depths by `depth_vae_conf.npy` separately in each
  frame. Retain exactly `floor(0.95 * valid_count)`; break equal-confidence ties
  by row-major pixel index. Invalid confidence is excluded from valid_count.
- Store rejected depths as zero in the website payload. Do not apply the former
  edge mask, percentile disparity floor, or far-depth cutoff. There is no runtime
  distance filter or checkbox. No history is accumulated.
- Keep full pixel resolution, source RGB values, exported intrinsics and c2w.
  The default observer keeps the first camera's forward/up axes and sits behind
  it by 40% of the first frame's median retained depth. Calibrated field of view
  fits the viewport. Frame-center following remains active; Reset view keeps
  playback time and translates that first-camera view with the current center.
  Robust frame bounds remain in metadata for clip planes and marker sizing.
- RGB/depth preview sprites and the RGB video keep their existing source frames.
  The depth inset is the supplied colormapped rendering; it is not confidence
  masked. RGB, depth and camera previews share the cloud's 10 FPS clock.

`provenance.json` records source/published hashes, scene mapping, per-frame valid
and retained counts, confidence thresholds, and retained scale identifiability.
All generated output replacement is atomic so source-tree hardlinks are not
modified by rebuilding website files.

## Rebuild and verify

Run on an allocated CPU node in the existing `wan` environment, from the repo:

```bash
python scripts/prepare_text4d_confidence.py \
  --source /n/lab_storage/ydu_lab/Lab/akiruga/text4d_indoor45/samples \
  --previous-provenance assets/text4d_indoor/provenance.json --workers 2
python scripts/test_text4d_confidence.py
node scripts/test-text4d-showcase.mjs
node scripts/test-text4d-geometry.mjs
```

The retained published provenance is a valid scale source for subsequent rebuilds.
Browser integration checks: `scripts/check_text4d_browser.mjs` (Playwright/Chromium,
using `UGG_PLAYWRIGHT_MODULE` and `PLAYWRIGHT_BROWSERS_PATH` from the local tools).
