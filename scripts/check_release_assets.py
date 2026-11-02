"""Validate manifest references, timeline metadata, poses, and optional MP4 decoding.

Run inside this task's verified CPU Slurm allocation, using conda environment wan.
"""
import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import subprocess

import imageio_ffmpeg
import numpy as np
from PIL import Image

from prepare_release_assets import metadata


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", required=True, type=Path)
    parser.add_argument("--decode", action="store_true")
    args = parser.parse_args()
    site = Path(__file__).resolve().parents[1]
    manifest = json.loads((site / "examples.json").read_text())
    evidence = {"status": "running", "counts": {}, "references": [], "checks": [], "decoded_videos": [], "errors": []}
    references = set()
    try:
        for task, gallery in manifest.items():
            cases = gallery["cases"]
            evidence["counts"][task] = len(cases)
            assert len({case["id"] for case in cases}) == len(cases), f"Duplicate IDs in {task}"
            if gallery.get("selection"):
                policy = gallery["selection"]
                assert len(cases) == policy["selected"] <= policy["limit"], task
                assert dict(Counter(case["dataset"] for case in cases)) == {dataset: count for dataset, count in policy["dataset_quotas"].items() if count}, task
                pages = [dict(sorted(Counter(case["dataset"] for case in cases[start:start + policy["page_size"]]).items()))
                         for start in range(0, len(cases), policy["page_size"])]
                assert pages == policy["page_datasets"], task
            for case in cases:
                for key in ("thumbnail", "src", "poses", "input_video", "clock_video", "trajectory_video"):
                    if case.get(key):
                        references.add(case[key])
                for view in case.get("views", {}).values():
                    references.add(view["src"])
                    if view.get("poster"):
                        references.add(view["poster"])
                if case.get("input_rgb"):
                    rgb = case["input_rgb"]
                    references.add(rgb["src"])
                    times = rgb["frame_times"]
                    assert len(times) == 50 and np.isfinite(times).all() and times[0] == 0
                    assert all(a < b for a, b in zip(times, times[1:])) and times[-1] < rgb["duration"]
                    with Image.open(site / rgb["src"]) as sprite:
                        assert sprite.size == (rgb["width"] * rgb["columns"], rgb["height"] * ((len(times) + rgb["columns"] - 1) // rgb["columns"]))
                        sprite.verify()
                if case.get("kind") == "synchronized":
                    if task == "depth":
                        for view in case["views"].values():
                            info = metadata(site / view["src"])
                            assert info["frames"] == case["frame_count"] and abs(info["fps"] - case["fps"]) < 1e-5, case["id"]
                            expected_width = case["width"] + (case["input_width"] if case.get("has_input") else 0)
                            assert (info["width"], info["height"]) == (expected_width, case["height"]), case["id"]
                    elif task == "camera" or case.get("poses"):
                        poses = json.loads((site / case["poses"]).read_text())
                        info = metadata(site / (case.get("input_video") or case["clock_video"]))
                        assert poses["frame_count"] == case["frame_count"] == info["frames"], case["id"]
                        assert poses["fps"] == case["fps"] and abs(info["fps"] - case["fps"]) < 1e-5, case["id"]
                        for key in (("reference",) if task == "nvs" else ("prediction", "reference")):
                            assert len(poses[key]) == case["frame_count"], case["id"]
                            for pose in poses[key]:
                                assert np.isfinite(pose["position"]).all() and np.isfinite(pose["rotation"]).all(), case["id"]
                if task in ("nvs", "depth"):
                    assert list(case["views"]) == ["comparison"], case["id"]
                if task in ("depth", "camera"):
                    assert case["thumbnail_kind"] == "rgb" if case["has_input"] else case["thumbnail_kind"] == "unavailable", case["id"]
                if task in ("nvs", "depth", "camera"):
                    assert case["autoplay"], case["id"]
        for relative in sorted(references):
            path = (site / relative).resolve()
            assert path.is_relative_to(site), f"Reference escapes site: {relative}"
            assert path.is_file() and path.stat().st_size, f"Missing/empty asset: {relative}"
            assert path.stat().st_size < 100 * 1024 * 1024, f"Asset exceeds GitHub per-file limit: {relative}"
        for name in ("assets/method2.pdf", "assets/method2.png"):
            assert (site / name).is_file(), f"Missing method figure: {name}"
        with Image.open(site / "assets/method2.png") as image:
            image.verify()
        import_report = json.loads((args.run_dir / "release-import-evidence.json").read_text())
        assert not any(case["status"] == "failed" for case in import_report["cases"]), "Failed imports remain"
        for task in ("nvs", "depth", "camera"):
            assert evidence["counts"][task] == import_report["included_counts"][task], task
        evidence["checks"].append("All manifest references, synchronized timelines, camera arrays, and method figure exist and validate")
        if args.decode:
            def decode(relative):
                result = subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-hide_banner", "-loglevel", "error", "-xerror", "-threads", "1",
                                         "-i", str(site / relative), "-an", "-f", "null", "-"], capture_output=True, text=True)
                if result.returncode:
                    raise RuntimeError(relative + ": " + result.stderr[-2000:])
                return relative
            videos = sorted(relative for relative in references if relative.endswith(".mp4"))
            with ThreadPoolExecutor(max_workers=2) as pool:
                for relative in pool.map(decode, videos):
                    evidence["decoded_videos"].append(relative)
            evidence["checks"].append(f"Fully decoded {len(videos)} distinct manifest MP4s without FFmpeg errors")
        evidence["references"] = sorted(references)
        evidence["status"] = "passed"
    except Exception as error:
        evidence["status"] = "failed"
        evidence["errors"].append(str(error))
        raise
    finally:
        args.run_dir.mkdir(parents=True, exist_ok=True)
        (args.run_dir / "release-asset-checks.json").write_text(json.dumps(evidence, indent=2) + "\n")
        print(json.dumps({key: evidence[key] for key in ("status", "counts", "checks", "errors")}, indent=2))


if __name__ == "__main__":
    main()
