"use strict";
// Interactive 3D reconstruction cases. The point cloud is a self-contained
// viser page, embedded in an iframe so its WebGL context stays isolated from
// the rest of the gallery. Loaded lazily by app.js on first case selection,
// and the panel is cached, so revisiting a case keeps its camera and frame.
function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text) node.textContent = text;
  return node;
}
export async function renderViserExample(panel, example) {
  const stage = element("div", "media-stage viser-stage");
  let visible = false, disposed = false, timeline, timelineObserver, readyObserver, currentFrame = -1;
  const frame = document.createElement("iframe");
  frame.className = "viser-frame";
  frame.title = example.title + " — interactive point cloud";
  frame.loading = "lazy";
  frame.allow = "fullscreen";
  // A .viser recording is played by the shared client; a .html case is a
  // self-contained export that is its own player.
  const recording = example.src.endsWith(".viser");
  const source = new URL(recording ? "viser/viser-client/index.html" : example.src, document.baseURI);
  if (recording) {
    source.searchParams.set("playbackPath", new URL(example.src, document.baseURI).pathname);
  }
  if (example.initial_camera) {
    source.searchParams.set("initialCameraPosition", example.initial_camera.position.join(","));
    source.searchParams.set("initialCameraLookAt", example.initial_camera.look_at.join(","));
    source.searchParams.set("initialCameraUp", (example.initial_camera.up || [0,-1,0]).join(","));
  }
  const loading = element("div", "placeholder", "Loading the 3D viewer…");
  stage.append(loading);
  frame.addEventListener("load", () => loading.remove(), {once: true});
  frame.addEventListener("error", () => {
    stage.replaceChildren(element("p", "result-error", "This 3D viewer is unavailable."));
  }, {once: true});

  // No sample row: the case grid below sits inside the same panel and highlights
  // whichever case is playing, so repeating its thumbnail and title here is noise.
  const children = [stage];
  if (example.input_rgb) {
    const data = example.input_rgb, sprite = new Image();
    const inset = element("div", "rgb-inset"), input = element("canvas");
    inset.hidden = true;
    input.width = data.width; input.height = data.height;
    input.setAttribute("role", "img"); input.setAttribute("aria-label", "Matching reconstruction input RGB");
    inset.append(element("span", "rgb-inset-label", "Input RGB"), input); stage.append(inset);
    const options = element("div", "viewer-options"), label = element("label"), toggle = element("input");
    toggle.type = "checkbox"; toggle.checked = true;
    label.append(toggle, document.createTextNode("Show input")); options.append(label);
    children.splice(1, 0, options);
    toggle.addEventListener("change", () => { inset.hidden = !toggle.checked; if (toggle.checked) draw(); });
    function draw() {
      if (disposed || !visible || !timeline || !sprite.naturalWidth) return;
      const time = Number(timeline.getAttribute("aria-valuenow"));
      if (!Number.isFinite(time)) return;
      let index = 0;
      for (let i = 1; i < data.frame_times.length && data.frame_times[i] <= time + 1e-9; i++) index = i;
      if (index !== currentFrame) {
        input.getContext("2d").drawImage(sprite, (index % data.columns) * data.width,
          Math.floor(index / data.columns) * data.height, data.width, data.height, 0, 0, data.width, data.height);
        currentFrame = index; input.dataset.frame = String(index);
      }
      inset.hidden = !toggle.checked;
      panel.dataset.rgbReady = "true";
    }
    function bindTimeline() {
      if (disposed || timeline) return;
      // The bundled, same-origin Viser player exposes its precise clock on the
      // slider's ARIA value. Follow it directly so pause, seek, loop and speed
      // changes share one timeline rather than starting a second media clock.
      timeline = [...frame.contentDocument.querySelectorAll("[role=slider][aria-valuemax]")]
        .find(node => Math.abs(Number(node.getAttribute("aria-valuemax")) - data.duration) < 1e-6);
      if (!timeline) return;
      readyObserver?.disconnect();
      timelineObserver = new MutationObserver(draw);
      timelineObserver.observe(timeline, {attributes:true, attributeFilter:["aria-valuenow"]});
      draw();
    }
    frame.addEventListener("load", () => {
      if (disposed) return;
      readyObserver = new MutationObserver(bindTimeline);
      readyObserver.observe(frame.contentDocument.body, {childList:true, subtree:true});
      bindTimeline();
    }, {once:true});
    sprite.addEventListener("load", draw, {once:true});
    sprite.addEventListener("error", () => {
      panel.dataset.rgbError = "true";
      inset.replaceChildren(element("p", "result-error", "RGB preview unavailable.")); inset.hidden = false;
    }, {once:true});
    sprite.src = data.src;
    panel.uggPlayback = {
      setVisible(value) { visible = value; if (value) draw(); },
      dispose() {
        disposed = true; timelineObserver?.disconnect(); readyObserver?.disconnect();
        sprite.removeAttribute("src"); frame.src = "about:blank";
      },
      snapshot() { return {frame:currentFrame, time:timeline ? Number(timeline.getAttribute("aria-valuenow")) : null}; },
    };
  }
  if (example.note) {
    const oracle = element("p", "oracle-note");
    oracle.append(element("b", "", "Selection note: "), document.createTextNode(example.note));
    children.push(oracle);
  }
  if (example.display_note) children.push(element("p", "display-note", example.display_note));
  panel.replaceChildren(...children);
  if (example.initial_camera?.fov) {
    const view = example.initial_camera, aspect = stage.clientWidth/stage.clientHeight || 16/10;
    const fov = 2*Math.atan(Math.max(Math.tan(view.fov/2),
      Math.tan((view.horizontal_fov || view.fov)/2)/aspect));
    source.searchParams.set("initialCameraFov", String(fov));
  }
  frame.src = source.href;
  stage.append(frame);
}
