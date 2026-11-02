#!/usr/bin/env python
"""Pull the 50 GT RGB frames for curated scene_44 and PROVE they line up with
its depth before anything is coloured with them.

Check: Sobel edges of the RGB vs edges of the GT depth. A correct pairing gives
a clearly positive correlation that degrades when frames are shifted; a wrong
pairing looks flat across shifts.
"""
import numpy as np, cv2, json, os

ID  = json.load(open("/n/lab_storage/ydu_lab/Lab/akiruga/world_model_4d/final-website/tools/scene44_identity.json")) \
      if os.path.exists("/n/lab_storage/ydu_lab/Lab/akiruga/world_model_4d/final-website/tools/scene44_identity.json") else None
SC    = "578511c8a9"; START, STRIDE, N = 7410, 10, 50
MKV   = f"/n/netscratch/ydu_lab/Everyone/datasets/scannetpp/data/{SC}/iphone/rgb.mkv"
D     = "/n/lab_storage/ydu_lab/Lab/akiruga/curated_oracle/depth/scannetpp__dense/scene_44"
OUT   = "/n/lab_storage/ydu_lab/Lab/akiruga/world_model_4d/final-website/assets/pointcloud/scene_44_rgb.npz"
H, W  = 288, 384

gt = np.load(f"{D}/gt_depth.npy")
idx = [START + i*STRIDE for i in range(N)]
cap = cv2.VideoCapture(MKV)
assert cap.isOpened()

frames = {}
want = set(idx) | {START + i*STRIDE + o for i in range(N) for o in (-30, 30)}   # +/- for the shift control
cap.set(cv2.CAP_PROP_POS_FRAMES, min(want))
cur = min(want)
while cur <= max(want):
    ok, f = cap.read()
    if not ok: break
    if cur in want:
        frames[cur] = cv2.resize(f, (W, H), interpolation=cv2.INTER_AREA)
    cur += 1
cap.release()
print(f"decoded {len(frames)} frames from {MKV.split('/')[-3]}")

def edges(x):
    x = x.astype(np.float32)
    g = np.hypot(cv2.Sobel(x, cv2.CV_32F, 1, 0, 3), cv2.Sobel(x, cv2.CV_32F, 0, 1, 3))
    return (g - g.mean()) / (g.std() + 1e-9)

def corr(shift):
    cs = []
    for i, fi in enumerate(idx):
        f = frames.get(fi + shift)
        if f is None: continue
        d = gt[i]
        m = np.isfinite(d) & (d > 1e-3)
        if m.sum() < 1000: continue
        a = edges(cv2.cvtColor(f, cv2.COLOR_BGR2GRAY))[m]
        b = edges(d)[m]
        cs.append(float((a*b).mean()))
    return np.mean(cs)

aligned = corr(0)
print(f"\nedge correlation, aligned      : {aligned:+.4f}")
for s in (-30, 30):
    print(f"edge correlation, shifted {s:+4d}  : {corr(s):+.4f}")

rgb = np.stack([cv2.cvtColor(frames[i], cv2.COLOR_BGR2RGB) for i in idx])
if aligned > 0.05 and aligned > 1.5*max(corr(-30), corr(30)):
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    np.savez_compressed(OUT, rgb=rgb, frame_indices=np.array(idx), scene=SC)
    print(f"\nALIGNED -> wrote {OUT} ({os.path.getsize(OUT)/1e6:.1f} MB) {rgb.shape}")
else:
    print("\nNOT CONVINCINGLY ALIGNED - not writing; do not colour from this.")
