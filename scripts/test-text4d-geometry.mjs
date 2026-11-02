import assert from "node:assert/strict";
import {firstFrameCamera, inverse3, unpackPointmaps, writePointmap} from "../text4d-geometry.js";

// Exercise skew, pixel centers, nontrivial rotations/translations, validity,
// and backwards seeks into a single reused buffer. Expected values are manual.
const info = {frame_count:2, grid_width:2, grid_height:1, stride:3,
  intrinsics: [[[2,1,0.5],[0,2,0.5],[0,0,1]], [[2,1,0.5],[0,2,0.5],[0,0,1]]],
  c2w: [[[0,-1,0,4],[1,0,0,5],[0,0,1,6],[0,0,0,1]], [[1,0,0,10],[0,1,0,20],[0,0,1,30],[0,0,0,1]]]};
const bytes = new ArrayBuffer(4*7);
new Float32Array(bytes,0,4).set([2,0,4,6]);
new Uint8Array(bytes,16,12).set([255,0,0, 0,0,0, 0,255,0, 0,0,255]);
const data = unpackPointmaps(bytes, info), positions = new Float32Array(6), colors = new Float32Array(6);
assert.equal(writePointmap(info,data,0,positions,colors),1);
assert.deepEqual([...positions.slice(0,3)],[4,5,8]);
assert.deepEqual([...colors.slice(0,3)],[1,0,0]);
assert.equal(writePointmap(info,data,1,positions,colors),2);
assert.deepEqual([...positions],[10,20,34,19,20,36]);
assert.deepEqual([...colors],[0,1,0,0,0,1]);
assert.equal(writePointmap(info,data,1,positions,colors,4),1,"remove only depth above the fixed cutoff");
assert.deepEqual([...positions.slice(0,3)],[10,20,34],"retained point keeps the original pose and position");
assert.deepEqual([...colors.slice(0,3)],[0,1,0],"retained point keeps its original color");
assert.equal(writePointmap(info,data,1,positions,colors,Infinity),2,"unfiltered comparison restores the full frame");
assert.equal(writePointmap(info,data,0,positions,colors),1,"rewind restores one current frame rather than accumulating");
assert.deepEqual([...positions.slice(0,3)],[4,5,8]);
assert.throws(()=>unpackPointmaps(new ArrayBuffer(1),info),/size/);
assert.throws(()=>writePointmap(info,data,2,positions,colors),/frame/);
assert.throws(()=>inverse3([[0,0,0],[0,0,0],[0,0,0]]),/intrinsics/);
const viewInfo = {grid_width:4,grid_height:1,width:4,height:2,
  c2w:[[[0,0,1,10],[1,0,0,20],[0,1,0,30],[0,0,0,1]]],
  intrinsics:[[[2,0,2],[0,2,1],[0,0,1]]]};
const viewDepth = new Float32Array([2,4,6,8,999]);
const view = firstFrameCamera(viewInfo,{depth:viewDepth});
assert.deepEqual(view.position,[8,20,30]);
assert.deepEqual(view.look_at,[15,20,30]);
assert.deepEqual(view.up.map(v=>v||0),[0,0,-1]);
assert.equal(view.median_depth,5);
assert.equal(view.fov,2*Math.atan(0.5));
assert.equal(view.horizontal_fov,Math.PI/2);
assert.deepEqual([...viewDepth],[2,4,6,8,999],"first-camera framing never mutates depth payloads");
assert.throws(()=>firstFrameCamera(viewInfo,{depth:new Float32Array([NaN,0,-1,Infinity])}),/no valid/);
console.log("PASS: unprojection, RGB, buffer reuse and first-frame camera axes/median/setback/FOV with unchanged source");
