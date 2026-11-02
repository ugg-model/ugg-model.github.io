"""Prepare matched RGB/depth frames and globally aligned camera poses for the page."""
import argparse
import json
import shutil
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

from media_utils import colors, encode_frames, sha256


def similarity_alignment(pred, gt):
    """One proper Sim(3) transform mapping all predicted camera centers to GT."""
    x, y = pred.mean(axis=0), gt.mean(axis=0)
    xc, yc = pred - x, gt - y
    u, singular, vt = np.linalg.svd(yc.T @ xc / len(pred))
    signs = np.ones(3)
    signs[-1] = np.sign(np.linalg.det(u @ vt))
    rotation = u @ np.diag(signs) @ vt
    variance = np.sum(xc * xc) / len(pred)
    if variance < 1e-12:
        raise ValueError("Cannot align a degenerate camera trajectory")
    scale = float(np.dot(singular, signs) / variance)
    translation = y - scale * rotation @ x
    if scale <= 0 or not np.isclose(np.linalg.det(rotation), 1, atol=1e-8):
        raise ValueError("Alignment must be a positive-scale, proper similarity transform")
    return scale, rotation, translation


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--curated", type=Path, required=True)
    parser.add_argument("--rgb-sample", type=Path, required=True)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--three-package", type=Path, help="Optional npm package to refresh the vendored renderer")
    parser.add_argument("--scene", default="scene_0")
    parser.add_argument("--prefix", default="", help="Filename prefix for an additional gallery case")
    args = parser.parse_args()
    site = Path(__file__).resolve().parents[1]
    assets = site / "assets"
    args.run_dir.mkdir(parents=True, exist_ok=True)
    depth = args.curated / "depth/scannetpp__dense" / args.scene
    pose = args.curated / "pose/scannetpp__dense" / args.scene
    def asset(name):
        return assets / (args.prefix + name)
    gt = np.load(pose / "gt_c2w.npy", allow_pickle=False)
    pred = np.load(pose / "pred_c2w.npy", allow_pickle=False)
    depth_gt_poses = np.load(depth / "gt_c2w.npy", allow_pickle=False)
    np.testing.assert_array_equal(gt, depth_gt_poses)
    with np.load(args.rgb_sample / "gt_cameras.npz", allow_pickle=False) as data:
        rgb_gt_poses = data["extrinsics"].astype(np.float64)
    rgb_relative = np.linalg.inv(rgb_gt_poses[0]) @ rgb_gt_poses
    if rgb_relative.shape != gt.shape:
        raise ValueError("RGB and selected pose frame counts differ")
    rotation_error = float(np.max(np.abs(rgb_relative[:, :3, :3] - gt[:, :3, :3])))
    if rotation_error > 1e-5:
        raise ValueError("The RGB video is not the selected pose frame sequence")
    x, y = rgb_relative[:, :3, 3], gt[:, :3, 3]
    gt_scale = float(np.sum(x * y) / np.sum(x * x))
    translation_error = float(np.max(np.abs(gt_scale * x - y)))
    if translation_error > 1e-3:
        raise ValueError("RGB and selected poses do not share a normalized trajectory")

    capture = cv2.VideoCapture(str(args.rgb_sample / "gt_rgb.mp4"))
    fps = float(capture.get(cv2.CAP_PROP_FPS))
    frames = []
    while True:
        ok, frame = capture.read()
        if not ok:
            break
        frames.append(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
    capture.release()
    if len(frames) != len(gt) or fps <= 0:
        raise ValueError("RGB decoding did not yield every selected frame")
    rgb = np.stack(frames)
    norm = np.squeeze(np.load(depth / "pred_depth_norm.npy", allow_pickle=False))
    gt_depth = np.squeeze(np.load(depth / "gt_depth.npy", allow_pickle=False))
    if norm.shape != gt_depth.shape or norm.shape[0] != len(rgb):
        raise ValueError("Depth and RGB frames differ")
    height, width = norm.shape[1:]
    resized_rgb = np.stack([np.asarray(Image.fromarray(frame).resize((width, height), Image.Resampling.BICUBIC)) for frame in rgb])
    predicted = colors(np.clip(norm * 0.5 + 0.5, 0, 1))
    valid = np.isfinite(gt_depth) & (gt_depth > 0)
    inverse_gt = np.divide(1, gt_depth, out=np.zeros_like(gt_depth), where=valid)
    low, high = np.percentile(inverse_gt[valid], [2, 98])
    reference = colors(np.clip((inverse_gt - low) / max(high - low, 1e-8), 0, 1))
    reference[~valid] = 0
    for label, depth_frames in [("prediction", predicted), ("reference", reference)]:
        # A single decoded frame contains both depth and matching RGB; no dual video clocks.
        packed = np.concatenate([depth_frames, resized_rgb], axis=2)
        destination = asset(f"depth-sync-{label}.mp4")
        temporary = destination.with_suffix(".tmp.mp4")
        encode_frames(packed, temporary, fps=fps)
        temporary.replace(destination)
        Image.fromarray(depth_frames[0]).save(asset(f"depth-{label}.png"))
    rgb_destination = asset("input-rgb.mp4")
    shutil.copyfile(args.rgb_sample / "gt_rgb.mp4", rgb_destination)
    Image.fromarray(rgb[0]).save(asset("input-rgb.png"))

    scale, rotation, translation = similarity_alignment(pred[:, :3, 3], gt[:, :3, 3])
    aligned = pred.copy()
    aligned[:, :3, 3] = scale * (rotation @ pred[:, :3, 3].T).T + translation
    aligned[:, :3, :3] = rotation @ pred[:, :3, :3]
    # A constant alignment must preserve every relative camera rotation.
    before = pred[:-1, :3, :3].transpose(0, 2, 1) @ pred[1:, :3, :3]
    after = aligned[:-1, :3, :3].transpose(0, 2, 1) @ aligned[1:, :3, :3]
    np.testing.assert_allclose(before, after, atol=1e-12, rtol=1e-12)
    np.testing.assert_allclose(aligned[:, :3, 3], scale * (rotation @ pred[:, :3, 3].T).T + translation, atol=1e-12)
    synthetic = np.array([[0,0,0],[1,0,0],[0,1,0],[0,0,1]], dtype=float)
    test_rotation = np.array([[0,-1,0],[1,0,0],[0,0,1]], dtype=float)
    test_scale, test_r, test_t = similarity_alignment(synthetic, 2.5 * (test_rotation @ synthetic.T).T + [3,4,5])
    np.testing.assert_allclose(test_scale, 2.5, atol=1e-12)
    np.testing.assert_allclose(test_r, test_rotation, atol=1e-12)
    np.testing.assert_allclose(test_t, [3,4,5], atol=1e-12)
    def serialize(poses):
        return [{"position": matrix[:3, 3].tolist(), "rotation": matrix[:3, :3].tolist()} for matrix in poses]
    camera = {
        "frame_count": len(gt), "fps": fps,
        "coordinate_convention": "OpenCV camera-to-world: x right, y down, z forward.",
        "alignment": {"type": "One global Sim(3), fitted to all corresponding camera centers.",
                      "scale": scale, "rotation": rotation.tolist(), "translation": translation.tolist()},
        "prediction": serialize(aligned), "reference": serialize(gt),
    }
    asset("camera-poses.json").write_text(json.dumps(camera, separators=(",", ":")) + "\n")
    evidence = {
        "rgb_source": str(args.rgb_sample / "gt_rgb.mp4"),
        "rgb_sha256": sha256(rgb_destination), "frame_count": len(rgb), "fps": fps,
        "rgb_resolution": list(rgb.shape[1:3]), "depth_resolution": [height, width],
        "depth_packing": "Each frame: selected depth on left, corresponding RGB on right. One decoder draws both canvases.",
        "gt_rotation_max_difference": rotation_error,
        "gt_normalization_scale": gt_scale, "gt_position_max_difference": translation_error,
        "depth_pose_gt_identical": True,
        "alignment": camera["alignment"],
        "relative_rotation_preservation_max_error": float(np.max(np.abs(before-after))),
        "synthetic_alignment_check": "passed",
        "frustum_display": "Fixed-size orientation glyphs, not calibrated field-of-view visualization.",
    }
    (args.run_dir / (args.prefix + "sync-asset-evidence.json")).write_text(json.dumps(evidence, indent=2) + "\n")
    public = {"frame_count": len(gt), "fps": fps,
              "rgb_source": f"rescued evaluation/depthpose/scannetpp/{args.rgb_sample.name}/gt_rgb.mp4",
              "frame_correspondence": "Verified all-frame relative GT rotations and normalized camera centers; depth and camera GT poses identical.",
              "depth_clock": "Depth and input RGB packed into a single video frame for synchronized canvas rendering.",
              "camera_alignment": camera["alignment"],
              "frustum_display": evidence["frustum_display"]}
    public["curated_sources"] = {task: str(path.relative_to(args.curated)) for task, path in [("depth", depth), ("camera", pose)]}
    public["selection"] = "Provisional ground-truth oracle-selected examples."
    for task, path in [("depth", depth), ("camera", pose)]:
        member = (path / "MEMBER.txt").read_text()
        (args.run_dir / (args.prefix + task + "-MEMBER.txt")).write_text(member)
    asset("sync-provenance.json").write_text(json.dumps(public, indent=2) + "\n")
    vendor = site / "vendor"
    vendor.mkdir(exist_ok=True)
    if args.three_package:
        for name in ["three.module.js", "three.core.js"]:
            shutil.copyfile(args.three_package / "build" / name, vendor / name)
        shutil.copyfile(args.three_package / "examples/jsm/controls/OrbitControls.js", vendor / "OrbitControls.js")
        shutil.copyfile(args.three_package / "LICENSE", vendor / "THREE-LICENSE.txt")
        version = json.loads((args.three_package / "package.json").read_text())["version"]
        (vendor / "README.txt").write_text(f"Three.js {version}, vendored from its npm package. MIT license in THREE-LICENSE.txt.\n")
    else:
        version = "existing vendored renderer"
    print(json.dumps({"status": "complete", "fps": fps, "frames": len(rgb), "three_version": version,
                      "evidence": str(args.run_dir / (args.prefix + "sync-asset-evidence.json"))}, indent=2))


if __name__ == "__main__":
    main()
