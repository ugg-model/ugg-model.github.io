// Run with: node scripts/test-depth-showcase.mjs
import assert from "node:assert/strict";
import {readFileSync, existsSync} from "node:fs";
import {DEPTH_SHOWCASE_IDS, applyDepthShowcase} from "../assets/depth-showcase.mjs";

const root = new URL("../", import.meta.url);
const source = JSON.parse(readFileSync(new URL("examples.json", root), "utf8"));
const original = JSON.stringify(source);
const selected = applyDepthShowcase(source);

assert.equal(DEPTH_SHOWCASE_IDS.length, 24);
assert.equal(new Set(DEPTH_SHOWCASE_IDS).size, 24);
assert.equal(Object.isFrozen(DEPTH_SHOWCASE_IDS), true);
assert.deepEqual(selected.depth.cases.map(example => example.id), DEPTH_SHOWCASE_IDS);
assert.deepEqual(selected.depth.selection.dataset_quotas, {scannetpp:14, bonn:3, sintel:2, kitti:5});
assert.equal(selected.depth.selection.selected, 24);
assert.equal(selected.depth.selection.page_datasets.length, 1);
assert.equal(selected.depth.selection.page_size, 24);
assert.match(selected.depth.selection.caption, /^24 selected depth/);
assert.equal(selected.depth.cases[0].id, "scannetpp-scene_44");
assert.equal(JSON.stringify(source), original, "Do not mutate the imported manifest");
assert.deepEqual(applyDepthShowcase(selected), selected, "Applying curation twice is harmless");
for (const task of Object.keys(source).filter(task => task !== "depth")) {
  assert.equal(selected[task], source[task], "Other galleries must be untouched: " + task);
}
for (const example of selected.depth.cases) {
  assert.equal(example, source.depth.cases.find(item => item.id === example.id));
  assert.match(example.note, /Oracle-selected/);
  for (const asset of [example.thumbnail, example.clock_video, example.input_rgb,
      ...Object.values(example.views || {}).flatMap(view => [view.src, view.poster])].filter(Boolean)) {
    assert.ok(existsSync(new URL(asset, root)), "Missing referenced asset: " + asset);
  }
}
const reversed = {...source, depth:{...source.depth, cases:[...source.depth.cases].reverse()}};
assert.deepEqual(applyDepthShowcase(reversed).depth.cases, selected.depth.cases, "Order must not depend on import rank");
const missing = {...source, depth:{...source.depth, cases:source.depth.cases.filter(item => item.id !== DEPTH_SHOWCASE_IDS[0])}};
assert.throws(() => applyDepthShowcase(missing), /Approved depth showcase cases missing/);
const duplicate = {...source, depth:{...source.depth, cases:[...source.depth.cases, source.depth.cases[0]]}};
assert.throws(() => applyDepthShowcase(duplicate), /Duplicate case IDs/);
assert.throws(() => applyDepthShowcase({}), /requires an imported depth case list/);
console.log("Depth showcase checks passed: exact 24 IDs/order, 14/3/5/2 coverage, original cases/media and other tasks preserved, missing/duplicate IDs rejected.");
