// Run with: node scripts/test-nvs-showcase.mjs
import assert from "node:assert/strict";
import {readFileSync, existsSync} from "node:fs";
import {NVS_SHOWCASE_IDS, applyNvsShowcase} from "../assets/nvs-showcase.mjs";
import {applyDepthShowcase} from "../assets/depth-showcase.mjs";
import {applyCameraShowcase} from "../assets/camera-showcase.mjs";

// Independent copy of the approved review export, not derived from the module.
const approved = `re10k128_50f__ncf2-sample_00064
re10k128_50f__ncf2-sample_00097
re10k_c50__ncf2-sample_00008
re10k_c50__ncf2-sample_00004
re10k128_50f__ncf2-sample_00063
re10k128_50f__ncf2-sample_00054
dl3dv20__ncf2-sample_00000
dl3dv20__ncf2-sample_00012
re10k_c50__ncf2-sample_00006
re10k128_50f__ncf2-sample_00100
dl3dv20__ncf2-sample_00009
dl3dv20__ncf2-sample_00007
re10k_c50__ncf2-sample_00000
re10k128_50f__ncf2-sample_00118
re10k128_50f__ncf2-sample_00018
re10k_c50__ncf2-sample_00002
re10k128_50f__ncf2-sample_00025
re10k128_50f__ncf2-sample_00076
re10k_c50__ncf2-sample_00005
re10k128_50f__ncf2-sample_00113
re10k_c50__ncf2-sample_00007
dl3dv20__ncf2-sample_00006
dl3dv20__ncf2-sample_00018
spatialvid__ncf2-sample_00007`.split("\n");
const root = new URL("../", import.meta.url);
const source = JSON.parse(readFileSync(new URL("examples.json", root), "utf8"));
const original = JSON.stringify(source);
const selected = applyNvsShowcase(source);
assert.deepEqual(NVS_SHOWCASE_IDS, approved);
assert.equal(NVS_SHOWCASE_IDS.length, 24);
assert.equal(new Set(NVS_SHOWCASE_IDS).size, 24);
assert.equal(Object.isFrozen(NVS_SHOWCASE_IDS), true);
assert.deepEqual(selected.nvs.cases.map(example => example.id), approved);
assert.deepEqual(selected.nvs.selection.dataset_quotas, {re10k128_50f:10, re10k_c50:7, dl3dv20:6, spatialvid:1});
assert.equal(selected.nvs.selection.selected, 24);
assert.equal(selected.nvs.selection.limit, 24);
assert.equal(selected.nvs.selection.conditioning_frames, 2);
assert.equal(selected.nvs.selection.page_datasets.length, 1);
assert.equal(selected.nvs.selection.page_size, 24);
assert.match(selected.nvs.selection.caption, /2 conditioning frames/);
assert.equal(selected.nvs.cases[0].id, "re10k128_50f__ncf2-sample_00064");
assert.deepEqual(applyNvsShowcase(selected), selected, "Curation is idempotent");
for (const task of Object.keys(source).filter(task => task !== "nvs")) {
  assert.equal(selected[task], source[task], "Other galleries remain untouched: " + task);
}
for (const example of selected.nvs.cases) {
  assert.equal(example, source.nvs.cases.find(item => item.id === example.id));
  assert.equal(example.protocol, "ncf2");
  assert.equal(example.task, "nvs");
  assert.match(example.note, /Oracle-selected/);
  for (const asset of [example.thumbnail, example.clock_video, example.poses,
      ...Object.values(example.views || {}).flatMap(view => [view.src, view.poster])].filter(Boolean)) {
    assert.ok(existsSync(new URL(asset, root)), "Missing referenced asset: " + asset);
  }
  const poses = JSON.parse(readFileSync(new URL(example.poses, root), "utf8"));
  assert.equal(poses.frame_count, example.frame_count);
  assert.equal(poses.reference.length, example.frame_count);
  assert.equal(poses.fps, example.fps);
  assert.equal(poses.prediction, undefined, "NVS cameras are supplied targets, not predicted poses");
}
assert.equal(new Set(selected.nvs.cases.map(example => example.source)).size, 24);
const reversed = {...source, nvs:{...source.nvs, cases:[...source.nvs.cases].reverse()}};
assert.deepEqual(applyNvsShowcase(reversed).nvs.cases, selected.nvs.cases);
const extra = {...source, nvs:{...source.nvs, cases:[...source.nvs.cases, {id:"unreviewed-new-case",dataset:"mip",protocol:"ncf1"}]}};
assert.deepEqual(applyNvsShowcase(extra).nvs.cases, selected.nvs.cases, "Re-imports cannot add unreviewed cases");
const missing = {...source, nvs:{...source.nvs, cases:source.nvs.cases.filter(item => item.id !== approved[0])}};
assert.throws(() => applyNvsShowcase(missing), /Approved NVS showcase cases missing/);
const duplicate = {...source, nvs:{...source.nvs, cases:[...source.nvs.cases, source.nvs.cases[0]]}};
assert.throws(() => applyNvsShowcase(duplicate), /Duplicate case IDs/);
assert.throws(() => applyNvsShowcase({}), /requires an imported NVS case list/);
const badProtocol = {...source, nvs:{...source.nvs, cases:source.nvs.cases.map(example =>
  example.id === approved[0] ? {...example, protocol:"ncf1"} : example)}};
assert.throws(() => applyNvsShowcase(badProtocol), /require two conditioning frames/);
const depthCamera = applyCameraShowcase(applyDepthShowcase(source));
const combined = applyNvsShowcase(depthCamera);
assert.equal(combined.depth, depthCamera.depth);
assert.equal(combined.camera, depthCamera.camera);
assert.deepEqual(applyCameraShowcase(applyDepthShowcase(selected)), combined, "Task selections commute");
for (const task of ["depth", "camera", "nvs"]) assert.equal(combined[task].cases.length, 24);
assert.equal(JSON.stringify(source), original, "Do not mutate the imported manifest or case objects");
const app = readFileSync(new URL("app.js", root), "utf8");
const selectionIndex = app.indexOf("examples = applyNvsShowcase(examples);");
assert.ok(selectionIndex >= 0 && selectionIndex < app.indexOf('document.querySelectorAll("[data-result-task]")'), "Select before creating filters, viewers or pagination");
assert.match(app, /await import\("\.\/assets\/nvs-showcase\.mjs"\)/);
console.log("NVS showcase passed: exact 24 IDs/order, 10/7/6/1 datasets, ncf2 only, original video/target cameras intact, other selections unchanged, missing/duplicate/protocol mismatches rejected.");
