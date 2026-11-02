#!/usr/bin/env python
"""Historical oblique-view camera utility; also reports scene planarity.

Production defaults now use tools/set_first_frame_cameras.py to align to the
first-frame camera. This utility remains for reproducing earlier comparisons.

Why not a fixed offset from the first camera: a point cloud is a shell seen from one
side. Park the camera on the wrong side and you are looking at the unobserved back of a
wall (dark, noisy); park it at a fixed multiple of the scene radius and a 50 m driving
scene becomes a speck. Both happened.

Rule here:
  * frame the ONE frame the viewer actually shows, not the union of all 50. The union of
    a driving scene is a 60 m swept volume, so fitting it put the camera 60 m back and
    every KITTI scene rendered as a speck,
  * look at that frame's robust centre,
  * stand on the side its SENSOR was on, so the surfaces facing us are the observed ones,
  * tilt up and swing sideways for a 3/4 view instead of a head-on depth map,
  * pull back exactly far enough to fit that frame's robust bounding box in the FOV.

Also prints a planarity score (smallest/largest singular value of the centred points).
A scene near zero is a flat wall seen face-on and makes a dull gallery tile however good
its AbsRel is.
"""
import argparse, json, os
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.dirname(HERE)
NPZ = "/n/lab_storage/ydu_lab/Lab/akiruga/world_model_4d/final-website/assets/pointcloud/recon24"
# Distance is solved so the displayed cloud subtends a fixed half-angle, measured off
# the hand-tuned camera the site shipped for scene_44: it frames that scene's mid-frame
# points at a 98th-percentile half-angle of 23.4 degrees. Sizing instead from the
# bounding-box diagonal fails on anisotropic clouds -- a KITTI road corridor's diagonal
# is its length, so the camera backed off to where the road was a sliver.
TARGET_HALF_ANGLE = 24.0
FIT = 1.0               # scales the target half-angle; >1 moves the camera IN, <1 pulls back


def unit(v):
    n = np.linalg.norm(v)
    return v / n if n > 1e-9 else v


def frame(points, counts, c2w, yaw_deg, pitch_deg, fit=FIT, index=None):
    index = 20 if index is None else index   # t=2.0 at 10 fps: what the thumbnail shows
    off = np.concatenate([[0], np.cumsum(counts)])
    shown = points[off[index]:off[index + 1]]       # exactly what is on screen at that time
    sample = shown[:: max(1, len(shown) // 200_000)]
    centre = np.median(sample, 0)
    lo, hi = np.percentile(sample, [5, 95], axis=0)
    radius = 0.5 * float(np.linalg.norm(hi - lo))

    view = unit(c2w[index, :3, 3] - centre)         # from the cloud toward the sensor side
    up_w = unit(-c2w[index, :3, 1])                 # OpenCV y is down, so world up is -y
    if abs(float(np.dot(up_w, view))) > 0.95:       # degenerate: looking straight down
        up_w = unit(np.cross(view, c2w[index, :3, 0]))
    right = unit(np.cross(up_w, view))
    yaw, pitch = np.radians(yaw_deg), np.radians(pitch_deg)
    d = unit(view * np.cos(yaw) + right * np.sin(yaw))
    d = unit(d * np.cos(pitch) + up_w * np.sin(pitch))

    target = np.radians(TARGET_HALF_ANGLE * fit)
    pts = sample[:: max(1, len(sample) // 20_000)]

    def half_angle(t):
        cam = centre + d * t
        v = pts - cam
        axis = -d
        along = v @ axis
        lat = np.linalg.norm(v - np.outer(along, axis), axis=1)
        return float(np.percentile(np.arctan2(lat, np.maximum(along, 1e-6)), 98))

    lo_t, hi_t = 1e-3, max(50.0, 20 * radius)       # monotone decreasing in t
    for _ in range(60):
        mid = 0.5 * (lo_t + hi_t)
        if half_angle(mid) > target:
            lo_t = mid
        else:
            hi_t = mid
    dist = 0.5 * (lo_t + hi_t)
    pos = centre + d * dist
    c = sample - sample.mean(0)
    sv = np.linalg.svd(c, compute_uv=False)
    return ([round(float(v), 3) for v in pos], [round(float(v), 3) for v in centre],
            float(sv[2] / sv[0]), radius)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--yaw", type=float, default=28.0, help="degrees to swing off the sensor axis")
    ap.add_argument("--pitch", type=float, default=22.0, help="degrees to rise above it")
    ap.add_argument("--overrides", default=os.path.join(HERE, "reconstruction_camera_overrides.json"))
    ap.add_argument("--write-examples", action="store_true")
    a = ap.parse_args()

    over = json.load(open(a.overrides)) if os.path.exists(a.overrides) else {}
    path = f"{HERE}/reconstruction_cases.json"
    doc = json.load(open(path))
    for case in doc["cases"]:
        p = case["provenance"]
        z = np.load(f"{NPZ}/{p['dataset']}__{p['scene']}.npz", allow_pickle=True)
        o = over.get(case["id"], {})
        pos, look, planarity, radius = frame(z["points"], z["counts"], z["c2w"],
                                             o.get("yaw", a.yaw), o.get("pitch", a.pitch),
                                             o.get("fit", FIT), o.get("index"))
        if "position" in o:
            pos, look = o["position"], o.get("look_at", look)
        case["initial_camera"] = {"position": pos, "look_at": look}
        p["planarity"] = round(planarity, 4)
        p["cloud_radius_m"] = round(radius, 2)
        print(f"  {case['id']:30s} radius {radius:7.2f} m  planarity {planarity:.4f}"
              f"{'   <- flat' if planarity < 0.06 else ''}{'   (override)' if o else ''}")
    json.dump(doc, open(path, "w"), indent=1)

    if a.write_examples:
        ex = json.load(open(f"{SITE}/examples.json"))
        ex["reconstruction"]["cases"] = doc["cases"]
        json.dump(ex, open(f"{SITE}/examples.json", "w"), indent=1)
        print(f"examples.json updated ({len(doc['cases'])} cases)")


if __name__ == "__main__":
    main()
