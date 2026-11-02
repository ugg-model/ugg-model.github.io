"""Import metric-ranked release galleries without changing the source tree.

Run on a verified CPU Slurm allocation in the documented wan environment.
Copies supplied renders, packs matched RGB with depth, and aligns camera poses
with one global Sim(3). Missing files are reported independently of usable views.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import math
from pathlib import Path
import re
import shutil
import subprocess
import threading

import cv2
import imageio_ffmpeg
import numpy as np
from PIL import Image

from prepare_sync_assets import similarity_alignment
from gallery_selection import select_cases

NAMES = {"dl3dv20": "DL3DV", "dl3dv_wide": "DL3DV Wide", "mip": "Mip-NeRF 360",
         "re10k128_50f": "RealEstate10K · 128 scenes", "re10k_c50": "RealEstate10K · 50 frames",
         "spatialvid": "Spatial Video", "bonn": "Bonn", "kitti": "KITTI", "sintel": "Sintel", "scannetpp": "ScanNet++"}
NOTE = "Oracle-selected against ground truth within a single release checkpoint. This does not represent ordinary test-time selection."


def metadata(path):
    capture = cv2.VideoCapture(str(path))
    result = {"frames": int(capture.get(cv2.CAP_PROP_FRAME_COUNT)),
              "fps": float(capture.get(cv2.CAP_PROP_FPS)),
              "width": int(capture.get(cv2.CAP_PROP_FRAME_WIDTH)),
              "height": int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))}
    ok, frame = capture.read()
    capture.release()
    if not ok or min(result.values()) <= 0 or not all(math.isfinite(v) for v in result.values()):
        raise ValueError("Video metadata or first frame is unavailable")
    return result


def same_timeline(a, b):
    return a["frames"] == b["frames"] and abs(a["fps"] - b["fps"]) < 1e-5


class Assets:
    def __init__(self, site):
        self.site = site
        self.root = site / "assets/release"
        self.root.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self.hashes = {}
        self.records = {}

    def digest(self, source):
        resolved = source.resolve()
        with self.lock:
            if resolved not in self.hashes:
                value = hashlib.sha256()
                with source.open("rb") as stream:
                    for block in iter(lambda: stream.read(1024 * 1024), b""):
                        value.update(block)
                self.hashes[resolved] = value.hexdigest()
            return self.hashes[resolved]

    def relative(self, path):
        return str(path.relative_to(self.site))

    def copy(self, source):
        key = self.digest(source)
        target = self.root / (key + source.suffix.lower())
        with self.lock:
            if not target.exists():
                temporary = target.with_suffix(target.suffix + ".tmp")
                shutil.copyfile(source, temporary)
                temporary.replace(target)
            self.records[self.relative(target)] = {"sha256": key, "bytes": target.stat().st_size, "kind": "copy"}
        return self.relative(target)

    def data(self, value):
        encoded = (json.dumps(value, separators=(",", ":"), allow_nan=False) + "\n").encode()
        key = hashlib.sha256(encoded).hexdigest()
        target = self.root / (key + ".json")
        with self.lock:
            target.write_bytes(encoded)
            self.records[self.relative(target)] = {"sha256": key, "bytes": len(encoded), "kind": "camera poses"}
        return self.relative(target)

    def poster(self, video):
        path = self.site / video
        key = self.digest(path)
        target = self.root / (key + ".jpg")
        with self.lock:
            if not target.exists():
                capture = cv2.VideoCapture(str(path))
                ok, frame = capture.read()
                capture.release()
                if not ok:
                    raise ValueError("Cannot decode poster frame")
                image = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
                image.thumbnail((480, 360), Image.Resampling.LANCZOS)
                image.save(target, quality=88)
            self.records[self.relative(target)] = {"sha256": self.digest(target), "bytes": target.stat().st_size, "kind": "poster"}
        return self.relative(target)

    def pack(self, left, right, resize_right=False):
        key = hashlib.sha256((self.digest(left) + self.digest(right) + str(resize_right) + ":h264-crf20-v1").encode()).hexdigest()
        target = self.root / (key + ".mp4")
        with self.lock:
            if not target.exists():
                info = metadata(left)
                transform = f"[1:v]scale={info['width']}:{info['height']}:flags=bicubic[r];[0:v][r]" if resize_right else "[0:v][1:v]"
                transform += "hstack=inputs=2:shortest=1,pad=ceil(iw/2)*2:ceil(ih/2)*2[v]"
                temporary = target.with_suffix(".tmp.mp4")
                subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-hide_banner", "-loglevel", "error", "-y",
                                "-threads", "1", "-i", str(left), "-threads", "1", "-i", str(right),
                                "-filter_complex_threads", "1", "-filter_complex", transform, "-map", "[v]", "-an",
                                "-c:v", "libx264", "-threads", "1", "-preset", "fast", "-crf", "20",
                                "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(temporary)], check=True)
                packed = metadata(temporary)
                if not same_timeline(info, packed) or packed["width"] != info["width"] * 2 or packed["height"] != info["height"]:
                    temporary.unlink()
                    raise ValueError("Packed video changed the source timeline or crop dimensions")
                temporary.replace(target)
            self.records[self.relative(target)] = {"sha256": self.digest(target), "bytes": target.stat().st_size, "kind": "packed video"}
        return self.relative(target)

    def depth_comparison(self, prediction, reference, rgb=None):
        sources = [prediction, reference] + ([rgb] if rgb else [])
        info = metadata(prediction)
        if metadata(reference) != info or (rgb and metadata(rgb)["frames"] != info["frames"]):
            raise ValueError("Depth comparison and RGB timelines differ")
        key = hashlib.sha256(("".join(self.digest(source) for source in sources) + ":depth-comparison-crf20-v1").encode()).hexdigest()
        target = self.root / (key + ".mp4")
        with self.lock:
            if not target.exists():
                transform = (f"[2:v]settb=AVTB,setpts=N/({info['fps']}*TB),scale={info['width']}:{info['height']}:flags=bicubic[r];[0:v][1:v][r]" if rgb else "[0:v][1:v]")
                transform += f"hstack=inputs={len(sources)}:shortest=1[v]"
                temporary = target.with_suffix(".tmp.mp4")
                inputs = [argument for source in sources for argument in ("-threads", "1", "-i", str(source))]
                subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-hide_banner", "-loglevel", "error", "-y", *inputs,
                                "-filter_complex_threads", "1", "-filter_complex", transform, "-map", "[v]", "-an",
                                "-r", str(info["fps"]), "-c:v", "libx264", "-threads", "1", "-preset", "fast", "-crf", "20",
                                "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(temporary)], check=True)
                packed = metadata(temporary)
                if not same_timeline(info, packed) or (packed["width"], packed["height"]) != (info["width"] * len(sources), info["height"]):
                    temporary.unlink()
                    raise ValueError(f"Depth comparison changed timeline or crop dimensions: {info} -> {packed}")
                temporary.replace(target)
            self.records[self.relative(target)] = {"sha256": self.digest(target), "bytes": target.stat().st_size, "kind": "packed depth comparison"}
        return self.relative(target)


def verified_rgb(case, rgb_root):
    """Verify every source pose frame before pairing outside-release ScanNet++ RGB."""
    sample = rgb_root / f"sample_{int(case.name.removeprefix('scene_')):05d}"
    gt_path = case / "gt_c2w.npy"
    if not gt_path.is_file():
        gt_path = (case / "pred_c2w.npy").resolve().with_name(case.name + "_gt_c2w.npy")
    gt = np.load(gt_path, allow_pickle=False).astype(np.float64)
    with np.load(sample / "gt_cameras.npz", allow_pickle=False) as data:
        cameras = data["extrinsics"].astype(np.float64)
    if not np.isfinite(gt).all() or not np.isfinite(cameras).all():
        raise ValueError("Recovered RGB correspondence contains non-finite poses")
    relative = np.linalg.inv(cameras[0]) @ cameras
    if relative.shape != gt.shape:
        raise ValueError("Recovered RGB and release pose frame counts differ")
    rotation_error = float(np.max(np.abs(relative[:, :3, :3] - gt[:, :3, :3])))
    x, y = relative[:, :3, 3], gt[:, :3, 3]
    variance = float(np.sum(x * x))
    if variance <= 1e-12:
        raise ValueError("Recovered RGB trajectory cannot establish positional correspondence")
    scale = float(np.sum(x * y) / variance)
    center_error = float(np.max(np.abs(scale * x - y)))
    if rotation_error >= 1e-5 or center_error >= 1e-3 or scale <= 0:
        raise ValueError("Recovered RGB does not match every release GT pose frame")
    rgb = sample / "gt_rgb.mp4"
    if metadata(rgb)["frames"] != len(gt):
        raise ValueError("Recovered RGB video and pose frame counts differ")
    return rgb, {"sample": sample.name, "rotation_error": rotation_error, "center_error": center_error, "scale": scale}


def nvs_camera_data(path, info):
    with np.load(path, allow_pickle=False) as data:
        matrices = data["extrinsics"].astype(np.float64)
    if matrices.shape != (info["frames"], 4, 4) or not np.isfinite(matrices).all():
        raise ValueError("NVS target cameras and RGB frame counts differ")
    rotations = matrices[:, :3, :3]
    np.testing.assert_allclose(rotations @ rotations.transpose(0, 2, 1), np.broadcast_to(np.eye(3), rotations.shape), atol=5e-3)
    np.testing.assert_allclose(np.linalg.det(rotations), 1, atol=5e-3)
    # Put the first target camera at the origin without changing relative poses.
    matrices = np.linalg.inv(matrices[0]) @ matrices
    return {"frame_count": len(matrices), "fps": info["fps"],
            "coordinate_convention": "OpenCV camera-to-world, relative to the first target frame.",
            "reference": [{"position": matrix[:3, 3].tolist(), "rotation": matrix[:3, :3].tolist()} for matrix in matrices]}


def public_metrics(value):
    keep = ("task", "dataset", "protocol", "ncf", "sample", "scene", "checkpoint", "member", "config", "psnr",
            "abs_rel", "delta1", "ate_m", "pool_size", "n_frames", "decode_percentile_clip", "depth_colour_range_m", "alignment", "align")
    return {key: value[key] for key in keep if key in value}


def camera_data(pred_path, gt_path, fps):
    pred = np.load(pred_path, allow_pickle=False).astype(np.float64)
    gt = np.load(gt_path, allow_pickle=False).astype(np.float64)
    if pred.shape != gt.shape or pred.ndim != 3 or pred.shape[1:] != (4, 4) or not len(pred):
        raise ValueError("Camera array shapes differ or are unsupported")
    if not np.isfinite(pred).all() or not np.isfinite(gt).all():
        raise ValueError("Camera arrays contain non-finite values")
    for matrices in (pred, gt):
        rotations = matrices[:, :3, :3]
        np.testing.assert_allclose(rotations @ rotations.transpose(0, 2, 1), np.broadcast_to(np.eye(3), rotations.shape), atol=5e-3)
        np.testing.assert_allclose(np.linalg.det(rotations), 1, atol=5e-3)
    try:
        scale, rotation, translation = similarity_alignment(pred[:, :3, 3], gt[:, :3, 3])
        kind = "One global Sim(3), fitted to corresponding camera centers."
    except ValueError:
        variance = np.sum((pred[:, :3, 3] - pred[:, :3, 3].mean(0)) ** 2) / len(pred)
        if variance >= 1e-12:
            raise
        scale, rotation = 1.0, np.eye(3)
        translation = gt[:, :3, 3].mean(0) - pred[:, :3, 3].mean(0)
        kind = "Translation only for a stationary predicted trajectory; scale/rotation are unidentifiable."
    aligned = pred.copy()
    aligned[:, :3, 3] = scale * (rotation @ pred[:, :3, 3].T).T + translation
    aligned[:, :3, :3] = rotation @ pred[:, :3, :3]
    before = pred[0, :3, :3].T @ pred[:, :3, :3]
    after = aligned[0, :3, :3].T @ aligned[:, :3, :3]
    np.testing.assert_allclose(before, after, atol=1e-9)
    np.testing.assert_allclose(aligned[:, :3, 3], scale * (rotation @ pred[:, :3, 3].T).T + translation, atol=1e-9)
    def serialize(matrices):
        return [{"position": matrix[:3, 3].tolist(), "rotation": matrix[:3, :3].tolist()} for matrix in matrices]
    return {"frame_count": len(gt), "fps": fps,
            "coordinate_convention": "OpenCV camera-to-world: x right, y down, z forward.",
            "alignment": {"type": kind, "scale": scale, "rotation": rotation.tolist(), "translation": translation.tolist()},
            "prediction": serialize(aligned), "reference": serialize(gt)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--run-dir", required=True, type=Path)
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--max-cases", type=int, default=72, help="Maximum cases per result task, balanced across datasets")
    parser.add_argument("--max-public-bytes", type=int, default=950_000_000)
    parser.add_argument("--use-original-nvs-poses", action="store_true")
    parser.add_argument("--scannet-rgb-root", type=Path)
    parser.add_argument("--prune-unused", action="store_true", help="Remove unreferenced generated assets only from assets/release")
    args = parser.parse_args()
    if args.workers < 1 or args.workers > 4:
        parser.error("Use 1–4 workers within the allocated CPU limit")
    if args.max_cases < 1:
        parser.error("--max-cases must be positive")
    site = Path(__file__).resolve().parents[1]
    args.run_dir.mkdir(parents=True, exist_ok=True)
    assets = Assets(site)
    manifest = json.loads((site / "examples.json").read_text())
    work = []
    for task in ("nvs", "depth", "pose"):
        for group in sorted((args.source / task).iterdir()):
            if group.is_dir():
                work.extend((task, group.name, case) for case in sorted(group.iterdir()) if case.is_dir())
    report = {"source": str(args.source), "cases": [], "assets": {}, "source_counts": {task: sum(item[0] == task for item in work) for task in ("nvs", "depth", "pose")}}
    catalog, catalog_metrics, selected_order = {"nvs": [], "depth": [], "camera": []}, {}, {}
    for task, group, case in work:
        source = str(case.relative_to(args.source))
        catalog_metrics[source] = json.loads((case / "metrics.json").read_text())
        catalog["camera" if task == "pose" else task].append({
            "id": re.sub(r"[^a-zA-Z0-9_-]", "-", group + "-" + case.name),
            "dataset": group.partition("__")[0], "source": source,
        })
    report["gallery_selection"] = {}
    selected_sources = set()
    for task, candidates in catalog.items():
        chosen, policy = select_cases(candidates, catalog_metrics, task, args.max_cases)
        selected_order[task] = [case["id"] for case in chosen]
        selected_sources.update(case["source"] for case in chosen)
        report["gallery_selection"][task] = policy
        report["cases"].extend({"source": case["source"], "id": case["id"], "status": "not_selected",
                                "metrics": public_metrics(catalog_metrics[case["source"]])}
                               for case in candidates if case["source"] not in selected_sources)
    work = [item for item in work if str(item[2].relative_to(args.source)) in selected_sources]

    def prepare(item):
        task, group, case = item
        source = str(case.relative_to(args.source))
        warnings, videos, paths, recovery = [], {}, {}, None
        metrics = catalog_metrics[source]
        expected = {"nvs": ("pred_rgb.mp4", "gt_rgb.mp4"),
                    "depth": ("pred_depth.mp4", "gt_depth.mp4", "gt_rgb.mp4"),
                    "pose": ("traj.mp4", "gt_rgb.mp4", "pred_c2w.npy", "gt_c2w.npy")}[task]
        for filename in expected:
            path = case / filename
            if not path.is_file():
                warnings.append({"file": filename, "reason": "Source symlink target is missing" if path.is_symlink() else "Not supplied in this release"})
        for filename in ("pred_rgb.mp4", "gt_rgb.mp4", "pred_depth.mp4", "gt_depth.mp4", "traj.mp4"):
            path = case / filename
            if filename == "gt_rgb.mp4" and not path.is_file() and group == "scannetpp" and args.scannet_rgb_root and task != "nvs":
                path, recovery = verified_rgb(case, args.scannet_rgb_root)
            if path.is_file():
                try:
                    videos[filename] = metadata(path)
                    paths[filename] = path
                except (OSError, ValueError) as exc:
                    warnings.append({"file": filename, "reason": str(exc)})
            elif path.is_symlink() and filename not in expected:
                warnings.append({"file": filename, "reason": "Source symlink target is missing"})
        if recovery:
            warnings = [warning for warning in warnings if warning["file"] != "gt_rgb.mp4" or "gt_rgb.mp4" not in videos]
        dataset, _, protocol = group.partition("__")
        protocol = protocol or "dense"
        scene = re.sub(r"^(sample_|scene_)", "", case.name).lstrip("0") or "0"
        short = ("Sample " if task == "nvs" else "Scene ") + scene if case.name.startswith(("sample_", "scene_")) else case.name.replace("rgbd_bonn_", "").replace("_", " ")
        conditioning = {"ncf1": "1 conditioning frame", "ncf2": "2 conditioning frames"}.get(protocol, "dense observations")
        example = {"id": re.sub(r"[^a-zA-Z0-9_-]", "-", group + "-" + case.name), "dataset": dataset,
                   "protocol": protocol, "source": source, "short_title": short,
                   "title": f"{NAMES.get(dataset, dataset)} · {short} · {conditioning}",
                   "selection": "Release model · " + conditioning, "note": NOTE,
                   "display_note": "", "views": {}, "autoplay": True}
        views = example["views"]
        def add_video(key, filename, label, description, src=None):
            if filename not in videos:
                return
            src = src or assets.copy(paths[filename])
            views[key] = {"label": label, "kind": "video", "src": src,
                          "poster": assets.poster(src), "description": description}
        if task == "nvs":
            if all(name in videos for name in ("pred_rgb.mp4", "gt_rgb.mp4")):
                a, b = videos["pred_rgb.mp4"], videos["gt_rgb.mp4"]
                if a == b:
                    src = assets.pack(paths["pred_rgb.mp4"], paths["gt_rgb.mp4"])
                    views["comparison"] = {"label": "Side by Side", "kind": "video", "src": src,
                                           "poster": assets.poster(src), "description": "UGG generated RGB on the left; reference RGB on the right.",
                                           "labels": ["UGG", "Ground truth"]}
                    example.update(kind="synchronized", task="nvs", has_input=False,
                                   frame_count=a["frames"], fps=a["fps"], width=a["width"] * 2, height=a["height"],
                                   clock_video=src, thumbnail=assets.poster(paths["gt_rgb.mp4"]))
                    if args.use_original_nvs_poses:
                        pose_path = paths["gt_rgb.mp4"].resolve().parent / "gt_cameras.npz"
                        example["poses"] = assets.data(nvs_camera_data(pose_path, a))
                else:
                    raise ValueError("NVS RGB dimensions or timelines differ")
            example["display_note"] = "Supplied target-camera poses; the highlighted camera corresponds to the video frame." if example.get("poses") else "Side-by-side RGB from the release model."
        elif task == "depth":
            primary = videos.get("pred_depth.mp4") or videos.get("gt_depth.mp4")
            depth_videos = [info for name, info in videos.items() if name in ("pred_depth.mp4", "gt_depth.mp4")]
            synchronized = bool(primary) and all(info == primary for info in depth_videos)
            input_info = videos.get("gt_rgb.mp4")
            matched_input = bool(synchronized and input_info and (same_timeline(primary, input_info) or (recovery and primary["frames"] == input_info["frames"])))
            if synchronized and all(name in videos for name in ("pred_depth.mp4", "gt_depth.mp4")):
                rgb = paths.get("gt_rgb.mp4") if matched_input else None
                src = assets.depth_comparison(paths["pred_depth.mp4"], paths["gt_depth.mp4"], rgb)
                views["comparison"] = {"label": "Side by Side", "kind": "video", "src": src,
                                       "poster": assets.poster(src), "description": "UGG depth on the left; ground-truth depth on the right.",
                                       "labels": ["UGG depth", "Ground truth"]}
            else:
                for key, filename, label in [("prediction", "pred_depth.mp4", "Predicted Depth"), ("reference", "gt_depth.mp4", "Reference Depth")]:
                    add_video(key, filename, label, label + " from the release result.")
                synchronized = False
            if synchronized:
                example.update(kind="synchronized", task="depth", has_input=matched_input,
                               frame_count=primary["frames"], fps=primary["fps"], width=primary["width"] * 2, height=primary["height"],
                               input_width=primary["width"], input_height=primary["height"])
            example["thumbnail"] = assets.poster(paths["gt_rgb.mp4"]) if input_info else "assets/rgb-unavailable.svg"
            example["thumbnail_kind"] = "rgb" if input_info else "unavailable"
            if input_info and not matched_input:
                warnings.append({"file": "gt_rgb.mp4", "reason": "RGB cannot share the depth clock; no overlay shown"})
                add_video("input", "gt_rgb.mp4", "Input RGB", "Available input RGB; its timeline does not match the depth renders.")
                example.pop("kind", None)
            elif not input_info:
                warnings.append({"file": "gt_rgb.mp4", "reason": "Matching input RGB is not supplied in this release"})
            example["display_note"] = "The supplied depth renders use the release visualization and alignment."
            if "pred_depth.mp4" not in videos:
                example["display_note"] += " Predicted depth is unavailable; the remaining views are shown."
        else:
            add_video("trajectory", "traj.mp4", "Trajectory Video", "UGG and ground-truth camera trajectories from the release result.")
            input_info = videos.get("gt_rgb.mp4")
            example["thumbnail"] = assets.poster(paths["gt_rgb.mp4"]) if input_info else "assets/rgb-unavailable.svg"
            example["thumbnail_kind"] = "rgb" if input_info else "unavailable"
            clock_name = "gt_rgb.mp4" if input_info else "traj.mp4"
            if clock_name in videos and (case / "pred_c2w.npy").is_file() and (case / "gt_c2w.npy").is_file():
                try:
                    info = videos[clock_name]
                    data = camera_data(case / "pred_c2w.npy", case / "gt_c2w.npy", info["fps"])
                    if data["frame_count"] != info["frames"]:
                        raise ValueError("Camera arrays and clock video have different frame counts")
                    poses = assets.data(data)
                    clock = assets.copy(paths[clock_name])
                    example.update(kind="synchronized", task="camera", has_input=bool(input_info),
                                   frame_count=data["frame_count"], fps=info["fps"], poses=poses, clock_video=clock,
                                   input_width=info["width"], input_height=info["height"])
                    if input_info:
                        example["input_video"] = clock
                    if "trajectory" in views:
                        example["trajectory_video"] = views["trajectory"]["src"]
                    views.clear()
                    views["comparison"] = {"label": "Side by Side", "kind": "camera", "src": poses,
                                           "description": "UGG and ground-truth camera positions and orientations."}
                    example["thumbnail"] = assets.poster(clock) if input_info else "assets/rgb-unavailable.svg"
                    example["thumbnail_kind"] = "rgb" if input_info else "unavailable"
                    example["display_note"] = data["alignment"]["type"] + " Frusta show orientation using a common glyph size."
                except (ValueError, AssertionError, OSError) as exc:
                    warnings.append({"file": "camera arrays", "reason": str(exc)})
            if not input_info:
                warnings.append({"file": "gt_rgb.mp4", "reason": "Matching input RGB is not supplied in this release"})
            elif example.get("kind") != "synchronized":
                add_video("input", "gt_rgb.mp4", "Input RGB", "Available input RGB from this release case.")
            if not example["display_note"]:
                example["display_note"] = "Available release videos; interactive camera data could not be paired with a video timeline."
        if not views:
            return None, {"source": source, "status": "unavailable", "warnings": warnings, "metrics": public_metrics(metrics)}
        example["default_view"] = "comparison" if "comparison" in views else next(iter(views))
        if "thumbnail" not in example:
            example["thumbnail"] = views.get("prediction", next(iter(views.values())))["poster"]
        if task == "pose" and example.get("kind") != "synchronized":
            example["default_view"] = "trajectory" if "trajectory" in views else next(iter(views))
        if metrics.get("pool_size"):
            example["selection"] += f" · pool {metrics['pool_size']}"
        return example, {"source": source, "status": "included", "id": example["id"], "warnings": warnings,
                         "metrics": public_metrics(metrics), "videos": videos, "rgb_recovery": recovery}

    prepared = {"nvs": [], "depth": [], "camera": []}
    def safe_prepare(item):
        try:
            return prepare(item)
        except Exception as exc:
            return None, {"source": str(item[2].relative_to(args.source)), "status": "failed", "error": str(exc)}
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        for item, (example, evidence) in zip(work, pool.map(safe_prepare, work)):
            report["cases"].append(evidence)
            if example:
                prepared["camera" if item[0] == "pose" else item[0]].append(example)
            print(json.dumps({"source": evidence["source"], "status": evidence["status"]}), flush=True)
    report["assets"] = assets.records
    report["included_counts"] = {task: len(cases) for task, cases in prepared.items()}
    (args.run_dir / "release-import-evidence.json").write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    if any(case["status"] == "failed" for case in report["cases"]):
        raise RuntimeError("Some case exports failed; inspect release-import-evidence.json and fix before publishing")
    if any(not cases for cases in prepared.values()):
        raise RuntimeError("One result task has no usable release cases")
    for task, cases in prepared.items():
        by_id = {case["id"]: case for case in cases}
        if set(by_id) != set(selected_order[task]):
            raise RuntimeError(f"Some selected {task} cases could not be exported; fix before publication")
        manifest[task] = {"cases": [by_id[case_id] for case_id in selected_order[task]],
                          "selection": report["gallery_selection"][task]}
    def references(value):
        if isinstance(value, str):
            return {value} if value.startswith("assets/release/") else set()
        if isinstance(value, dict):
            return set().union(*(references(item) for item in value.values()))
        if isinstance(value, list):
            return set().union(*(references(item) for item in value))
        return set()
    retained = references(manifest)
    unused = [path for path in assets.root.iterdir() if re.fullmatch(r"[0-9a-f]{64}\.(mp4|jpg|json)", path.name) and assets.relative(path) not in retained] if args.prune_unused else []
    report["removed_unused_assets"] = [assets.relative(path) for path in unused]
    report["public_asset_bytes"] = sum(path.stat().st_size for path in (site / "assets").rglob("*") if path.is_file()) - sum(path.stat().st_size for path in unused)
    if report["public_asset_bytes"] > args.max_public_bytes:
        raise RuntimeError("Public assets exceed the configured size budget; review export/storage choices before publication")
    target = site / "examples.json"
    temporary = target.with_suffix(".tmp.json")
    temporary.write_text(json.dumps(manifest, indent=2, allow_nan=False) + "\n")
    temporary.replace(target)
    for path in unused:
        path.unlink()
    report["assets"] = {key: value for key, value in assets.records.items() if key in retained}
    (args.run_dir / "release-import-evidence.json").write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    public = {"release": "release-oracle-chosen", "selection": NOTE, "counts": report["included_counts"],
              "source_counts": report["source_counts"], "gallery_selection": report["gallery_selection"],
              "frame_pairing": "The source release reports identical contig_first frame indices; paired videos were checked for equal frame counts and rates.",
              "cases": [{key: value for key, value in case.items() if key in ("source", "status", "id", "metrics")}
                        for case in report["cases"] if case["status"] == "included"],
              "nvs_camera_source": "Original target cameras beside the symlinked release RGB videos." if args.use_original_nvs_poses else "Not imported.",
              "rgb_recovery": [{"source": case["source"], **case["rgb_recovery"]} for case in report["cases"] if case.get("rgb_recovery")],
              "depth_frame_packing": "Predicted depth, reference depth, then optional matching RGB in one decoded frame. Verified recovered RGB is retimed by frame index to the depth render rate."}
    (assets.root / "provenance.json").write_text(json.dumps(public, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"status": "complete", "counts": report["included_counts"], "asset_bytes": report["public_asset_bytes"]}), flush=True)


if __name__ == "__main__":
    main()
