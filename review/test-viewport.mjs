import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
const events = new Map();
let cardTop = 2400;
const inspector = {isConnected: true, scrollTop: 320};
const checkbox = {isConnected: true, focus(options) {
  assert.equal(options.preventScroll, true);
  document.activeElement = this;
}};
const card = {isConnected: true, getBoundingClientRect() {
  return {top: cardTop - window.scrollY, bottom: cardTop + 200 - window.scrollY};
}};
globalThis.window = {
  scrollX: 12, scrollY: 2200, innerHeight: 900,
  addEventListener(type, callback) { events.set(type, callback); },
  scrollTo({left, top, behavior}) {
    assert.equal(behavior, 'instant');
    this.scrollX = left; this.scrollY = top;
  },
};
globalThis.document = {
  activeElement: checkbox,
  getElementById: id => id === 'inspector' ? inspector : null,
  querySelectorAll: () => [card],
};
const {captureViewport, restoreViewport, preserveViewport} = await import('./viewport.mjs');
preserveViewport(() => {
  window.scrollY = 151;
  inspector.scrollTop = 0;
  document.activeElement = null;
  cardTop = 600; // Sorting must not scroll to the moved card.
});
assert.equal(window.scrollY, 2200);
assert.equal(window.scrollX, 12);
assert.equal(inspector.scrollTop, 320);
assert.equal(document.activeElement, checkbox);
cardTop = 2400;
const beforeLoad = captureViewport();
cardTop += 80; // A differently sized preview above the library.
window.scrollY = 151;
restoreViewport(beforeLoad);
assert.equal(window.scrollY, 2280);
const stale = captureViewport();
events.get('wheel')();
window.scrollY = 2600;
inspector.scrollTop = 90;
restoreViewport(stale);
assert.equal(window.scrollY, 2600, 'Async loading must not undo user scrolling');
assert.equal(inspector.scrollTop, 90);
const detached = captureViewport();
card.isConnected = false;
window.scrollY = 0;
restoreViewport(detached);
assert.equal(window.scrollY, 2600);
assert.throws(() => preserveViewport(() => {
  window.scrollY = 0;
  throw Error('Expected test error');
}), /Expected test error/);
assert.equal(window.scrollY, 2600);
const app = readFileSync(new URL('./app.mjs', import.meta.url), 'utf8');
assert.ok(app.includes('cardCache.get(key)'));
assert.ok(!app.includes("$('case-grid').replaceChildren"));
assert.ok(!app.includes('scrollIntoView('), 'Case clicks must not force scrolling');
assert.ok(app.includes('p.dataset.reviewTask=task'));
assert.ok(app.includes("host.style.minHeight=''"));
const state = readFileSync(new URL('./state.mjs', import.meta.url), 'utf8');
assert.ok(state.includes('ugg-material-review:v1'), 'Do not reset existing browser records');
console.log('PASS: scroll offsets, stable focus, inspector scroll, sorting, preview-height changes, stale async loads, and existing storage key.');
