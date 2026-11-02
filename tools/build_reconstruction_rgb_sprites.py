#!/usr/bin/env python
"""Input-RGB sprite sheet AND gallery thumbnail for each reconstruction case.

The viewer draws the frame matching the viser clock into the upper-right inset, so the
RGB must be the SAME array that coloured the cloud -- not a re-decode of something that
merely looks similar. Both come from here: `gt_rgb.mp4` beside the frozen oracle scene,
or the gated `_7scenes_rgb/<scene>.npz` for 7-Scenes.

`frame_times` is accumulated the way the published cases were (repeated +1/fps in float,
so the stored duration is 4.999999999999998, not 5.0). The viewer finds the player's
slider by matching `aria-valuemax` to that duration within 1e-6, so this must not be
"tidied up" into an exact 5.0.

The gallery THUMBNAIL is the first input frame, not a render of the cloud. A rendered
cloud tile is not canonically oriented -- each scene's opening camera is derived from
its own geometry -- so a grid of them reads as twelve arbitrary angles. Every other
gallery on the site (Text-to-4D, NVS, Camera) already shows an RGB frame; this matches
them. tools/shoot_reconstruction_thumbs.py still renders the clouds, but for REVIEW.
"""
import argparse, json, os
import cv2, numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.dirname(HERE)
ORACLE = "/n/lab_storage/ydu_lab/Lab/akiruga/release-oracle-chosen/depth"
RGB_NPZ = {"7scenes": ("/n/lab_storage/ydu_lab/Lab/akiruga/world_model_4d/final-website/"
                       "assets/pointcloud/_7scenes_rgb"),
           "scannetpp": ("/n/lab_storage/ydu_lab/Lab/akiruga/world_model_4d/final-website/"
                         "assets/pointcloud/_scannetpp_rgb")}
MOVED_ROOT = "/n/netscratch/ydu_lab/Lab/akiruga/labstorage_move_20261025"
CELL = (192, 144)
THUMB = (320, 240)
COLUMNS = 10


def rgb_npz(dataset, scene):
    """The extracted loader RGB, from the live tree or, failing that, a daily snapshot.

    final-website moved off lab_storage to netscratch on 2026-10-25, so try there too,
    and finally the lab_storage daily snapshots (<dir>/.snapshot/ydu_lab_daily_<date>/)
    -- a build should not have to re-run the extractor because the tree was relocated.
    """
    base = RGB_NPZ.get(dataset)
    if not base:
        return None
    for root in (base, base.replace("/n/lab_storage/ydu_lab/Lab/akiruga/world_model_4d",
                                    MOVED_ROOT)):
        if os.path.exists(f"{root}/{scene}.npz"):
            return f"{root}/{scene}.npz"
    root, rest = base.split("/world_model_4d/", 1)
    snaps = f"{root}/world_model_4d/.snapshot"
    for day in sorted(os.listdir(snaps), reverse=True) if os.path.isdir(snaps) else []:
        candidate = f"{snaps}/{day}/{rest}/{scene}.npz"
        if os.path.exists(candidate):
            return candidate
    return None


def frames_for(case):
    p = case["provenance"]
    # Must match what coloured the cloud, including the corrected loader RGB.
    fixed = rgb_npz(p["dataset"], p["scene"])
    if fixed:
        return np.load(fixed)["rgb"]
    cap = cv2.VideoCapture(f"{ORACLE}/{p['dataset']}/{p['scene']}/gt_rgb.mp4")
    out = []
    while True:
        ok, f = cap.read()
        if not ok:
            break
        out.append(cv2.cvtColor(f, cv2.COLOR_BGR2RGB))
    cap.release()
    return np.stack(out)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--fps", type=float, default=10.0)
    ap.add_argument("--quality", type=int, default=88)
    a = ap.parse_args()
    path = f"{HERE}/reconstruction_cases.json"
    doc = json.load(open(path))
    for case in doc["cases"]:
        rgb = frames_for(case)
        n = case["provenance"]["frames"]
        assert len(rgb) >= n, f"{case['id']}: {len(rgb)} rgb frames vs {n} recorded"
        rgb = rgb[:n]
        rows = (n + COLUMNS - 1) // COLUMNS
        sheet = np.zeros((rows * CELL[1], COLUMNS * CELL[0], 3), np.uint8)
        for i, f in enumerate(rgb):
            cell = cv2.resize(f, CELL, interpolation=cv2.INTER_AREA)
            y, x = (i // COLUMNS) * CELL[1], (i % COLUMNS) * CELL[0]
            sheet[y:y+CELL[1], x:x+CELL[0]] = cell
        out = f"{SITE}/assets/viser/recon/rgb-{case['id']}.jpg"
        cv2.imwrite(out, cv2.cvtColor(sheet, cv2.COLOR_RGB2BGR),
                    [int(cv2.IMWRITE_JPEG_QUALITY), a.quality])
        thumb = cv2.resize(rgb[0], THUMB, interpolation=cv2.INTER_AREA)
        cv2.imwrite(f"{SITE}/assets/viser/recon/thumb-{case['id']}.jpg",
                    cv2.cvtColor(thumb, cv2.COLOR_RGB2BGR),
                    [int(cv2.IMWRITE_JPEG_QUALITY), 90])
        times, t = [], 0.0
        for _ in range(n):
            times.append(t); t += 1.0 / a.fps
        case["input_rgb"] = {"src": f"assets/viser/recon/rgb-{case['id']}.jpg",
                             "width": CELL[0], "height": CELL[1], "columns": COLUMNS,
                             "frame_times": times, "duration": t}
        print(f"  {case['id']:34s} {n} frames -> sprite {os.path.getsize(out)/1e3:.0f} kB"
              f" + thumbnail from input frame 0")
    json.dump(doc, open(path, "w"), indent=1)
    print(f"{len(doc['cases'])} cases carry input_rgb")


if __name__ == "__main__":
    main()
