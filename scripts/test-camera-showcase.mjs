// Run with: node scripts/test-camera-showcase.mjs
import assert from "node:assert/strict";
import {readFileSync, existsSync} from "node:fs";
import {CAMERA_SHOWCASE_IDS, applyCameraShowcase} from "../assets/camera-showcase.mjs";
import {applyDepthShowcase} from "../assets/depth-showcase.mjs";

const approved = `scannetpp-scene_3
scannetpp-scene_42
scannetpp-scene_4
scannetpp-scene_32
sintel-temple_2
scannetpp-scene_46
scannetpp-scene_25
scannetpp-scene_6
scannetpp-scene_2
scannetpp-scene_37
scannetpp-scene_33
scannetpp-scene_11
scannetpp-scene_9
scannetpp-scene_17
scannetpp-scene_1
sintel-sleeping_2
scannetpp-scene_28
scannetpp-scene_24
scannetpp-scene_45
scannetpp-scene_10
scannetpp-scene_12
scannetpp-scene_22
scannetpp-scene_19
bonn-rgbd_bonn_balloon2`.split("\n");
// Latest user export is authoritative, including reselected scene_10 and balloon2.
const root = new URL("../", import.meta.url);
const source = JSON.parse(readFileSync(new URL("examples.json", root), "utf8"));
const original = JSON.stringify(source);
const selected = applyCameraShowcase(source);
assert.deepEqual(CAMERA_SHOWCASE_IDS, approved);
assert.equal(CAMERA_SHOWCASE_IDS.length, 24);
assert.equal(new Set(CAMERA_SHOWCASE_IDS).size, 24);
assert.equal(Object.isFrozen(CAMERA_SHOWCASE_IDS), true);
assert.deepEqual(selected.camera.cases.map(example => example.id), approved);
assert.deepEqual(selected.camera.selection.dataset_quotas, {scannetpp:21, sintel:2, bonn:1});
assert.equal(selected.camera.selection.selected, 24);
assert.equal(selected.camera.selection.page_datasets.length, 1);
assert.equal(selected.camera.selection.page_size, 24);
assert.equal(selected.camera.cases[0].id, "scannetpp-scene_3");
assert.ok(CAMERA_SHOWCASE_IDS.includes("scannetpp-scene_10"));
assert.ok(CAMERA_SHOWCASE_IDS.includes("bonn-rgbd_bonn_balloon2"));
assert.equal(JSON.stringify(source), original, "Do not mutate the imported manifest");
assert.deepEqual(applyCameraShowcase(selected), selected, "Curation is idempotent");
for (const task of Object.keys(source).filter(task => task !== "camera")) {
  assert.equal(selected[task], source[task], "Other galleries remain untouched: " + task);
}
for (const example of selected.camera.cases) {
  assert.equal(example, source.camera.cases.find(item => item.id === example.id));
  assert.match(example.note, /Oracle-selected/);
  for (const asset of [example.thumbnail, example.clock_video, example.poses,
      example.input_video, example.trajectory_video,
      ...Object.values(example.views || {}).flatMap(view => [view.src, view.poster])].filter(Boolean)) {
    assert.ok(existsSync(new URL(asset, root)), "Missing referenced asset: " + asset);
  }
  const poses = JSON.parse(readFileSync(new URL(example.poses, root), "utf8"));
  assert.equal(poses.prediction.length, example.frame_count);
  assert.equal(poses.reference.length, example.frame_count);
}
const reversed = {...source, camera:{...source.camera, cases:[...source.camera.cases].reverse()}};
assert.deepEqual(applyCameraShowcase(reversed).camera.cases, selected.camera.cases);
const extra = {...source, camera:{...source.camera, cases:[...source.camera.cases, {id:"unreviewed-new-case",dataset:"bonn"}]}};
assert.deepEqual(applyCameraShowcase(extra).camera.cases, selected.camera.cases, "Re-imports cannot add unreviewed display cases");
const missing = {...source, camera:{...source.camera, cases:source.camera.cases.filter(item => item.id !== approved[0])}};
assert.throws(() => applyCameraShowcase(missing), /Approved camera showcase cases missing/);
const duplicate = {...source, camera:{...source.camera, cases:[...source.camera.cases, source.camera.cases[0]]}};
assert.throws(() => applyCameraShowcase(duplicate), /Duplicate case IDs/);
assert.throws(() => applyCameraShowcase({}), /requires an imported camera case list/);
const depthOnly = applyDepthShowcase(source);
const combined = applyCameraShowcase(depthOnly);
assert.equal(combined.depth, depthOnly.depth, "The approved depth selection must be preserved");
assert.deepEqual(applyDepthShowcase(selected), combined, "Task selections commute");
assert.equal(combined.depth.cases.length, 24);
assert.equal(combined.camera.cases.length, 24);
assert.equal(combined.nvs.cases.length, 72);
assert.equal(JSON.stringify(source), original);
const app = readFileSync(new URL("app.js", root), "utf8");
const selectionIndex = app.indexOf("examples = applyCameraShowcase(applyDepthShowcase(examples));");
assert.ok(selectionIndex >= 0 && selectionIndex < app.indexOf('document.querySelectorAll("[data-result-task]")'), "Apply selection before building gallery controls");
assert.match(app, /await import\("\.\/assets\/camera-showcase\.mjs"\)/);
console.log("Camera showcase passed: exact 24 IDs/order, 21/2/1 datasets, latest export overrides prior exclusions, original poses/media intact, other galleries unchanged, missing/duplicate IDs rejected.");
