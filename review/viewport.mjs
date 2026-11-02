// Preserve the user's place when review controls update the surrounding layout.
// Do not restore an old position after the user has interacted during an async load.
let interaction = 0;
for (const type of ['wheel', 'touchmove', 'pointerdown', 'keydown']) {
  window.addEventListener(type, () => { interaction++; }, {capture: true, passive: true});
}
export function captureViewport() {
  const inspector = document.getElementById('inspector');
  const anchor = [...document.querySelectorAll('#case-grid > .review-card')].find(card => {
    const box = card.getBoundingClientRect();
    return box.bottom > 80 && box.top < window.innerHeight;
  });
  return {
    x: window.scrollX, y: window.scrollY, interaction,
    focus: document.activeElement, anchor, top: anchor?.getBoundingClientRect().top,
    inspector, inspectorTop: inspector?.scrollTop ?? 0,
  };
}
export function restoreViewport(saved) {
  if (!saved || saved.interaction !== interaction) return;
  // Moving an existing card during sorting may drop keyboard focus.
  if (saved.focus?.isConnected && document.activeElement !== saved.focus) {
    saved.focus.focus({preventScroll: true});
  }
  if (saved.inspector?.isConnected) saved.inspector.scrollTop = saved.inspectorTop;
  const y = saved.anchor?.isConnected
    ? window.scrollY + saved.anchor.getBoundingClientRect().top - saved.top
    : saved.y;
  window.scrollTo({left: saved.x, top: y, behavior: 'instant'});
}
export function preserveViewport(update) {
  // Filtering or sorting may move the anchor itself. Preserve the scroll offset.
  const saved = {...captureViewport(), anchor: null};
  try { return update(); } finally { restoreViewport(saved); }
}
