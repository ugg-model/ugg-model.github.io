"""Camera-matched capture: reconstruction clouds and our clouds, ONE viewer, ONE rule.

Both sides are viser pages, so the viewer is identical. The camera for each is
computed from that cloud's own geometry by the same rule and passed in through the
page's initialCameraPosition / initialCameraLookAt parameters, which is exactly how
the website sets the reconstruction viewer's camera. So this is a same-viewer,
same-camera-rule comparison in the real viewer, not a crop normalisation.
"""
import sys, math, json
import numpy as np
from playwright.sync_api import sync_playwright

OUT = sys.argv[1]
PC = "/n/lab_storage/ydu_lab/Lab/akiruga/world_model_4d/final-website/assets/pointcloud"
SCENES = [
    ("recon_scannetpp", f"{PC}/scannetpp_scene_44.npz", "assets/viser/scannetpp_scene44.html"),
    ("recon_bonn", f"{PC}/bonn_release_person_tracking2.npz", "assets/viser/bonn_person_tracking2.html"),
    ("recon_kitti", f"{PC}/kitti_release_drive0095.npz", "assets/viser/kitti_drive0095.html"),
    ("ours_sample_026", None, "viser/t4d_sample_026_standalone.html"),
    ("ours_sample_018", None, "viser/t4d_sample_018_standalone.html"),
]
NPZ_FOR_OURS = {
    "ours_sample_026": sys.argv[2] + "/t4d_sample_026.npz",
    "ours_sample_018": sys.argv[2] + "/t4d_sample_018.npz",
}
FRAME = 25
FOV = math.radians(48)
DIR = np.array([0.45, -0.55, -1.4])


def camera_for(npz_path):
    """Same rule for every cloud: look at the frame's robust centre from a distance
    set by its own radius, along a fixed direction."""
    z = np.load(npz_path)
    cnt = z["counts"]
    off = np.concatenate([[0], np.cumsum(cnt)])
    P = z["points"][off[FRAME]:off[FRAME + 1]].astype(np.float64)
    low, high = np.quantile(P, [0.02, 0.98], axis=0)
    target = (low + high) / 2
    radius = max(float(np.linalg.norm(high - low) / 2), 1e-6)
    half = min(FOV / 2, math.atan(math.tan(FOV / 2)))
    dist = radius / math.sin(half) * 0.75
    eye = target + DIR / np.linalg.norm(DIR) * dist
    return eye, target, radius


ARGS = ["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"]
meta = {}
with sync_playwright() as p:
    b = p.chromium.launch(args=ARGS)
    for name, npz, page in SCENES:
        src = npz or NPZ_FOR_OURS[name]
        eye, target, radius = camera_for(src)
        meta[name] = dict(radius=radius, eye=eye.tolist(), target=target.tolist())
        url = (f"http://127.0.0.1:8731/{page}"
               f"?initialCameraPosition={','.join(f'{v:.4f}' for v in eye)}"
               f"&initialCameraLookAt={','.join(f'{v:.4f}' for v in target)}"
               f"&initialCameraUp=0,-1,0")
        try:
            pg = b.new_page(viewport={"width": 760, "height": 620})
            pg.goto(url, timeout=240000)
            pg.wait_for_timeout(90000)
            c = pg.query_selector("canvas")
            pg.screenshot(path=f"{OUT}/cam_{name}.png", clip=c.bounding_box())
            print(f"captured {name}  radius={radius:.3f}", flush=True)
            pg.close()
        except Exception as e:
            print("FAILED", name, type(e).__name__, str(e)[:70], flush=True)
    b.close()
json.dump(meta, open(f"{OUT}/cam_meta.json", "w"), indent=1)
print("done", flush=True)
