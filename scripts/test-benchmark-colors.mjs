// Run: node scripts/test-benchmark-colors.mjs (no npm dependencies).
// Keep each identity's color fixed across the entire benchmark section, not per tab.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
const read = path => fs.readFileSync(new URL(path, import.meta.url), 'utf8');
const nodes = new Map();
const node = selector => {
  if (!nodes.has(selector)) nodes.set(selector, {
    innerHTML: '', textContent: '', hidden: false, value: '', events: {},
    setAttribute() {}, addEventListener(name, handler) { this.events[name] = handler; }
  });
  return nodes.get(selector);
};
const errors = [];
const root = { querySelector: node, querySelectorAll: () => [] };
const context = {
  window: { matchMedia: () => ({matches: true}) },
  document: { getElementById: id => id === 'benchmarks' ? root : null },
  console: { error: (...args) => errors.push(args) }
};
vm.runInNewContext(read('../assets/benchmarks/data.js'), context);
const data = context.window.UGG_BENCHMARKS;
// Intentional palette revisions must update this explicit contract as well.
const expectedColors = {
  "aether": "#e47739",
  "seva": "#bd4147",
  "geo4d": "#20996d",
  "gen3r": "#cf9a21",
  "chrono": "#ce789f",
  "marigold": "#8b909a",
  "ugg": "#377bd4",
  "tts": "#8d68c8",
  "oracle": "#5f3c83",
  "full": "#244c80",
  "no-rgb": "#944827",
  "no-re10k": "#6c7a24",
  "single": "#199dab",
  "no-depth": "#a53d79",
  "dense-rays": "#967c55",
  "global-camera": "#54505e",
  "no-pose": "#d04d20",
  "w0": "#eead83",
  "w1": "#83ba95",
  "w2": "#75a5df",
  "w4": "#b6a0cd"
};
const seen = new Map();
for (const [id, method] of Object.entries(data.methods)) {
  assert.match(method.color, /^#[0-9a-f]{6}$/i, `${id}: use an opaque RGB hex color`);
  const color = method.color.toLowerCase();
  assert(!seen.has(color), `${id} reuses ${color} from ${seen.get(color)}`);
  seen.set(color, id);
}
assert.deepEqual(Object.fromEntries(Object.entries(data.methods).map(([id, m]) => [id, m.color])), expectedColors);
const snapshot = JSON.stringify(data);
vm.runInNewContext(read('../assets/benchmarks/benchmarks.js'), context);
assert.deepEqual(errors, []);
assert.equal(node('#bm-app').hidden, false);
const click = (selector, key, value) => node(selector).events.click({
  target: { closest: () => ({dataset: {[key]: String(value)}}) }
});
const filter = value => node('#bm-dataset').events.change({target: {value}});
const oracle = checked => node('#bm-oracle').events.change({target: {checked}});
const matches = (text, re) => Array.from(text.matchAll(re));
const escape = s => String(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const observed = new Map();
let states = 0;
for (const [ti, task] of data.tasks.entries()) {
  click('#bm-tabs', 'task', ti);
  for (const [si, setting] of task.settings.entries()) {
    click('#bm-modes', 'mode', si);
    for (const showOracle of task.key === 'depth' ? [false, true] : [false]) {
      oracle(showOracle);
      for (const dataset of ['all', ...setting.datasets]) {
        filter(dataset);
        const rows = setting.rows.filter(r => showOracle || data.methods[r.method].kind !== 'oracle');
        const legend = matches(node('#bm-legend').innerHTML,
          /<span class="bm-legend-item [^"]*" style="--bm-color:([^"]+)"><i[^>]*><\/i>([^<]*)<\/span>/g);
        assert.equal(legend.length, rows.length);
        rows.forEach((row, ri) => {
          const m = data.methods[row.method];
          assert.equal(legend[ri][1], expectedColors[row.method]);
          assert.equal(legend[ri][2], escape(m.label) + (m.kind === 'oracle' ? ' †' : ''));
        });
        const charts = matches(node('#bm-charts').innerHTML, /<svg\b[^>]*>([\s\S]*?)<\/svg>/g);
        const indices = setting.datasets.flatMap((name, di) => dataset === 'all' || dataset === name ? [di] : []);
        assert.equal(charts.length, indices.length * setting.metrics.length);
        charts.forEach(([, svg], ci) => {
          const bars = matches(svg, /<g class="([^"]+)" style="--bm-color:([^"]+)"[^>]*data-method="([^"]+)"[^>]*data-value="([^"]+)"[\s\S]*?<text[^>]*>([^<]*)<\/text><\/g>/g);
          assert.equal(bars.length, rows.length);
          const mi = ci % setting.metrics.length;
          const column = indices[Math.floor(ci / setting.metrics.length)] * setting.metrics.length + mi;
          const metric = setting.metrics[mi];
          bars.forEach(([, classes, color, id, value, label], ri) => {
            const row = rows[ri];
            assert.equal(id, row.method);
            assert.equal(color, expectedColors[id], `${task.key}/${setting.key}/${dataset}/${id}`);
            if (observed.has(id)) assert.equal(color, observed.get(id));
            observed.set(id, color);
            assert.equal(Number(value), row.values[column]);
            assert.equal(label, row.values[column].toFixed(metric.digits));
            // Color changes must not change numerical emphasis or block membership.
            const block = setting.blocks?.find(b => b.includes(id));
            const peers = setting.rows.filter(r => data.methods[r.method].kind !== 'oracle' && (!setting.blocks || block?.includes(r.method)));
            const better = metric.direction === 'up' ? (a, b) => a > b : (a, b) => a < b;
            const best = data.methods[id].kind !== 'oracle' && peers.length > 0 && !peers.some(r => better(r.values[column], row.values[column]));
            assert.equal(classes.split(' ').includes('bm-best'), best);
          });
        });
        states++;
      }
    }
  }
}
assert.equal(states, 57);
assert.equal(observed.size, Object.keys(expectedColors).length);
assert.equal(JSON.stringify(data), snapshot, 'Rendering must not mutate the registry or values');
const css = read('../assets/benchmarks/benchmarks.css');
assert.match(css, /#benchmarks \.bm-bar\.bm-best \.bm-value\{font-weight:700\}/);
assert.doesNotMatch(css, /[^{}]*\.bm-ours[^{}]*\.bm-value[^{}]*\{/);
assert.deepEqual(errors, []);
console.log(`PASS: ${observed.size} unique, fixed method/variant colors; bars and legends agree in ${states} states; values, precision and best-result classes preserved.`);
