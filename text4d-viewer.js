import * as THREE from "three";
import {OrbitControls} from "./vendor/OrbitControls.js";
import {createCameraViewer} from "./camera-viewer.js";
import {firstFrameCamera, inverse3, unpackPointmaps, writePointmap} from "./text4d-geometry.js?view=first-frame-40&depth=f16";

function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text) node.textContent = text;
  return node;
}
function imageAt(url) {
  return new Promise((resolve, reject) => {
    const image = new Image();
    image.onload = () => resolve(image); image.onerror = () => reject(new Error("Preview unavailable"));
    image.src = url;
  });
}

export async function renderText4DExample(panel, example) {
  const abort = new AbortController();
  let visible = false, disposed = false, ready = false, wanted = !matchMedia("(prefers-reduced-motion: reduce)").matches;
  let info, data, sprites, renderer, scene, camera, orbit, geometry, material, observer, cameraViewer, defaultCamera;
  let cameraGlyph, glyphGeometry, glyphMaterial, pathGeometry, pathMaterial;
  let frame = -1, time = 0, previous = null, animationId, dirty = true, mode = "rgb";
  // Scenes whose camera travels publish a per-frame centre so the observer can
  // ride along; without it a one-frame-scale view leaves the cloud behind, and a
  // view wide enough to hold the whole path renders each frame as a speck.
  let followAnchor = null;
  const stage = element("div", "text4d-stage");
  const loading = element("div", "placeholder", "Loading the generated scene…");
  const inset = element("div", "text4d-inset"), selector = element("select");
  selector.setAttribute("aria-label", "Floating preview");
  for (const [value, title] of [["rgb", "RGB"], ["depth", "Depth"], ["camera", "Camera"]]) {
    const option = element("option", "", title); option.value = value; selector.append(option);
  }
  const insetBody = element("div", "text4d-inset-body"), preview = element("canvas");
  preview.width = 192; preview.height = 144; preview.setAttribute("role", "img");
  const cameraContainer = element("div", "text4d-camera"); cameraContainer.hidden = true;
  insetBody.append(preview, cameraContainer); inset.append(insetBody); stage.append(loading, inset);
  const bar = element("div", "timeline");
  const play = element("button", "", wanted ? "Pause" : "Play"); play.type = "button"; play.dataset.action = "play";
  const before = element("button", "frame-step", "‹"), after = element("button", "frame-step", "›");
  before.type = after.type = "button";
  before.setAttribute("aria-label", "Previous frame"); after.setAttribute("aria-label", "Next frame");
  const slider = element("input"); slider.type = "range"; slider.min = "0"; slider.max = "49"; slider.step = "1"; slider.value = "0";
  slider.setAttribute("aria-label", "Video frame");
  const frameLabel = element("output", "frame-label", "Frame 1 / 50");
  bar.append(play, before, slider, after, frameLabel);
  const options = element("div", "viewer-options"), speedLabel = element("label", "speed-control", "Speed");
  const speed = element("select"); speed.setAttribute("aria-label", "Playback speed");
  for (const rate of [0.5,1,2,4,8]) {
    const option = element("option", "", rate + "×"); option.value = String(rate); option.selected = rate === 1; speed.append(option);
  }
  speedLabel.append(speed);
  const reset = element("button", "reset-view", "Reset view"); reset.type = "button";
  const previewLabel = element("label", "speed-control", "Preview"); previewLabel.append(selector);
  options.append(speedLabel, reset, previewLabel);
  const prompt = element("p", "text4d-prompt");
  prompt.append(element("b", "", "Text prompt"), document.createTextNode(example.prompt));
  panel.replaceChildren(stage, bar, options, prompt);
  bar.querySelectorAll("button,input").forEach(node => {node.disabled = true;});
  selector.disabled = reset.disabled = speed.disabled = true;

  function drawPreview() {
    if (!ready || frame < 0) return;
    const cameraMode = mode === "camera";
    preview.hidden = cameraMode; cameraContainer.hidden = !cameraMode;
    if (cameraMode) {
      if (!cameraViewer) {
        const poses = info.c2w.map(pose => ({position:pose.slice(0,3).map(row => row[3]), rotation:pose.slice(0,3).map(row => row.slice(0,3))}));
        cameraViewer = createCameraViewer(cameraContainer, {frame_count:info.frame_count, reference:poses}, {single:true, singleLabel:"Generated camera"});
        cameraViewer.setRotate(false);
      }
      cameraViewer.setFrame(frame); cameraViewer.setPlaying(wanted); cameraViewer.setVisible(visible);
    } else {
      cameraViewer?.setVisible(false);
      const source = sprites[mode], s = info.sprites;
      preview.getContext("2d").drawImage(source, frame%s.columns*s.width, Math.floor(frame/s.columns)*s.height,
        s.width, s.height, 0, 0, preview.width, preview.height);
      preview.dataset.frame = String(frame);
      preview.setAttribute("aria-label", "Generated " + (mode === "rgb" ? "RGB" : "depth") + " at the current point-cloud frame");
    }
    inset.dataset.mode = mode; inset.dataset.frame = String(frame);
  }
  function paint(nextFrame, force = false) {
    if (!ready) return;
    if (nextFrame !== frame || force) {
      frame = nextFrame;
      const centres = info.frame_centers;
      if (centres && centres[frame]) {
        const next = new THREE.Vector3().fromArray(centres[frame]);
        if (followAnchor) {
          const shift = next.clone().sub(followAnchor);
          orbit.target.add(shift); camera.position.add(shift); orbit.update();
          dirty = true;
        }
        followAnchor = next;
      }
      const count = writePointmap(info, data, frame, geometry.attributes.position.array, geometry.attributes.color.array);
      geometry.attributes.position.needsUpdate = geometry.attributes.color.needsUpdate = true;
      geometry.setDrawRange(0, count);
      const inv = inverse3(info.intrinsics[frame]), scale = info.radius*0.06;
      const corners = [[0,0],[info.width,0],[info.width,info.height],[0,info.height]].map(([u,v]) => [
        (inv[0]*u+inv[1]*v+inv[2])*scale,
        (inv[3]*u+inv[4]*v+inv[5])*scale,
        (inv[6]*u+inv[7]*v+inv[8])*scale,
      ]);
      const vertices = [];
      corners.forEach((corner,i) => vertices.push(0,0,0,...corner,...corner,...corners[(i+1)%4]));
      const blend = amount => corners[0].map((value,i) => value*(1-amount)+corners[1][i]*amount);
      const peak = blend(0.5).map((value,i) => value + ((corners[0][i]+corners[1][i])-(corners[2][i]+corners[3][i]))*0.15);
      vertices.push(...blend(0.35),...peak,...peak,...blend(0.65));
      glyphGeometry.attributes.position.array.set(vertices);
      glyphGeometry.attributes.position.needsUpdate = true;
      cameraGlyph.matrix.set(...info.c2w[frame].flat());
      cameraGlyph.matrixWorldNeedsUpdate = true;
      renderer.domElement.dataset.frame = String(frame);
      renderer.domElement.dataset.points = String(count);
      slider.value = String(frame); frameLabel.textContent = "Frame " + (frame+1) + " / " + info.frame_count;
      drawPreview(); dirty = true;
    }
    if (visible && dirty) {renderer.render(scene, camera); dirty = false;}
  }
  function animate(now) {
    if (disposed || !visible || !ready) return;
    if (wanted && previous !== null) {
      time = (time + (now-previous)/1000*Number(speed.value)) % (info.frame_count/10);
    }
    previous = now;
    paint(Math.min(info.frame_count-1, Math.floor(time*10+1e-9)));
    animationId = requestAnimationFrame(animate);
  }
  function startClock() {
    cancelAnimationFrame(animationId); previous = null;
    if (visible && ready && !disposed) animationId = requestAnimationFrame(animate);
  }
  function seek(value) {
    if (!ready) return;
    wanted = false; play.textContent = "Play"; time = Math.max(0, Math.min(info.frame_count-1, value))/10;
    previous = null; cameraViewer?.setPlaying(false); paint(Math.round(time*10));
  }
  slider.addEventListener("input", () => seek(Number(slider.value)));
  before.addEventListener("click", () => seek(frame-1)); after.addEventListener("click", () => seek(frame+1));
  play.addEventListener("click", () => {
    wanted = !wanted; play.textContent = wanted ? "Pause" : "Play"; previous = null;
    cameraViewer?.setPlaying(wanted);
  });
  speed.addEventListener("change", () => {previous = null;});
  selector.addEventListener("change", () => {mode = selector.value; drawPreview();});
  function home() {
    if (!ready) return;
    const start = info.frame_centers?.[Math.max(frame, 0)];
    const shift = new THREE.Vector3();
    if (start) shift.fromArray(start).sub(new THREE.Vector3().fromArray(info.frame_centers[0]));
    orbit.target.fromArray(defaultCamera.look_at).add(shift);
    camera.position.fromArray(defaultCamera.position).add(shift);
    followAnchor = start ? new THREE.Vector3().fromArray(start) : null;
    orbit.update(); dirty = true; paint(Math.max(frame, 0));
  }
  reset.addEventListener("click", () => {home(); cameraViewer?.reset();});
  panel.uggPlayback = {
    setVisible(value) {
      visible = value; cameraViewer?.setVisible(value && mode === "camera");
      if (value && ready) {dirty = true; paint(frame);}
      startClock();
    },
    dispose() {
      disposed = true; visible = false; abort.abort(); cancelAnimationFrame(animationId);
      observer?.disconnect(); orbit?.dispose(); cameraViewer?.dispose(); geometry?.dispose(); material?.dispose();
      glyphGeometry?.dispose(); glyphMaterial?.dispose(); pathGeometry?.dispose(); pathMaterial?.dispose();
      renderer?.dispose(); renderer?.forceContextLoss(); data = sprites = null;
    },
    snapshot() {
      return {ready, frame, time, mode, visible, playing:wanted, speed:Number(speed.value),
        points:geometry?.drawRange.count, point_clouds:scene?.children.filter(item => item.isPoints).length,
        observer_position:camera?.position.toArray(), observer_target:orbit?.target.toArray(),
        observer_up:camera?.up.toArray(), observer_fov:camera?.fov, default_camera:defaultCamera,
        inset_frame:Number(inset.dataset.frame), camera:cameraViewer?.snapshot(),
        world_camera:cameraGlyph ? {frame,matrix:cameraGlyph.matrix.toArray(),trajectory_points:pathGeometry.attributes.position.count} : null,
        confidence_filter: info?.confidence_filter,
        rendered_frames:renderer?.info.render.frame};
    },
  };
  try {
    const response = await fetch(example.scene, {signal:abort.signal});
    if (!response.ok) throw new Error("Scene unavailable");
    info = await response.json();
    if (info.confidence_filter?.retained_fraction !== 0.95) throw new Error("Pointmap confidence metadata unavailable");
    const base = new URL(example.scene, document.baseURI);
    const [compressed, rgb, depth] = await Promise.all([
      fetch(new URL(info.payload, base), {signal:abort.signal}).then(response => {
        if (!response.ok) throw new Error("Pointmap unavailable");
        return response.arrayBuffer();
      }),
      imageAt(new URL(info.sprites.rgb, base)), imageAt(new URL(info.sprites.depth, base)),
    ]);
    const stream = new Blob([compressed]).stream().pipeThrough(new DecompressionStream("gzip"));
    data = unpackPointmaps(await new Response(stream).arrayBuffer(), info);
    if (disposed) return;
    sprites = {rgb, depth};
    defaultCamera = firstFrameCamera(info, data);
    renderer = new THREE.WebGLRenderer({antialias:true});
    renderer.setPixelRatio(Math.min(devicePixelRatio, 2)); renderer.outputColorSpace = THREE.SRGBColorSpace;
    const canvas = renderer.domElement; canvas.className = "text4d-cloud"; canvas.tabIndex = 0;
    canvas.setAttribute("role", "img"); canvas.setAttribute("aria-label", "Generated current-frame colored point cloud. Drag to orbit, scroll to zoom.");
    stage.prepend(canvas);
    scene = new THREE.Scene(); scene.background = new THREE.Color(0xf7f7f9);
    camera = new THREE.PerspectiveCamera(48, 1, info.radius*0.001, (info.extent_radius || info.radius)*100);
    camera.up.fromArray(defaultCamera.up);
    orbit = new OrbitControls(camera, canvas); orbit.enableDamping = false;
    orbit.minDistance = info.radius*0.02; orbit.maxDistance = info.radius*20; orbit.listenToKeyEvents(canvas);
    const capacity = info.grid_width*info.grid_height;
    geometry = new THREE.BufferGeometry();
    geometry.setAttribute("position", new THREE.BufferAttribute(new Float32Array(capacity*3),3).setUsage(THREE.DynamicDrawUsage));
    geometry.setAttribute("color", new THREE.BufferAttribute(new Float32Array(capacity*3),3).setUsage(THREE.DynamicDrawUsage));
    material = new THREE.PointsMaterial({vertexColors:true, size:2, sizeAttenuation:false});
    const cloud = new THREE.Points(geometry, material); cloud.frustumCulled = false; scene.add(cloud);
    pathGeometry = new THREE.BufferGeometry().setFromPoints(info.c2w.map(pose => new THREE.Vector3(pose[0][3],pose[1][3],pose[2][3])));
    pathMaterial = new THREE.LineBasicMaterial({color:0xe6a000});
    scene.add(new THREE.Line(pathGeometry,pathMaterial));
    glyphGeometry = new THREE.BufferGeometry().setAttribute("position",new THREE.BufferAttribute(new Float32Array(60),3).setUsage(THREE.DynamicDrawUsage));
    glyphMaterial = new THREE.LineBasicMaterial({color:0xef594e});
    cameraGlyph = new THREE.LineSegments(glyphGeometry,glyphMaterial);
    cameraGlyph.matrixAutoUpdate = false; cameraGlyph.frustumCulled = false; scene.add(cameraGlyph);
    orbit.addEventListener("change", () => {dirty = true; if (visible && frame >= 0) paint(frame);});
    canvas.addEventListener("keydown", event => {if (event.key === "Home") {event.preventDefault(); home();}});
    const resize = () => {
      if (!stage.clientWidth || !stage.clientHeight) return;
      renderer.setSize(stage.clientWidth, stage.clientHeight, false);
      camera.aspect = stage.clientWidth/stage.clientHeight;
      camera.fov = THREE.MathUtils.radToDeg(2*Math.atan(Math.max(
        Math.tan(defaultCamera.fov/2), Math.tan(defaultCamera.horizontal_fov/2)/camera.aspect)));
      camera.updateProjectionMatrix();
      if (!ready) return;
      if (frame < 0) home();
      dirty = true; paint(frame < 0 ? 0 : frame);
    };
    ready = true; slider.max = String(info.frame_count-1);
    resize(); observer = new ResizeObserver(resize); observer.observe(stage);
    bar.querySelectorAll("button,input").forEach(node => {node.disabled = false;});
    selector.disabled = reset.disabled = speed.disabled = false;
    panel.dataset.text4dReady = "true"; loading.remove(); startClock();
  } catch (error) {
    if (disposed) return;
    panel.uggPlayback.dispose();
    throw error;
  }
}
