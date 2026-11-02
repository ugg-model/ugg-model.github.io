# UGG paper website

Live page: [https://sky-lzy.github.io/UGG-website/](https://sky-lzy.github.io/UGG-website/)

Static website for **UGG: Unified Generative Geometry Model — NeurIPS 2026**.
Results appear in five independent galleries: 3D Reconstruction, Novel View
Synthesis, Depth Prediction, Camera Prediction, and Text-to-4D Generation.
An interactive input → UGG → output overview highlights each task's modalities
and animates its routes before a separate link opens its examples. It covers two
further conditioning modes that have no gallery of their own, Depth-to-Video and
Camera-to-Video, whose Explore link is hidden. The picker advances on its own
every 2.5 s, pausing on hover, focus and offscreen, and stops for good once a
task is chosen. Keyboard task selection and reduced motion are supported; under
reduced motion it settles on the first task instead of cycling. The method explanations use three
responsive cards below the native HTML/CSS architecture diagram. Its labels,
token shapes, attention layers and timestep modulation are selectable HTML;
the small RGB/depth/ray-map previews are losslessly encoded images from slide 1
of the supplied PowerPoint. `assets/method/source.json` records source hashes.
The diagram is centered and uniformly 15% smaller on screens wider than 900px;
on narrower screens it keeps the full available width and the same arrangement.
To regenerate these previews in the existing `wan` environment on a CPU
allocation, run `python scripts/extract_method_media.py /path/to/source.pptx`.
The extraction checks exact decoded RGB equality after lossless encoding.

Both point-cloud galleries start with closer framing. Reconstruction camera
distances are 65% of their previous values; Text-to-4D fits the current display
bounds at a closer distance and higher elevation. Orbit, zoom and reset remain
available, and point coordinates and colors are unchanged.

## GitHub Pages

Publish `main` from **/(root)** in Settings → Pages → Deploy from a branch.
The root `index.html` is the homepage; `.nojekyll` avoids Jekyll processing.
No build or server is required for the published site. After **every push**, wait
for the Pages deployment, verify that the new HTML and manifest are live, and run
the browser check against the public URL. A successful push is not publication.
All assets, modules, and media use relative paths under `/UGG-website/`.

## Release results and display

The source for the expanded galleries is `release-oracle-chosen`. The inspected
release has 456 NVS case folders, 80 depth folders, and 66 pose folders. The gallery
imports up to 72 cases per task: 72 NVS candidates, 72 depth candidates, and all 66 camera cases. Import
ranks cases within each dataset, selects before preparing media, and records
included/excluded cases and the selection policy. Source files remain unchanged.

The **published** NVS, depth and camera galleries use the final user export
`UGG_selections_1791910567753.json` (exported 2026-10-13T16:56:07.753Z).
`assets/published-selection.json` records its SHA-256 and exact ordered selected
IDs without publishing personal review notes or review-status flags. These IDs
supersede earlier first-pass recommendations, provisional alternatives and
exclusion lists, including cases the user explicitly selected again.

- NVS: 24 — RealEstate10K 128-scenes 10, RealEstate10K 50-frames 7,
  DL3DV 6, Spatial Video 1; default sample_00064 in the 128-scenes group.
  All use two conditioning frames (ncf2), recorded in the selection metadata.
- Depth: 24 — ScanNet++ 14, Bonn 3, KITTI 5, Sintel 2;
  default ScanNet++ scene_44.
- Camera: 24 — ScanNet++ 21, Sintel 2, Bonn 1;
  default ScanNet++ scene_3.

The three `assets/*-showcase.mjs` modules apply these ordered allowlists **before**
creating thumbnails, viewers or pagination. Each gallery contains exactly 24 cases with no pagination. Keyboard navigation cannot
expose unselected cases. Missing/duplicate IDs (or an NVS conditioning-protocol
mismatch) fail validation rather than substituting an unapproved case.

The original `examples.json` still archives 72 NVS, 72 depth and 66 camera candidates.
The NVS import was PSNR-ranked within six dataset groups; the depth import was
AbsRel-ranked, retaining Bonn 5, KITTI 13, Sintel 14 and ScanNet++ 40. All candidate
objects, videos, depth renders, supplied NVS cameras, predicted/reference poses and
oracle provenance are unchanged. No pose correction, video re-encoding or
benchmark recomputation is part of applying a selection.

The independent `/review/` workspace and its browser-local saved selections remain
unchanged. Its earlier presets are review aids, not the official publication source.
This publication does not apply browser-local changes automatically.

Selection is independent across tasks. Tied import scores use case IDs for
consistent ordering. NVS, depth and camera each occupy one page of 24 visually
selected cases, with no pagination controls. These are curated showcase clips,
not a sample representing average benchmark quality. Benchmark tables/charts
are unchanged.

NVS/depth/camera have no dataset selectors or selection captions. NVS/depth
sample headings show only the dataset name, without release/pool details.
Reconstruction omits interaction instructions and AbsRel; NVS/camera omit their
instruction captions. Camera trajectory-video and Text-to-4D RGB-video links are
not displayed. Source metadata, media and playback controls are unchanged.
Each gallery retains up to three case viewers, releasing older video/WebGL
resources. Visible NVS, depth, and camera results autoplay with audio muted and loop;
manual pauses persist while a case remains cached. Offscreen/inactive galleries
and hidden browser tabs pause. Reduced-motion preferences disable initial autoplay,
while Play controls remain available.

NVS, depth and camera play at 10 displayed frames per second at the default 1×
speed: a 50-frame clip lasts five seconds, while shorter clips finish sooner.
Each viewer offers 0.5×, 1×, 2×, 4× and 8×. Speed changes preserve the current
frame and pause state; cached cases retain their selected speed. Playback rates
are normalized against the original encoded FPS, which remains the source for
frame seeking and synchronized RGB/pose lookup. No videos are re-encoded.

The 3D reconstruction viewers also show matching RGB in the upper-right.
Their 50-frame, 10 FPS Viser timeline drives the RGB inset, including pause,
scrubbing, looping and speed changes. A decoded image sprite avoids a second
video clock. The sprite is built from the same GT RGB array that colours the
cloud, so the inset cannot drift from the geometry.
`assets/viser/reconstruction-rgb-provenance.json` is the earlier check of the
three original exports: all 150 recorded point/color frame pairs matched, and
projecting their points into the RGB images verified the frame correspondence.

Reconstruction shows only the current pointmap, with its original RGB colors.
The gallery holds 12 scenes across ScanNet++, 7-Scenes, KITTI and Bonn, each the
best-AbsRel scene of its benchmark in the frozen release-model oracle that a
review of the rendered cloud also passed; `tools/RECONSTRUCTION_PIPELINE.md`
documents how they are chosen and built, and `tools/reconstruction_rejects.json`
records what was rejected on sight and why. Each scene is a `.viser` recording
played by the shared client in `viser/viser-client/`, which must stay on the
same viser version that wrote the recordings — an older client cannot read them
at all. The three scenes the site shipped before are kept, in front and
unchanged in content.
The RGB-only inset continues to follow the native player.

Both point-cloud sections open slightly behind their first-frame camera, with
the same forward direction and roll. The setback is 40% of the first frame's
median positive depth; calibrated field of view is fitted to the viewport.
Reconstruction stores these defaults in `initial_camera` metadata. Text-to-4D
derives them from its first pose and retained depth buffer, without modifying
pointmaps. Its existing frame-center following remains active; Reset view uses
the first-camera orientation and offset translated with that center.

Text-to-4D publishes 24 selected indoor scenes, labelled Scene 01–24, after
Camera Prediction. The exact previous website choices and original sample mapping
are in `assets/text4d-showcase.mjs`; former Scene 22 is indoor sample_000 (kitchen
and dining space). Only the selected scene assets remain in the repo.

Point clouds use the original `depth_vae_depth.npy` export (mean of three signed-
disparity channels), the existing per-clip depth/pose scale, and the highest-
confidence 95% of valid points **in each frame**, ranked by `depth_vae_conf.npy`.
Equal scores use row-major pixel order. The old edge mask, percentile disparity
floor and far-depth filter are removed. Original RGB colors, intrinsics and camera
poses are retained. Only current-frame points are drawn; the observer follows the
frame center while retaining the first-camera viewing direction by default.

The Preview selector beside Speed and Reset view switches the upper-right inset
between RGB (default), the supplied colormapped depth rendering, and camera pose.
One 10 FPS clock drives all modalities, with pause, stepping, seeking and
0.5×/1×/2×/4×/8× playback. Hidden galleries pause; at most three panels are cached.
Payloads use `DecompressionStream("gzip")` to decode float32 depths followed by
exact RGB bytes; rejected points have zero depth. Source collections are unchanged.
See [the indoor protocol](assets/text4d_indoor/README.md) for source hashes,
per-frame retained counts, relative-scale limitations and rebuild instructions.

Run the focused checks on an allocated CPU node in the existing `wan` environment:

```bash
python scripts/test_text4d_confidence.py
node scripts/test-text4d-showcase.mjs
node scripts/test-text4d-geometry.mjs
```

NVS shows generated/reference RGB side by side in one view. A small interactive
3D overlay in the upper-right shows the target-camera trajectory, with the current
camera driven by the same decoded video frame. These are supplied target cameras,
not estimated NVS cameras. Camera arrays are read beside the original release RGB
symlink targets when `--use-original-nvs-poses` is enabled.

Depth shows the supplied predicted/reference renders side by side. Matching RGB
is packed as a third region of the same decoded video frame and drawn as a small
overlay in the **upper-right**. Depth and camera thumbnails show RGB only; an explicit
RGB-unavailable placeholder is used when input cannot be verified. Missing ScanNet++
RGB can be recovered with `--scannet-rgb-root`: every source camera rotation and
normalized center must match the release GT sequence, and frame counts must agree.
For depth, recovered RGB is retimed by frame index to the supplied depth playback
rate without dropping/repeating source frames. Camera playback uses the RGB rate.
The release renders and raw source files remain unchanged.

Camera prediction retains two linked interactive views of frame positions and
orientations and an upper-right RGB overlay. A single global Sim(3) aligns predicted
centers to GT; the same
rotation applies to every predicted orientation. Stationary predictions use only
a global translation, with that limitation disclosed. Frusta are fixed-size
orientation glyphs, not calibrated intrinsics. RGB is optional; a supplied
trajectory video provides the timeline for cases without RGB. The original
trajectory video is also linked for each available camera case. If arrays cannot
be paired with a video timeline, the available video views remain accessible.

**These results are ground-truth oracle-selected within a single release
checkpoint.** The manifest and exported provenance retain this information;
viewer boxes omit the selection/source annotations. No new benchmark or ordinary
test-time selection claim is made. The source reports verified contiguous GT frame windows;
import checks media timelines and camera arrays. The method figure is rendered
from the original PowerPoint in HTML/CSS. The earlier PDF/PNG assets are retained
as source references and are no longer displayed.

```text
index.html                 Paper text, sections and method figure
styles.css                 Responsive light/dark layout
results-flow.js             Interactive task conditioning/output diagram
app.js                     Filters, paged thumbnails, playback and citation copy
sync-viewers.js             Shared RGB/depth and camera timelines
camera-viewer.js            Linked 3D camera views with resource cleanup
examples.json              Imported candidate cases and available views
assets/depth-showcase.mjs   Final 24 depth IDs, display order and selection caption
assets/camera-showcase.mjs  Final 24 camera IDs and display order
assets/nvs-showcase.mjs     Final 24 NVS IDs, display order and ncf2 caption
assets/release/             Deduplicated videos/posters/poses and provenance
assets/method2.pdf          Original supplied method figure
assets/method2.png          Browser display of the original figure
vendor/                    Vendored Three.js, OrbitControls and MIT license
scripts/                   Preview, import and QA commands
```

## Preparation and validation

On this Slurm cluster, use a **task-specific, verified CPU allocation** and
`conda activate wan`. Login nodes are only for lightweight inspection, editing,
and scheduler commands. Keep output, caches, and browser dependencies local to
the active worktree; reuse existing browser tools where available.

```bash
export UGG_RUN_DIR="$PWD/outputs/curated-results"
export MPLCONFIGDIR="$UGG_RUN_DIR/matplotlib"
mkdir -p "$UGG_RUN_DIR"
python scripts/prepare_release_assets.py \
  --source /path/to/release-oracle-chosen \
  --run-dir "$UGG_RUN_DIR" --workers 2 --max-cases 72 \
  --use-original-nvs-poses \
  --scannet-rgb-root /path/to/original/evaluation/depthpose/scannetpp \
  --prune-unused
pdftoppm -cropbox -singlefile -r 300 -png assets/method2.pdf assets/method2
node --check app.js
node scripts/test-published-selection.mjs
node scripts/test-depth-showcase.mjs
node scripts/test-camera-showcase.mjs
node scripts/test-nvs-showcase.mjs
node --check sync-viewers.js
node --check camera-viewer.js
node scripts/test-benchmarks.mjs
node scripts/test-benchmark-highlights.mjs
python -m py_compile scripts/prepare_release_assets.py scripts/serve.py
python scripts/test_gallery_selection.py
python scripts/check_release_assets.py --run-dir "$UGG_RUN_DIR" --decode
python scripts/serve.py --port 8080 --base-path /UGG-website/
# Run browser QA in another step of the same allocation:
node scripts/check_browser.mjs \
  --base-url http://127.0.0.1:8080/UGG-website/ \
  --run-dir "$UGG_RUN_DIR/local-browser"
# After the published HTML/manifest match the intended revision:
node scripts/check_browser.mjs \
  --base-url https://sky-lzy.github.io/UGG-website/ \
  --run-dir "$UGG_RUN_DIR/public-browser"
```

Set `UGG_PLAYWRIGHT_MODULE` to an existing Playwright `index.mjs`, and
`PLAYWRIGHT_BROWSERS_PATH` to its existing Chromium cache. Browser tools can be
installed in an ignored task-local directory when unavailable. Chromium QA uses
SwiftShader software WebGL; no GPU is required.

Asset QA verifies every manifest reference and optionally fully decodes all MP4s.
Browser QA samples the first/last cases of every dataset/protocol group, verifies
all their views, autoplay/manual pause/offscreen behavior, RGB/depth frame matching,
camera matrices and linked orbit, NVS target-camera synchronization,
the one-page NVS/depth/camera selections,
all 24 camera and all 24 NVS viewers and exact IDs/order through dataset filters/reset,
filters/pagination/keyboard access, the method
figure, and layouts at 375/768/1440 pixels. This does not substitute for human
review of scientific examples. Read the task worklog for actual execution evidence
and unverified browsers; Safari/iOS/Firefox require separate review.

The benchmark charts and tables added on main are preserved. The teaser, 4D media,
arXiv/code links, and final citation details remain provisional and are outside this update.
