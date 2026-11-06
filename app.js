"use strict";
// Cache-busting token, stamped by tools/bump_asset_version.py.
const ASSET_VERSION = "20261106-f16";
function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text) node.textContent = text;
  return node;
}
function renderPlaceholder(panel, example) {
  const inner = element("div", "placeholder-inner");
  inner.append(element("div", "pending", example.label + " · placeholder"),
    element("h3", "", example.title), element("p", "", example.description));
  const placeholder = element("div", "placeholder");
  placeholder.append(inner);
  panel.replaceChildren(placeholder, element("p", "caption", "Example pending selection."));
}
function renderExample(panel, example) {
  const motion = window.matchMedia("(prefers-reduced-motion: reduce)");
  let visible = false, wanted = (example.autoplay ?? true) && !motion.matches, current;
  const managedPauses = new WeakSet();
  function pause(video) {
    if (video && !video.paused) { managedPauses.add(video); video.pause(); }
  }
  function resume() {
    if (visible && wanted && current) current.play().catch(() => {});
  }
  const segment = element("div", "seg"), segmentWrap = element("div", "segwrap");
  segment.setAttribute("role", "group"); segment.setAttribute("aria-label", "Example view");
  segmentWrap.append(segment);
  const stage = element("div", "media-stage"), labels = element("div", "media-labels");
  const description = element("p", "caption"); description.setAttribute("aria-live", "polite");
  function showView(key) {
    const view = example.views[key];
    pause(current);
    const media = element("video");
    media.controls = true; media.loop = true; media.muted = true;
    media.playsInline = true; media.preload = "metadata"; media.poster = view.poster;
    media.setAttribute("aria-label", view.description); media.src = view.src;
    current = media;
    media.addEventListener("play", () => { if (current === media) wanted = true; });
    media.addEventListener("pause", () => {
      if (!managedPauses.delete(media) && current === media) wanted = false;
    });
    media.addEventListener("loadeddata", resume);
    media.addEventListener("error", () => stage.replaceChildren(element("p", "result-error", "This preview is unavailable.")), {once:true});
    stage.replaceChildren(media);
    labels.replaceChildren(...(view.labels || []).map(label => element("span", "", label)));
    labels.hidden = !view.labels;
    description.textContent = view.description;
    segment.querySelectorAll("button").forEach(button => button.setAttribute("aria-pressed", String(button.dataset.view === key)));
    resume();
  }
  Object.entries(example.views).forEach(([key, view]) => {
    const button = element("button", "", view.label); button.type = "button"; button.dataset.view = key;
    button.addEventListener("click", () => showView(key)); segment.append(button);
  });
  panel.replaceChildren(segmentWrap, stage, labels, description);
  function motionChange() { if (motion.matches) { wanted = false; pause(current); } }
  motion.addEventListener("change", motionChange);
  panel.uggPlayback = {
    setVisible(value) { visible = value; if (value) resume(); else pause(current); },
    dispose() {
      visible = false; pause(current); motion.removeEventListener("change", motionChange);
      if (current) { current.removeAttribute("src"); current.load(); }
    },
  };
  showView(example.default_view);
}
const galleries = new Map();
function updateVisibility(state) {
  state.cache.forEach(panel => {
    const visible = state.inView && !panel.hidden && !document.hidden;
    panel.uggSync?.setVisible(visible);
    panel.uggPlayback?.setVisible(visible);
  });
}
fetch("examples.json").then(response => {
  if (!response.ok) throw new Error("Example manifest unavailable");
  return response.json();
}).then(async examples => {
  const {applyDepthShowcase} = await import("./assets/depth-showcase.mjs");
  const {applyCameraShowcase} = await import("./assets/camera-showcase.mjs");
  examples = applyCameraShowcase(applyDepthShowcase(examples));
  const {applyNvsShowcase} = await import("./assets/nvs-showcase.mjs");
  examples = applyNvsShowcase(examples);
  const {applyText4DShowcase} = await import("./assets/text4d-showcase.mjs");
  examples = applyText4DShowcase(examples);
  document.querySelectorAll("[data-result-task]").forEach(section => {
    const task = section.dataset.resultTask, cases = examples[task].cases;
    const sceneLabels = new Map(["nvs","depth","camera","generation"].includes(task)
      ? cases.map((example,index) => [example.id,"Scene " + String(index + 1).padStart(2,"0")])
      : []);
    const viewer = section.querySelector(".case-viewer"), thumbs = section.querySelector(".case-thumbnails");
    const state = {cache:new Map(), inView:false, selected:null}; galleries.set(section, state);
    const pageSize = 24;
    let filtered = cases, page = 0;
    const filters = element("div", "gallery-filters");
    const count = element("p", "gallery-count"); count.setAttribute("aria-live", "polite");
    const pager = element("div", "gallery-pager");
    const previous = element("button", "", "Previous cases"), next = element("button", "", "Next cases");
    previous.type = next.type = "button";
    previous.dataset.action = "previous-page"; next.dataset.action = "next-page";
    const pageLabel = element("span"); pageLabel.setAttribute("aria-live", "polite");
    pager.append(previous, pageLabel, next);
    const selectors = {};
    const datasetNames = {dl3dv20:"DL3DV",dl3dv_wide:"DL3DV Wide",mip:"Mip-NeRF 360",re10k128_50f:"RealEstate10K · 128 scenes",re10k_c50:"RealEstate10K · 50 frames",spatialvid:"Spatial Video",bonn:"Bonn",kitti:"KITTI",sintel:"Sintel",scannetpp:"ScanNet++"};
    for (const [key, label] of [["dataset", "Dataset"], ["protocol", "Protocol"]]) {
      if (key === "dataset" && ["nvs", "depth", "camera"].includes(task)) continue;
      const values = [...new Set(cases.map(example => example[key]).filter(Boolean))].sort();
      if (values.length < 2) continue;
      const field = element("label", "", label), select = element("select");
      select.setAttribute("aria-label", label + " for " + task);
      const all = element("option", "", "All " + label.toLowerCase() + "s"); all.value = ""; select.append(all);
      values.forEach(value => {
        const title = key === "dataset" ? (datasetNames[value] || value) : ({ncf1:"1 conditioning frame",ncf2:"2 conditioning frames",dense:"Dense · first contiguous frames"}[value] || value);
        const option = element("option", "", title); option.value = value; select.append(option);
      });
      select.addEventListener("change", () => {
        filtered = cases.filter(example => Object.entries(selectors).every(([name, control]) => !control.value || example[name] === control.value));
        page = 0; renderThumbs(true);
      });
      field.append(select); filters.append(field); selectors[key] = select;
    }
    if (filters.childElementCount) thumbs.before(filters);
    thumbs.before(count); thumbs.after(pager);
    if (!["nvs", "depth", "camera"].includes(task) && examples[task].selection?.caption) {
      thumbs.before(element("p", "caption gallery-selection", examples[task].selection.caption));
    }
    viewer.replaceChildren();
    function trimCache() {
      while (state.cache.size > 3) {
        const entry = [...state.cache].find(([id, panel]) => id !== state.selected && panel.dataset.caseReady);
        if (!entry) break;
        const [id, panel] = entry;
        panel.uggSync?.dispose(); panel.uggPlayback?.dispose();
        panel.querySelectorAll("video").forEach(video => { video.pause(); video.removeAttribute("src"); video.load(); });
        panel.remove(); state.cache.delete(id);
      }
    }
    async function selectCase(example, button) {
      state.selected = example.id;
      thumbs.querySelectorAll("button").forEach(item => item.setAttribute("aria-pressed", String(item === button)));
      state.cache.forEach((panel, id) => { panel.hidden = id !== example.id; });
      let panel = state.cache.get(example.id);
      if (!panel) {
        panel = element("div", "panel case-panel"); panel.dataset.caseId = example.id;
        panel.id = task + "-" + example.id; button.setAttribute("aria-controls", panel.id);
        state.cache.set(example.id, panel); viewer.append(panel);
        panel.append(element("div", "placeholder", "Loading this case…"));
        // Cache each case viewer so revisiting it preserves its frame and view.
        try {
          if (example.kind === "placeholder") renderPlaceholder(panel, example);
          else if (example.kind === "viser") {
            const module = await import(`./viser-viewer.js?v=${ASSET_VERSION}`);
            await module.renderViserExample(panel, example);
          }
          else if (example.kind === "synchronized") {
            const module = await import(`./sync-viewers.js?v=${ASSET_VERSION}`);
            await module.renderSyncExample(panel, example);
          } else if (example.kind === "text4d") {
            const module = await import(`./text4d-viewer.js?v=${ASSET_VERSION}`);
            await module.renderText4DExample(panel, example);
          } else renderExample(panel, example);
          panel.dataset.caseReady = "true";
        } catch {
          panel.replaceChildren(element("div", "placeholder", "Result preview unavailable."));
          panel.dataset.caseError = "true";
        }
      } else {
        panel.hidden = false;
        state.cache.delete(example.id); state.cache.set(example.id, panel);
      }
      panel.hidden = state.selected !== example.id;
      trimCache();
      updateVisibility(state);
    }
    function renderThumbs(selectFirst = false) {
      thumbs.replaceChildren();
      const start = page * pageSize, visibleCases = filtered.slice(start, start + pageSize);
      count.textContent = filtered.length ? "Cases " + (start + 1) + "–" + (start + visibleCases.length) + " of " + filtered.length : "No cases match these filters.";
      count.hidden = cases.length <= pageSize && task !== "camera" && task !== "nvs";
      pager.hidden = filtered.length <= pageSize;
      previous.disabled = page === 0; next.disabled = start + pageSize >= filtered.length;
      pageLabel.textContent = "Page " + (page + 1) + " of " + Math.max(1, Math.ceil(filtered.length / pageSize));
      visibleCases.forEach((example, index) => {
      const button = element("button", "thumb case-thumb"); button.type = "button";
      button.dataset.caseId = example.id; button.setAttribute("aria-pressed", "false");
      button.setAttribute("aria-label", example.kind === "placeholder" ? example.label + ": case pending" : "Select " + (sceneLabels.get(example.id) || example.title));
      button.setAttribute("aria-pressed", String(example.id === state.selected));
      button.setAttribute("aria-controls", task + "-" + example.id);
      if (example.thumbnail) {
        const image = element("img"); image.src = example.thumbnail; image.alt = ""; image.loading = "lazy";
        button.append(image);
      } else button.append(element("span", "thumb-pending", "◇"));
      button.append(element("span", "thumb-label", example.kind === "placeholder" ? "Case pending" : (sceneLabels.get(example.id) || example.short_title)));
      button.addEventListener("click", () => selectCase(example, button));
      button.addEventListener("keydown", event => {
        let target;
        if (event.key === "ArrowRight") target = (index + 1) % visibleCases.length;
        if (event.key === "ArrowLeft") target = (index + visibleCases.length - 1) % visibleCases.length;
        if (event.key === "Home") target = 0;
        if (event.key === "End") target = visibleCases.length - 1;
        if (target !== undefined) { event.preventDefault(); const next = thumbs.children[target]; next.focus(); next.click(); }
      });
      thumbs.append(button);
      });
      if (selectFirst && visibleCases.length) selectCase(visibleCases[0], thumbs.children[0]);
      if (!visibleCases.length) {
        state.selected = null; state.cache.forEach(panel => { panel.hidden = true; }); updateVisibility(state);
      }
    }
    previous.addEventListener("click", () => { page--; renderThumbs(true); });
    next.addEventListener("click", () => { page++; renderThumbs(true); });
    renderThumbs(true);
    if ("IntersectionObserver" in window) {
      const observer = new IntersectionObserver(entries => {
        state.inView = entries.at(-1).isIntersecting; updateVisibility(state);
      });
      observer.observe(viewer);
    } else { state.inView = true; updateVisibility(state); }
  });
}).catch(() => {
  document.querySelectorAll(".case-viewer").forEach(viewer => {
    viewer.replaceChildren(element("div", "placeholder", "Result preview pending. Selected examples will go here."));
  });
});
document.addEventListener("visibilitychange", () => galleries.forEach(updateVisibility));
const copyButton = document.querySelector("#copy-citation");
copyButton.addEventListener("click", async () => {
  try {
    await navigator.clipboard.writeText(document.querySelector("#citation").textContent);
    copyButton.textContent = "Copied"; setTimeout(() => { copyButton.textContent = "Copy BibTeX"; }, 1800);
  } catch {
    copyButton.textContent = "Select citation to copy";
    const selection = window.getSelection(), range = document.createRange();
    range.selectNodeContents(document.querySelector("#citation")); selection.removeAllRanges(); selection.addRange(range);
  }
});
if ("IntersectionObserver" in window) {
  const links = [...document.querySelectorAll(".navlinks a")];
  const observer = new IntersectionObserver(entries => {
    entries.forEach(entry => {
      if (!entry.isIntersecting) return;
      const id = entry.target.matches(".result-section") ? "results" : entry.target.id;
      links.forEach(link => {
        if (link.hash === "#" + id) link.setAttribute("aria-current", "location");
        else link.removeAttribute("aria-current");
      });
    });
  }, {rootMargin:"-15% 0px -55% 0px"});
  document.querySelectorAll("main section[id]").forEach(section => observer.observe(section));
}
