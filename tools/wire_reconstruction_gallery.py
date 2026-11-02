#!/usr/bin/env python
"""Stage the recordings into assets/ and write the gallery's manifest entries.

Reads the selection and each recording's camera/size json, copies the .viser files
into assets/viser/recon/, and writes tools/reconstruction_cases.json. Patching
examples.json is a separate, explicit step (--write-examples) so the manifest the site
reads is never half-updated.
"""
import argparse, json, os, random, re, shutil, sys

HERE = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.dirname(HERE)
VISER = "/n/lab_storage/ydu_lab/Lab/akiruga/world_model_4d/final-website/assets/pointcloud/recon24_viser"
DEST = os.path.join(SITE, "assets/viser/recon")

SEVEN = ["chess/seq-03", "chess/seq-05", "fire/seq-03", "fire/seq-04", "heads/seq-01",
         "office/seq-02", "office/seq-06", "office/seq-07", "office/seq-09",
         "pumpkin/seq-01", "pumpkin/seq-07", "redkitchen/seq-03", "redkitchen/seq-04",
         "redkitchen/seq-06", "redkitchen/seq-12", "redkitchen/seq-14",
         "stairs/seq-01", "stairs/seq-04"]
SHUFFLE_SEED = 20261020
LABEL = {"scannetpp": "ScanNet++", "7scenes": "7-Scenes", "kitti": "KITTI",
         "bonn": "Bonn", "sintel": "Sintel"}


def identify(ds, scene):
    """(case id, human scene name)."""
    if ds == "scannetpp":
        n = scene.split("_")[1]
        return f"scannetpp-scene-{n}", f"scene {n}"
    if ds == "7scenes":
        seq = SEVEN[int(scene.split("_")[1])]
        return "7scenes-" + seq.replace("/", "-"), seq
    if ds == "bonn":
        name = scene.replace("rgbd_bonn_", "")
        return "bonn-" + name.replace("_", "-"), name
    if ds == "kitti":
        m = re.search(r"drive_(\d+)", scene)
        return f"kitti-drive-{m.group(1)}", f"drive {m.group(1)}"
    return f"sintel-{scene.replace('_','-')}", scene


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--write-examples", action="store_true")
    a = ap.parse_args()

    sel = json.load(open(f"{HERE}/reconstruction_selection.json"))["selected"]
    review = json.load(open(f"{HERE}/reconstruction_rejects.json")) \
        if os.path.exists(f"{HERE}/reconstruction_rejects.json") else {}
    drop = set(review.get("drop", {}))
    # Keep sprites that build_reconstruction_rgb_sprites.py already attached.
    prior = {}
    if os.path.exists(f"{HERE}/reconstruction_cases.json"):
        prior = {c["id"]: {k: c[k] for k in ("input_rgb", "initial_camera", "display_note")
                           if k in c}
                 for c in json.load(open(f"{HERE}/reconstruction_cases.json"))["cases"]}
    os.makedirs(DEST, exist_ok=True)
    cases, total = [], 0
    for r in sel:
        cid, human = identify(r["dataset"], r["scene"])
        if cid in drop:
            print(f"  dropped on review: {cid}")
            continue
        stem = f"{r['dataset']}__{r['scene']}"
        rec, meta = f"{VISER}/{stem}.viser", f"{VISER}/{stem}.json"
        if not (os.path.exists(rec) and os.path.exists(meta)):
            print(f"  MISSING recording for {cid}", file=sys.stderr); continue
        info = json.load(open(meta))
        shutil.copyfile(rec, f"{DEST}/{cid}.viser")
        total += info["bytes"]
        cases.append({
            "id": cid, "kind": "viser",
            "short_title": LABEL[r["dataset"]],
            "title": f"{LABEL[r['dataset']]} · {human}",
            "selection": f"AbsRel {r['abs_rel']:.4f}",
            "thumbnail": f"assets/viser/recon/thumb-{cid}.jpg",
            "src": f"assets/viser/recon/{cid}.viser",
            "initial_camera": info["initial_camera"],
            "description": "Drag to orbit, scroll to zoom, scrub to move through time.",
            "provenance": {
                "dataset": r["dataset"], "scene": r["scene"], "member": r["member"],
                "abs_rel": r["abs_rel"], "delta1": r["delta1"],
                "pose_source": r["pose_source"], "frames": info["frames"],
                "points_per_frame": info["points_per_frame"],
                "camera_travel_m": r["travel_m"],
            },
        })
        # frame_reconstruction_cameras.py and the sprite builder run after this, so
        # keep what they already computed instead of resetting it to the build-time guess.
        cases[-1].update(prior.get(cid) or {})
    # Gallery order: the three scenes the site already shipped stay in front, in their
    # original order; everything else is shuffled with a fixed seed so the order is
    # reproducible and not an implicit ranking.
    first = ["scannetpp-scene-44", "bonn-person-tracking2", "kitti-drive-0095"]
    head = [c for i in first for c in cases if c["id"] == i]
    tail = [c for c in cases if c["id"] not in first]
    random.Random(SHUFFLE_SEED).shuffle(tail)
    cases = head + tail
    ids = [c["id"] for c in cases]
    assert len(ids) == len(set(ids)), f"duplicate case ids: {ids}"
    json.dump({"cases": cases}, open(f"{HERE}/reconstruction_cases.json", "w"), indent=1)
    print(f"{len(cases)} cases, {total/1e6:.0f} MB of recordings -> {DEST}")
    print("  order: " + ", ".join(ids))

    if a.write_examples:
        ex = json.load(open(f"{SITE}/examples.json"))
        ex["reconstruction"]["cases"] = cases
        json.dump(ex, open(f"{SITE}/examples.json", "w"), indent=1)
        print(f"examples.json: reconstruction now has {len(cases)} cases")


if __name__ == "__main__":
    main()
