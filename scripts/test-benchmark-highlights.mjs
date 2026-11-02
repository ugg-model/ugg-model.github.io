// Run: node scripts/test-benchmark-highlights.mjs (no npm dependencies).
// Exercise the production renderer, with independent expected winners from
// manuscript Tables 1–4. Browser checks should additionally verify CSS font weights.
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
const root = { querySelector: node, querySelectorAll: () => [] };
const errors = [];
const context = {
  window: { matchMedia: () => ({matches: true}) },
  document: { getElementById: id => id === 'benchmarks' ? root : null },
  console: { error: (...args) => errors.push(args) }
};
vm.runInNewContext(read('../assets/benchmarks/data.js'), context);
const data = context.window.UGG_BENCHMARKS;
const original = JSON.stringify(data);
vm.runInNewContext(read('../assets/benchmarks/benchmarks.js'), context);
assert.deepEqual(errors, [], 'Production renderer initializes without errors');
assert.equal(node('#bm-app').hidden, false);
const click = (selector, key, value) => node(selector).events.click({
  target: { closest: () => ({dataset: {[key]: String(value)}}) }
});
const selectTask = key => click('#bm-tabs', 'task', data.tasks.findIndex(t => t.key === key));
const selectMode = index => click('#bm-modes', 'mode', index);
const filter = value => node('#bm-dataset').events.change({target: {value}});
const oracle = checked => node('#bm-oracle').events.change({target: {checked}});
const matches = (html, expression) => Array.from(html.matchAll(expression));
const charts = () => matches(node('#bm-charts').innerHTML, /<svg\b[^>]*>([\s\S]*?)<\/svg>/g).map(([, svg]) =>
  matches(svg, /<g\s+class="([^"]*)"[^>]*data-method="([^"]+)"\s+data-value="([^"]+)"[\s\S]*?<text[^>]*>([^<]*)<\/text><\/g>/g)
    .map(([, classes, method, value, label]) => ({method, value: Number(value), label, best: classes.split(' ').includes('bm-best')}))
);
const chartWinners = () => charts().map(bars => bars.filter(b => b.best).map(b => b.method));
const tableRows = index => {
  const [, body] = matches(node('#bm-table-body').innerHTML, /<tbody>([\s\S]*?)<\/tbody>/g)[index];
  return matches(body, /<tr[^>]*><th[^>]*>([^<]*)<\/th>([\s\S]*?)<\/tr>/g).map(([, label, html]) => ({
    label, cells: matches(html, /<td([^>]*)>([^<]*)<\/td>/g).map(([, attrs, value]) => ({value, best: attrs.includes('bm-best')}))
  }));
};
const tableWinners = (setting, index) => {
  const rows = tableRows(index);
  return rows[0].cells.map((_, column) => rows.flatMap((r, ri) => r.cells[column].best ? [setting.rows[ri].method] : []));
};
const W = text => text.split(' ').map(column => column.split('+'));
const expected = {
  generation: [
    W('ugg ugg ugg ugg ugg ugg seva seva seva'),
    W('ugg ugg ugg ugg ugg ugg ugg ugg ugg')
  ],
  pose: [
    W('ugg ugg ugg ugg ugg ugg ugg ugg gen3r ugg ugg ugg ugg ugg ugg'),
    W('ugg ugg ugg ugg ugg ugg ugg ugg ugg ugg')
  ],
  depth: [
    W('tts ugg ugg gen3r aether aether geo4d geo4d ugg geo4d'),
    W('ugg ugg tts tts marigold marigold tts tts tts tts')
  ],
  ablations: [
    W('single single full full'),
    W('full+dense-rays full+dense-rays full+dense-rays full+dense-rays'),
    W('full full full'),
    W('w2 w0 w1 w0')
  ]
};
let tableValues = 0, chartValues = 0, chartCount = 0, oracleValues = 0;
for (const task of data.tasks) {
  selectTask(task.key);
  task.settings.forEach((setting, index) => {
    const winners = expected[task.key][index];
    assert.equal(winners.length, setting.datasets.length * setting.metrics.length);
    selectMode(index); filter('all'); oracle(false);
    assert.deepEqual(chartWinners(), winners, `${task.key}/${setting.key}: chart ranking`);
    assert.deepEqual(tableWinners(setting, index), winners, `${task.key}/${setting.key}: table ranking`);
    assert.match(node('.bm-chart-note').textContent, /Bold values mark the best non-oracle result/);
    assert.equal(matches(node('#bm-charts').innerHTML, /class="bm-block-separator"/g).length, setting.blocks ? winners.length : 0);
    const rows = tableRows(index);
    assert.equal(rows.length, setting.rows.length);
    rows.forEach((r, ri) => r.cells.forEach((cell, ci) => {
      assert.equal(cell.value, setting.rows[ri].values[ci].toFixed(setting.metrics[ci % setting.metrics.length].digits));
      tableValues++;
    }));
    charts().forEach((bars, ci) => {
      const expectedRows = setting.rows.filter(r => data.methods[r.method].kind !== 'oracle');
      assert.equal(bars.length, expectedRows.length);
      bars.forEach((b, ri) => {
        assert.equal(b.method, expectedRows[ri].method);
        assert.equal(b.value, expectedRows[ri].values[ci]);
        assert.equal(b.label, b.value.toFixed(setting.metrics[ci % setting.metrics.length].digits));
        chartValues++;
      });
      chartCount++;
    });
    setting.datasets.forEach((dataset, di) => {
      filter(dataset);
      const start = di * setting.metrics.length;
      assert.deepEqual(chartWinners(), winners.slice(start, start + setting.metrics.length));
      assert.deepEqual(tableWinners(setting, index), winners, 'Filters do not alter full tables');
    });
    filter('all');
    if (task.key === 'depth') {
      oracle(true);
      assert.deepEqual(chartWinners(), winners, 'Showing Oracle never changes non-oracle ranking');
      charts().forEach((bars, ci) => {
        const b = bars.find(item => item.method === 'oracle');
        const source = setting.rows.find(r => r.method === 'oracle').values[ci];
        assert(b && !b.best);
        assert.equal(b.value, source);
        assert.equal(b.label, source.toFixed(setting.metrics[ci % setting.metrics.length].digits));
        oracleValues++;
      });
      oracle(false);
    }
  });
}
assert.deepEqual([tableValues, chartValues, chartCount, oracleValues], [378, 358, 78, 20]);
assert.equal(JSON.stringify(data), original, 'Rendering never changes source data');
// Synthetic edge cases on a disposable in-memory copy, not manuscript edits.
const generation = data.tasks[0].settings[0];
const seva = generation.rows.find(r => r.method === 'seva');
const ugg = generation.rows.find(r => r.method === 'ugg');
const saved = [...seva.values];
seva.values[0] = ugg.values[0]; // Tie on a higher-is-better metric.
seva.values[1] = ugg.values[1]; // Tie on a lower-is-better metric.
selectTask('generation'); selectMode(0);
assert.deepEqual(chartWinners().slice(0, 2), [['seva', 'ugg'], ['seva', 'ugg']]);
assert.deepEqual(tableWinners(generation, 0).slice(0, 2), [['seva', 'ugg'], ['seva', 'ugg']]);
seva.values[0] = ugg.values[0] - .0001; // Same displayed precision, not an actual tie.
selectTask('generation');
assert.deepEqual(chartWinners()[0], ['ugg']);
assert.deepEqual(tableWinners(generation, 0)[0], ['ugg']);
seva.values = saved;
assert.equal(JSON.stringify(data), original);
const css = read('../assets/benchmarks/benchmarks.css');
assert.match(css, /#benchmarks \.bm-bar\.bm-best \.bm-value\{font-weight:700\}/);
assert.match(css, /#benchmarks td\.bm-best\{/);
assert.doesNotMatch(css, /[^{}]*\.bm-ours[^{}]*\.bm-value[^{}]*\{/);
assert.deepEqual(errors, []);
console.log('PASS: all 10 settings, 78 charts, 358 chart values + 20 Oracle values, 378 table values, filters, ties, precision, ranking blocks and CSS rank-only bolding.');
