"""Copy one provisional NVS case and make a frame-matched side-by-side preview."""
import argparse
import json
import shutil
import subprocess
from pathlib import Path

import cv2
import imageio_ffmpeg
from media_utils import poster, sha256


def metadata(path):
    capture = cv2.VideoCapture(str(path))
    result = {"frames": int(capture.get(cv2.CAP_PROP_FRAME_COUNT)),
              "fps": float(capture.get(cv2.CAP_PROP_FPS)),
              "width": int(capture.get(cv2.CAP_PROP_FRAME_WIDTH)),
              "height": int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))}
    capture.release()
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sample", type=Path, required=True)
    parser.add_argument("--prefix", required=True)
    parser.add_argument("--run-dir", type=Path, required=True)
    args = parser.parse_args()
    assets = Path(__file__).resolve().parents[1] / "assets"
    args.run_dir.mkdir(parents=True, exist_ok=True)
    sources = {"prediction": args.sample / "pred_rgb.mp4", "reference": args.sample / "gt_rgb.mp4"}
    meta = {key: metadata(source) for key, source in sources.items()}
    if meta["prediction"] != meta["reference"] or meta["prediction"]["frames"] <= 0:
        raise ValueError("NVS prediction/reference frame counts, frame rates or dimensions differ")
    for view, source in sources.items():
        shutil.copyfile(source, assets / f"{args.prefix}{view}.mp4")
    output = assets / f"{args.prefix}comparison.mp4"
    subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-hide_banner", "-loglevel", "error",
                    "-y", "-i", str(sources["prediction"]), "-i", str(sources["reference"]),
                    "-filter_complex", "[0:v][1:v]hstack=inputs=2:shortest=1[v]", "-map", "[v]",
                    "-an", "-c:v", "libx264", "-crf", "20", "-pix_fmt", "yuv420p",
                    "-movflags", "+faststart", str(output)], check=True)
    for view in ["prediction", "reference", "comparison"]:
        poster(assets / f"{args.prefix}{view}.mp4", assets / f"{args.prefix}{view}.png")
    member = (args.sample / "MEMBER.txt").read_text()
    (args.run_dir / f"{args.prefix}MEMBER.txt").write_text(member)
    evidence = {"source": str(args.sample), "metadata": meta,
                "selection": "Ground-truth PSNR oracle selection",
                "comparison": "Prediction left, reference right, matching frame order and native FPS",
                "sha256": {view: sha256(assets / f"{args.prefix}{view}.mp4")
                           for view in ["prediction", "reference", "comparison"]}}
    (args.run_dir / f"{args.prefix}asset-evidence.json").write_text(json.dumps(evidence, indent=2) + "\n")
    public = {**evidence, "source": "nvs/" + args.sample.parent.name + "/" + args.sample.name}
    (assets / f"{args.prefix}provenance.json").write_text(json.dumps(public, indent=2) + "\n")
    print(json.dumps({"status": "complete", "metadata": meta, "case": args.sample.name}))


if __name__ == "__main__":
    main()
