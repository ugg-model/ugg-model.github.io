"""Export RGB sprites verified against each existing reconstruction recording.

Run on a task CPU allocation. The point clouds are preserved; RGB is accepted
only after matching all recorded point/color buffers and projecting those points
back onto their original RGB frame pixels.
"""
import argparse
import base64
import hashlib
import json
import re
from pathlib import Path

import cv2
import msgspec
import numpy as np
import zstandard
from PIL import Image

CASES = {
    "scannetpp-scene44": ("scannetpp_scene44.html", "scannetpp_scene_44.npz", "scannetpp__dense/scene_44"),
    "bonn-person-tracking2": ("bonn_person_tracking2.html", "bonn_release_person_tracking2.npz", "bonn__dense/rgbd_bonn_person_tracking2"),
    "kitti-drive0095": ("kitti_drive0095.html", "kitti_release_drive0095.npz", "kitti__dense/2011_09_26_drive_0095_sync_02"),
}


def recording(path):
    payload = base64.b64decode(re.search(r'window\.__VISER_EMBED_DATA__="([^"]+)"', path.read_text()).group(1))
    raw = zstandard.ZstdDecompressor().decompress(payload[8:], max_output_size=int.from_bytes(payload[:8], "little"))
    length = int.from_bytes(raw[:8], "little")
    data = msgspec.msgpack.decode(raw[8:8 + length])
    offsets, offset = [], 8 + length
    for size in data["binaryBufferLengths"]:
        offset += (8 - offset % 8) % 8
        offsets.append(offset)
        offset += size

    def buffer(prop):
        index = prop["__binary_index"]
        start = offsets[index]
        return raw[start:start + data["binaryBufferLengths"][index]]

    clouds = [(time, message) for time, message in data["messages"] if message["type"] == "PointCloudMessage" and message["name"] == "/cloud"]
    return data, clouds, buffer


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pointcloud-root", type=Path, required=True)
    parser.add_argument("--curated-root", type=Path, required=True, help="Original RGB frames used to color the existing reconstruction exports")
    parser.add_argument("--run-dir", type=Path, required=True)
    args = parser.parse_args()
    root = Path.cwd()
    manifest = json.loads((root / "examples.json").read_text())
    evidence = {"cases": [], "status": "pending"}
    args.run_dir.mkdir(parents=True, exist_ok=True)
    for case in manifest["reconstruction"]["cases"]:
        html_name, npz_name, original_case = CASES[case["id"]]
        html_path = root / "assets/viser" / html_name
        data, clouds, buffer = recording(html_path)
        with np.load(args.pointcloud_root / npz_name, allow_pickle=False) as source:
            counts, points, colors, poses, intrinsics = [source[key] for key in ("counts", "points", "colors", "c2w", "K")]
        assert len(clouds) == len(counts) == 50
        times = [time for time, _ in clouds]
        assert np.allclose(times, np.arange(50) / 10, atol=1e-9)
        assert abs(data["durationSeconds"] - 5) < 1e-9
        if case["id"] == "scannetpp-scene44":
            with np.load(args.pointcloud_root / "scene_44_rgb.npz", allow_pickle=False) as source:
                rgb = source["rgb"]
        else:
            original = args.curated_root / "depth" / original_case
            height, width = np.load(original / "gt_depth.npy", mmap_mode="r").shape[1:]
            frames = sorted((original / "gt_rgb").iterdir())
            assert len(frames) == 50
            decoded = []
            for frame in frames:
                image = cv2.imread(str(frame))
                assert image is not None
                if case["id"] == "kitti-drive0095":
                    image = image[0:375, 371:871]
                decoded.append(cv2.cvtColor(cv2.resize(image, (width, height), interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2RGB))
            rgb = np.stack(decoded)
        assert len(rgb) == 50
        fractions, offset = [], 0
        for frame, (_, cloud) in enumerate(clouds):
            stop = offset + int(counts[frame])
            p, c = points[offset:stop], colors[offset:stop]
            assert p.astype(np.float16).tobytes() == buffer(cloud["props"]["points"])
            assert c.astype(np.uint8).tobytes() == buffer(cloud["props"]["colors"])
            # Match the existing exporters' pinhole convention, including their
            # treatment of intrinsics. Do not alter reconstruction geometry.
            camera = (p.astype(np.float64) - poses[frame, :3, 3]) @ np.linalg.inv(poses[frame, :3, :3]).T
            k = intrinsics[frame]
            uv = np.column_stack((camera[:, 0] / camera[:, 2] * k[0, 0] + k[0, 2], camera[:, 1] / camera[:, 2] * k[1, 1] + k[1, 2]))
            pixels = np.rint(uv).astype(int)
            assert (pixels >= 0).all() and (pixels[:, 0] < rgb.shape[2]).all() and (pixels[:, 1] < rgb.shape[1]).all()
            fraction = float(np.all(rgb[frame, pixels[:, 1], pixels[:, 0]] == c, axis=1).mean())
            fractions.append(fraction)
            assert fraction >= .9999, f"RGB does not match recorded point colors: {case['id']} frame {frame}, fraction {fraction}"
            offset = stop
        width, height, columns = 192, 144, 10
        sprite = Image.new("RGB", (width * columns, height * 5))
        for frame, image in enumerate(rgb):
            tile = Image.fromarray(image).resize((width, height), Image.Resampling.LANCZOS)
            sprite.paste(tile, ((frame % columns) * width, (frame // columns) * height))
        destination = root / "assets/viser" / ("rgb-" + case["id"] + ".jpg")
        sprite.save(destination, quality=90, subsampling=0)
        case["input_rgb"] = {"src": str(destination.relative_to(root)), "width": width, "height": height, "columns": columns, "frame_times": times, "duration": data["durationSeconds"]}
        entry = {"id": case["id"], "recording_sha256": hashlib.sha256(html_path.read_bytes()).hexdigest(), "pointcloud_source": npz_name, "frames": 50, "recorded_buffers_match": True, "rgb_point_match_min": min(fractions), "rgb_point_matches": fractions, "sprite": case["input_rgb"], "sprite_sha256": hashlib.sha256(destination.read_bytes()).hexdigest(), "sprite_bytes": destination.stat().st_size}
        evidence["cases"].append(entry)
        print(json.dumps({"id": case["id"], "verified_frames": 50, "rgb_point_match_min": min(fractions), "sprite_bytes": entry["sprite_bytes"]}), flush=True)
    evidence["status"] = "passed"
    (root / "examples.json").write_text(json.dumps(manifest, indent=2) + "\n")
    (root / "assets/viser/reconstruction-rgb-provenance.json").write_text(json.dumps(evidence, indent=2) + "\n")
    (args.run_dir / "reconstruction-rgb-evidence.json").write_text(json.dumps(evidence, indent=2) + "\n")


if __name__ == "__main__":
    main()
