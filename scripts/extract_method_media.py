"""Losslessly encode slide-1 preview media; architecture is native HTML/CSS."""
import argparse
import hashlib
import json
import io
from pathlib import Path
from zipfile import ZipFile
from PIL import Image

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("source", type=Path)
args = parser.parse_args()
target = Path("assets/method")
target.mkdir(parents=True, exist_ok=True)
images = {"rgb-input": 6, "depth-input": 8, "ray-input": 5,
          "rgb-1": 9, "rgb-2": 10, "rgb-3": 11,
          "depth-1": 12, "depth-2": 13, "depth-3": 14,
          "ray-1": 15, "ray-2": 16, "ray-3": 17}
record = {"source": args.source.name, "source_sha256": hashlib.sha256(args.source.read_bytes()).hexdigest(),
          "slide": 1, "note": "Lossless WebP with original pixel dimensions/colors; architecture labels and shapes rebuilt in HTML/CSS.", "images": []}
with ZipFile(args.source) as archive:
    for name, number in images.items():
        member = f"ppt/media/image{number}.png"
        data = archive.read(member)
        image = Image.open(io.BytesIO(data)).convert("RGB")
        path = target / f"{name}.webp"
        image.save(path, "WEBP", lossless=True, method=6)
        assert Image.open(path).convert("RGB").tobytes() == image.tobytes(), "Lossless preview must preserve source pixels"
        (target / f"{name}.png").unlink(missing_ok=True)
        record["images"].append({"file": str(path), "member": member,
                                "source_sha256": hashlib.sha256(data).hexdigest(),
                                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                                "width": image.width, "height": image.height})
(target / "source.json").write_text(json.dumps(record, indent=2) + "\n")
print(f"Encoded {len(images)} source previews into {target}; exact decoded RGB verified")
