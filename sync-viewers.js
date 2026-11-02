function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text) node.textContent = text;
  return node;
}

export async function renderSyncExample(panel, example) {
  const cameraMode = example.task === "camera";
  const nvsMode = example.task === "nvs";
  const hasCamera = cameraMode || (nvsMode && !!example.poses);
  const hasInput = example.has_input ?? !!example.input_video;
  const motion = window.matchMedia("(prefers-reduced-motion: reduce)");
  let wanted = (example.autoplay ?? true) && !motion.matches, managedPause = false, disposed = false, callbackId;
  panel.replaceChildren();
  const frameCount = example.frame_count, fps = example.fps;
  let cameraViewer = null, frame = 0, sourceRequest = 0, visible = false;
  const segment = element("div", "seg"), segmentWrap = element("div", "segwrap");
  segment.setAttribute("role", "group"); segment.setAttribute("aria-label", "Depth view");
  if (!cameraMode && Object.keys(example.views).length > 1) {
    Object.entries(example.views).forEach(([key, view]) => {
      const button = element("button", "", view.label);
      button.type = "button"; button.dataset.view = key;
      button.setAttribute("aria-pressed", String(key === example.default_view));
      button.addEventListener("click", () => {
        const time = video.currentTime;
        main.setAttribute("aria-label", view.description);
        [...segment.children].forEach(item => item.setAttribute("aria-pressed", String(item === button)));
        loadSource(view.src, time);
      });
      segment.append(button);
    });
    segmentWrap.append(segment); panel.append(segmentWrap);
  }
  const stage = element("div", cameraMode ? "sync-stage camera-stage" : nvsMode ? "sync-stage nvs-sync-stage" : "sync-stage depth-sync-stage");
  const video = element("video", "sync-source");
  video.muted = true; video.playsInline = true; video.loop = true; video.preload = "auto";
  video.setAttribute("aria-hidden", "true");
  video.dataset.role = "sync-master";
  const main = cameraMode ? null : element("canvas", nvsMode ? "comparison-canvas" : "depth-canvas");
  if (main) {
    main.width = example.width; main.height = example.height;
    main.setAttribute("role", "img"); main.setAttribute("aria-label", example.views[example.default_view].description);
    stage.append(main);
    const view = example.views[example.default_view];
    if (view.labels) {
      const labels = element("div", "comparison-labels");
      labels.append(...view.labels.map(label => element("span", "", label)));
      stage.append(labels);
    }
  }
  const poseInset = nvsMode && hasCamera ? element("div", "pose-inset") : null;
  if (poseInset) stage.append(poseInset);
  const inset = hasInput ? element("div", "rgb-inset") : null;
  const input = hasInput ? element("canvas") : null;
  if (input) {
    inset.append(element("span", "rgb-inset-label", "Input RGB"));
    input.width = example.input_width || example.width;
    input.height = example.input_height || example.height;
    input.setAttribute("role", "img"); input.setAttribute("aria-label", "Matching GT input video");
    inset.append(input); stage.append(inset);
  }
  stage.append(video);
  panel.append(stage);
  const bar = element("div", "timeline");
  const play = element("button", "", "Play");
  play.type = "button"; play.dataset.action = "play";
  const previous = element("button", "frame-step", "‹");
  previous.type = "button"; previous.setAttribute("aria-label", "Previous frame");
  const next = element("button", "frame-step", "›");
  next.type = "button"; next.setAttribute("aria-label", "Next frame");
  const slider = element("input");
  slider.type = "range"; slider.min = "0"; slider.max = String(frameCount - 1); slider.step = "1"; slider.value = "0";
  slider.setAttribute("aria-label", "Video frame");
  const label = element("output", "frame-label", "Frame 1 / " + frameCount);
  bar.append(play, previous, slider, next, label);
  panel.append(bar);
  const controls = element("div", "viewer-options");
  const speedLabel = element("label", "speed-control", "Speed");
  const speed = element("select");
  speed.setAttribute("aria-label", "Playback speed");
  for (const multiplier of [0.5, 1, 2, 4, 8]) {
    const option = element("option", "", multiplier + "×");
    option.value = String(multiplier); option.selected = multiplier === 1;
    speed.append(option);
  }
  function applySpeed() {
    // FPS metadata still describes the encoded video and pose timeline.
    // Normalize wall-clock playback without changing frame lookup or seeking.
    const rate = 10 / fps * Number(speed.value);
    video.defaultPlaybackRate = rate; video.playbackRate = rate;
  }
  speed.addEventListener("change", applySpeed);
  speedLabel.append(speed); controls.append(speedLabel); applySpeed();
  function checkbox(text, checked, callback) {
    const label = element("label"), input = element("input");
    input.type = "checkbox"; input.checked = checked;
    input.addEventListener("change", () => callback(input.checked));
    label.append(input, document.createTextNode(text)); controls.append(label);
    return input;
  }
  if (inset) checkbox("Show input", true, value => { inset.hidden = !value; });
  let rotate, orientations;
  if (hasCamera) {
    if (poseInset) checkbox("Show camera", true, value => {
      poseInset.hidden = !value; cameraViewer?.setVisible(visible && value);
    });
    rotate = checkbox("Rotate view during playback", !motion.matches, value => cameraViewer?.setRotate(value));
    orientations = checkbox("Show frame orientations", true, value => cameraViewer?.setOrientations(value));
    const reset = element("button", "reset-view", "Reset view");
    reset.type = "button"; reset.addEventListener("click", () => cameraViewer?.reset()); controls.append(reset);
  }
  panel.append(controls);

  function updatePlayState() {
    play.textContent = video.paused ? "Play" : "Pause";
    play.setAttribute("aria-label", video.paused ? "Play synchronized video" : "Pause synchronized video");
    cameraViewer?.setPlaying(!video.paused);
  }
  function pauseManaged() {
    if (!video.paused) { managedPause = true; video.pause(); }
  }
  function resume() {
    // Other cases may finish loading while this viewer is still fetching poses.
    // Wait for this clock's decoded frame before attempting playback.
    if (visible && wanted && !disposed && video.readyState >= 2) video.play().catch(updatePlayState);
  }
  function motionChange() {
    if (motion.matches) {
      wanted = false; pauseManaged();
      if (rotate) { rotate.checked = false; cameraViewer?.setRotate(false); }
    }
  }
  motion.addEventListener("change", motionChange);
  function draw(mediaTime = video.currentTime) {
    if (disposed || video.readyState < 2) return;
    frame = Math.max(0, Math.min(frameCount - 1, Math.floor(mediaTime * fps + 0.0001)));
    if (main) {
      main.getContext("2d").drawImage(video, 0, 0, example.width, example.height, 0, 0, main.width, main.height);
      if (input) input.getContext("2d").drawImage(video, example.width, 0, input.width, input.height, 0, 0, input.width, input.height);
      main.dataset.frame = String(frame);
    } else if (input) {
      input.getContext("2d").drawImage(video, 0, 0, input.width, input.height);
    }
    if (input) input.dataset.frame = String(frame);
    panel.dataset.frame = String(frame);
    slider.value = String(frame);
    slider.setAttribute("aria-valuetext", "Frame " + (frame + 1) + " of " + frameCount);
    label.textContent = "Frame " + (frame + 1) + " / " + frameCount;
    cameraViewer?.setFrame(frame);
  }
  function queueFrame() {
    if (!disposed && "requestVideoFrameCallback" in video) callbackId = video.requestVideoFrameCallback((now, metadata) => { draw(metadata.mediaTime); queueFrame(); });
  }
  if ("requestVideoFrameCallback" in video) queueFrame();
  else video.addEventListener("timeupdate", () => draw());
  video.addEventListener("loadeddata", () => draw());
  video.addEventListener("seeked", () => draw());
  video.addEventListener("play", () => { wanted = true; updatePlayState(); });
  video.addEventListener("pause", () => {
    if (managedPause) managedPause = false;
    else wanted = false;
    updatePlayState();
  });
  video.addEventListener("error", () => {
    panel.dataset.mediaError = "true";
    label.textContent = "Video preview unavailable";
    play.disabled = true;
  });
  function seek(index) { video.currentTime = (Math.max(0, Math.min(frameCount - 1, index)) + 0.001) / fps; }
  slider.addEventListener("input", () => { wanted = false; pauseManaged(); seek(Number(slider.value)); });
  previous.addEventListener("click", () => { wanted = false; pauseManaged(); seek(frame - 1); });
  next.addEventListener("click", () => { wanted = false; pauseManaged(); seek(frame + 1); });
  play.addEventListener("click", async () => {
    wanted = video.paused;
    if (!wanted) video.pause();
    else try { await video.play(); } catch { label.textContent = "Press Play to start the video"; }
  });
  function loadSource(src, time = 0) {
    const request = ++sourceRequest;
    pauseManaged(); video.src = src;
    applySpeed();
    video.addEventListener("loadeddata", async () => {
      if (disposed || request !== sourceRequest) return;
      if (time > 0) video.currentTime = Math.min(time, (frameCount - 1) / fps);
      else draw();
      resume();
    }, {once: true});
    video.load();
  }
  panel.uggSync = {
    pause() { wanted = false; video.pause(); },
    setVisible(value) {
      visible = value; cameraViewer?.setVisible(value && !poseInset?.hidden);
      if (!value) pauseManaged(); else resume();
    },
    dispose() {
      disposed = true; visible = false; pauseManaged();
      if (callbackId !== undefined) video.cancelVideoFrameCallback(callbackId);
      motion.removeEventListener("change", motionChange); cameraViewer?.dispose();
      video.removeAttribute("src"); video.load();
    },
    snapshot() { return { frame, time: video.currentTime, paused: video.paused, wanted, visible,
      speed: Number(speed.value), playback_fps: fps * video.playbackRate, camera: cameraViewer?.snapshot() }; },
  };
  if (hasCamera) {
    try {
      const response = await fetch(example.poses);
      if (!response.ok) throw new Error("Camera data unavailable");
      const data = await response.json();
      if (data.frame_count !== frameCount || data.fps !== fps) throw new Error("Camera and video timelines differ");
      const { createCameraViewer } = await import("./camera-viewer.js");
      cameraViewer = createCameraViewer(poseInset || stage, data, { single: nvsMode });
      cameraViewer.setRotate(rotate.checked);
      cameraViewer.setOrientations(orientations.checked);
      cameraViewer.setVisible(visible);
      cameraViewer.setFrame(frame);
    } catch (error) {
      panel.dataset.viewerError = String(error);
      (poseInset || stage).prepend(element("p", "result-error", nvsMode
        ? "3D camera preview requires WebGL."
        : hasInput
        ? "Interactive camera views require WebGL. The input video and timeline are available."
        : "Interactive camera views require WebGL. The timeline and trajectory video are available."));
    }
  }
  loadSource(cameraMode ? example.input_video || example.clock_video : example.views[example.default_view].src);
  updatePlayState();
  panel.dataset.syncReady = "true";
}
