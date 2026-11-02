import * as THREE from "three";
import { OrbitControls } from "./vendor/OrbitControls.js";

// Every camera-to-world rotation is applied directly; frusta are orientation glyphs.
function poseMatrix(pose) {
  const r = pose.rotation, p = pose.position;
  return new THREE.Matrix4().set(
    r[0][0], r[0][1], r[0][2], p[0],
    r[1][0], r[1][1], r[1][2], p[1],
    r[2][0], r[2][1], r[2][2], p[2], 0, 0, 0, 1);
}

function frustumGeometry(length) {
  const w = length * 0.52, h = w * 0.75;
  const corners = [[-w,-h,length], [w,-h,length], [w,h,length], [-w,h,length]];
  const positions = [];
  corners.forEach((corner, i) => {
    positions.push(0,0,0, ...corner, ...corner, ...corners[(i + 1) % 4]);
  });
  // The triangle marks the top of the camera, making roll visible.
  positions.push(-w * 0.4, -h, length, 0, -h * 1.5, length,
                 0, -h * 1.5, length, w * 0.4, -h, length);
  return new THREE.BufferGeometry().setAttribute("position", new THREE.Float32BufferAttribute(positions, 3));
}

export function createCameraViewer(container, data, { single = false, singleLabel = "Target camera" } = {}) {
  const grid = document.createElement("div");
  grid.className = single ? "camera-grid camera-grid-single" : "camera-grid";
  container.append(grid);
  const definitions = single
    ? [[0, data.reference, singleLabel, 0x2e9c5b]]
    : [[0, data.prediction, "UGG prediction", 0x3b63c7], [1, data.reference, "Ground truth", 0x2e9c5b]];
  const points = definitions.flatMap(([, poses]) => poses.map(pose => new THREE.Vector3(...pose.position)));
  const bounds = new THREE.Box3().setFromPoints(points);
  const center = bounds.getCenter(new THREE.Vector3());
  const radius = Math.max(bounds.getSize(new THREE.Vector3()).length() / 2, 0.05);
  const views = [];
  let leader = 0, syncing = false, visible = false, playing = false, rotating = true, dirty = true;
  let previous = performance.now(), currentFrame = 0, animationId, disposed = false;
  for (const [index, poses, label, color] of definitions) {
    const cell = document.createElement("div");
    cell.className = "camera-cell";
    const title = document.createElement("div");
    title.className = "camera-view-label";
    title.textContent = label;
    cell.append(title);
    grid.append(cell);
    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    const canvas = renderer.domElement;
    canvas.setAttribute("role", "img");
    canvas.setAttribute("aria-label", label + ": frame positions, orientations, and animated current camera");
    canvas.dataset.camera = single || index === 1 ? "reference" : "prediction";
    canvas.tabIndex = 0;
    cell.append(canvas);
    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0xf7f7f9);
    const camera = new THREE.PerspectiveCamera(48, 1, radius * 0.001, radius * 80);
    camera.up.set(0, -1, 0); // OpenCV world from the first camera: +y points down.
    const controls = new OrbitControls(camera, canvas);
    controls.target.copy(center);
    controls.enableDamping = false;
    controls.minDistance = radius * 0.3;
    controls.maxDistance = radius * 20;
    controls.autoRotateSpeed = 0.6;
    controls.listenToKeyEvents(canvas);
    const geometry = new THREE.BufferGeometry().setFromPoints(poses.map(pose => new THREE.Vector3(...pose.position)));
    scene.add(new THREE.Line(geometry, new THREE.LineBasicMaterial({ color, transparent: true, opacity: 0.65 })));
    const dot = document.createElement("canvas"); dot.width = dot.height = 32;
    const context = dot.getContext("2d");
    context.fillStyle = "#fff"; context.beginPath(); context.arc(16, 16, 13, 0, Math.PI * 2); context.fill();
    scene.add(new THREE.Points(geometry, new THREE.PointsMaterial({
      color, size: radius * 0.032, sizeAttenuation: true, map: new THREE.CanvasTexture(dot),
      transparent: true, alphaTest: 0.2, depthWrite: false,
    })));
    const ghostGeometry = frustumGeometry(radius * 0.055);
    const ghostMaterial = new THREE.LineBasicMaterial({ color, transparent: true, opacity: 0.24 });
    const ghosts = new THREE.Group();
    poses.forEach(pose => {
      const ghost = new THREE.LineSegments(ghostGeometry, ghostMaterial);
      ghost.matrixAutoUpdate = false;
      ghost.matrix.copy(poseMatrix(pose));
      ghosts.add(ghost);
    });
    scene.add(ghosts);
    const active = new THREE.Group();
    active.matrixAutoUpdate = false;
    active.add(new THREE.LineSegments(frustumGeometry(radius * 0.19), new THREE.LineBasicMaterial({ color: 0xe6a000 })));
    active.add(new THREE.AxesHelper(radius * 0.13));
    active.add(new THREE.Mesh(new THREE.SphereGeometry(radius * 0.026, 12, 8), new THREE.MeshBasicMaterial({ color: 0xe6a000 })));
    scene.add(active);
    const floor = new THREE.GridHelper(radius * 3.5, 12, 0xa7aeb9, 0xc9cdd4);
    floor.position.set(center.x, bounds.max.y + radius * 0.18, center.z);
    floor.material.transparent = true;
    floor.material.opacity = 0.22;
    scene.add(floor);
    const view = { poses, canvas, cell, renderer, scene, camera, controls, active, ghosts, fitted: false };
    view.home = () => {
      const halfAngle = Math.min(THREE.MathUtils.degToRad(camera.fov / 2),
        Math.atan(Math.tan(THREE.MathUtils.degToRad(camera.fov / 2)) * camera.aspect));
      const distance = radius / Math.sin(halfAngle) * 1.2;
      camera.position.copy(center).add(new THREE.Vector3(1.2,-0.85,-1.5).normalize().multiplyScalar(distance));
      controls.target.copy(center);
      controls.update();
      controls.saveState();
      dirty = true;
    };
    views.push(view);
    controls.addEventListener("start", () => { leader = index; });
    controls.addEventListener("change", () => {
      dirty = true;
      if (syncing) return;
      syncing = true;
      views.forEach(other => {
        if (other === view) return;
        other.camera.position.copy(camera.position);
        other.camera.quaternion.copy(camera.quaternion);
        other.controls.target.copy(controls.target);
        other.controls.update();
      });
      syncing = false;
    });
    const resize = () => {
      const width = cell.clientWidth, height = cell.clientHeight;
      if (!width || !height) return;
      renderer.setSize(width, height, false);
      const previousAspect = camera.aspect;
      camera.aspect = width / height;
      camera.updateProjectionMatrix();
      if (!view.fitted) {
        view.home();
        view.fitted = true;
      } else if (index === leader && Math.abs(previousAspect - camera.aspect) > 0.001) {
        const angle = aspect => Math.min(THREE.MathUtils.degToRad(camera.fov / 2),
          Math.atan(Math.tan(THREE.MathUtils.degToRad(camera.fov / 2)) * aspect));
        const factor = Math.sin(angle(previousAspect)) / Math.sin(angle(camera.aspect));
        camera.position.sub(controls.target).multiplyScalar(factor).add(controls.target);
        controls.update();
      }
      dirty = true;
    };
    const observer = new ResizeObserver(resize);
    observer.observe(cell);
    view.observer = observer;
    view.resize = resize;
    canvas.addEventListener("keydown", event => {
      if (event.key === "Home") { event.preventDefault(); view.home(); }
    });
  }
  const setFrame = frame => {
    currentFrame = Math.max(0, Math.min(data.frame_count - 1, frame));
    views.forEach(view => {
      view.active.matrix.copy(poseMatrix(view.poses[currentFrame]));
      view.active.matrixWorldNeedsUpdate = true;
      view.canvas.dataset.frame = String(currentFrame);
    });
    dirty = true;
  };
  setFrame(0);
  function animate(now) {
    if (disposed) return;
    const dt = Math.min((now - previous) / 1000, 0.1); previous = now;
    if (visible) {
      const controls = views[leader].controls;
      controls.autoRotate = playing && rotating;
      if (controls.autoRotate) { controls.update(dt); dirty = true; }
      if (dirty) {
        views.forEach(view => view.renderer.render(view.scene, view.camera));
        dirty = false;
      }
    }
    animationId = requestAnimationFrame(animate);
  }
  animationId = requestAnimationFrame(animate);
  return {
    setFrame,
    setPlaying(value) { playing = value; },
    setVisible(value) { visible = value; if (value) { views.forEach(view => view.resize()); dirty = true; } },
    setRotate(value) { rotating = value; },
    setOrientations(value) { views.forEach(view => { view.ghosts.visible = value; }); dirty = true; },
    reset() { views[leader].home(); },
    dispose() {
      disposed = true; visible = false; cancelAnimationFrame(animationId);
      const resources = new Set();
      views.forEach(view => {
        view.observer.disconnect(); view.controls.dispose();
        view.scene.traverse(object => {
          if (object.geometry) resources.add(object.geometry);
          for (const material of Array.isArray(object.material) ? object.material : [object.material]) {
            if (!material) continue;
            if (material.map) resources.add(material.map);
            resources.add(material);
          }
        });
        view.renderer.dispose(); view.renderer.forceContextLoss();
      });
      resources.forEach(resource => resource.dispose()); grid.remove();
    },
    snapshot() {
      return { frame: currentFrame, views: views.map(view => ({
        active_matrix: view.active.matrix.toArray(), observer_position: view.camera.position.toArray(),
        observer_target: view.controls.target.toArray(), frame_points: view.poses.length,
        orientation_markers: view.ghosts.children.length, rendered_frames: view.renderer.info.render.frame,
        projected_centers: view.poses.map(pose => new THREE.Vector3(...pose.position).project(view.camera).toArray()),
      })) };
    },
  };
}
