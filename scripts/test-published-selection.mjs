// Run: node scripts/test-published-selection.mjs [original-review-export.json]
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {createHash} from 'node:crypto';
import {DEPTH_SHOWCASE_IDS, applyDepthShowcase} from '../assets/depth-showcase.mjs';
import {CAMERA_SHOWCASE_IDS, applyCameraShowcase} from '../assets/camera-showcase.mjs';
import {NVS_SHOWCASE_IDS, applyNvsShowcase} from '../assets/nvs-showcase.mjs';
const root = new URL('../', import.meta.url);
const read = path => JSON.parse(readFileSync(new URL(path, root), 'utf8'));
const record = read('assets/published-selection.json');
const source = read('examples.json');
const untouched = JSON.stringify(source);
const modules = {nvs:NVS_SHOWCASE_IDS, depth:DEPTH_SHOWCASE_IDS, camera:CAMERA_SHOWCASE_IDS};
const expectedCounts = {nvs:{re10k128_50f:10,re10k_c50:7,dl3dv20:6,spatialvid:1}, depth:{scannetpp:14,bonn:3,sintel:2,kitti:5}, camera:{scannetpp:21,sintel:2,bonn:1}};
const apply = input => applyNvsShowcase(applyCameraShowcase(applyDepthShowcase(input)));
const displayed = apply(source);
assert.equal(record.schema, 'ugg-showcase/v1');
assert.equal(record.source_export_sha256, '41e48de4f2353289b8fda24ccc060a6e6ca0bfc79cb97854caaf67cf19847e5c');
for (const task of ['nvs','depth','camera']) {
  const approved = record.tasks[task].selected;
  const gallery = displayed[task];
  assert.equal(approved.length,24);
  assert.equal(new Set(approved).size,24);
  assert.deepEqual(modules[task],approved,task+': module matches the saved user-export order');
  assert.deepEqual(gallery.cases.map(c=>c.id),approved,task+': no removed cases in rendered input');
  assert.deepEqual(gallery.selection.dataset_quotas,expectedCounts[task]);
  assert.deepEqual(record.tasks[task].dataset_counts,expectedCounts[task]);
  assert.equal(record.tasks[task].candidate_count,source[task].cases.length);
  assert.equal(gallery.selection.method,'user_review_selection');
  assert.equal(gallery.selection.source_export_sha256,record.source_export_sha256);
  assert.equal(gallery.selection.exported_at,record.exported_at);
  assert.equal(gallery.selection.limit,24);
  assert.equal(gallery.selection.page_datasets.length,1);
  assert.equal(gallery.cases[0].id,approved[0]);
  for (const dataset of Object.keys(expectedCounts[task])) {
    assert.deepEqual(gallery.cases.filter(c=>c.dataset===dataset).map(c=>c.id),
      approved.filter(id=>source[task].cases.find(c=>c.id===id).dataset===dataset));
  }
  for (const c of gallery.cases) assert.equal(c,source[task].cases.find(s=>s.id===c.id),'Preserve media, source data and oracle provenance');
  assert.equal('records' in record.tasks[task],false,'Do not publish personal notes or reviewed flags');
}
// A fresh review export supersedes old "excluded/provisional" recommendations.
for (const id of ['scannetpp-scene_10','scannetpp-scene_45','scannetpp-scene_12','scannetpp-scene_19','bonn-rgbd_bonn_balloon2']) {
  assert.ok(displayed.camera.cases.some(c=>c.id===id),'Reselected camera case must remain: '+id);
}
for (const task of Object.keys(source).filter(t=>!modules[t])) assert.equal(displayed[task],source[task],task+': unchanged');
assert.equal(JSON.stringify(source),untouched);
assert.deepEqual(apply(displayed),displayed,'Selections remain idempotent');
// Optional byte-for-byte provenance check against the original private upload.
if (process.argv[2]) {
  const bytes=readFileSync(process.argv[2]);
  assert.equal(createHash('sha256').update(bytes).digest('hex'),record.source_export_sha256);
  const original=JSON.parse(bytes.toString('utf8'));
  for (const task of Object.keys(modules)) assert.deepEqual(record.tasks[task].selected,original.tasks[task].selected);
  console.log('Original uploaded export verified: SHA-256 and all 72 ordered selections match.');
}
console.log('Published selection passed: NVS/depth/camera 24 each, exact final order, dataset counts, reselected cases, unchanged media and other tasks.');
