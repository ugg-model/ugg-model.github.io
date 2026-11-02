// Run with: node scripts/test-benchmarks.mjs (no npm dependencies).
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
const context = { window: {} };
vm.runInNewContext(fs.readFileSync(new URL('../assets/benchmarks/data.js', import.meta.url), 'utf8'), context);
const data = context.window.UGG_BENCHMARKS;
const task = key => data.tasks.find(item => item.key === key);
const setting = (key, mode) => task(key).settings.find(item => item.key === mode);
const row = (key, mode, method) => setting(key, mode).rows.find(item => item.method === method).values;
const totals = {};
for (const t of data.tasks) {
  totals[t.key] = 0;
  assert.equal(new Set(t.settings.map(s => s.key)).size, t.settings.length);
  for (const s of t.settings) {
    assert.equal(new Set(s.rows.map(r => r.method)).size, s.rows.length);
    for (const m of s.metrics) assert(['up', 'down'].includes(m.direction));
    for (const r of s.rows) {
      assert(data.methods[r.method], r.method);
      assert.equal(r.values.length, s.datasets.length * s.metrics.length);
      r.values.forEach((v, i) => {
        assert(Number.isFinite(v) && v >= 0);
        const m = s.metrics[i % s.metrics.length];
        assert.equal(Number(v.toFixed(m.digits)), v, 'Manuscript precision must not be rounded away');
        if (['delta', 'ssim', 'lpips'].includes(m.key)) assert(v <= 1);
      });
      totals[t.key] += r.values.length;
    }
    if (s.blocks) {
      const ids = s.blocks.flat();
      assert.equal(new Set(ids).size, ids.length);
      assert.equal(ids.length, s.rows.length);
    }
  }
}
assert.deepEqual(totals, { generation: 54, pose: 100, depth: 160, ablations: 64 });
assert.equal(Object.values(totals).reduce((a, b) => a + b, 0), data.source.valueCount);
assert.equal(row('generation', 'two-view', 'ugg')[0], 25.73);
assert.equal(row('generation', 'one-view', 'ugg')[0], 21.79);
assert(row('generation', 'two-view', 'seva')[6] > row('generation', 'two-view', 'ugg')[6]);
assert.deepEqual(Array.from(setting('pose', 'sparse').metrics, m => m.key), ['tae', 'rper']);
assert.equal(row('pose', 'sparse', 'ugg')[0], 4.287);
assert(row('pose', 'dense', 'gen3r')[8] < row('pose', 'dense', 'ugg')[8]);
assert.equal(row('depth', 'dense', 'ugg')[3], 0.883);
assert(row('depth', 'dense', 'tts')[8] > row('depth', 'dense', 'ugg')[8]);
assert.equal(row('depth', 'sparse', 'oracle')[6], 0.183);
assert.equal(data.methods.oracle.kind, 'oracle');
assert.equal(setting('ablations', 'pose').blocks.length, 2);
assert.equal(setting('ablations', 'guidance').metrics[0].digits, 4);
console.log('PASS: all 378 values, 10 settings, metric directions, precision and scientific-display regressions.');
