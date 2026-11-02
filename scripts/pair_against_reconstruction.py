"""Per-scene matched comparison: reconstruction beside EACH of the 45.

Both panels in every pair are real-viewer captures (viser reconstruction viewer /
text-to-4D viewer), cropped to the cloud's own extent and scaled to the same
panel, so each pair is a like-for-like comparison rather than one shared
reference panel at the corner of a grid.
"""
import glob
import numpy as np
from PIL import Image

SP = "/tmp/claude-67408/-n-lab-storage-ydu-lab-Lab-akiruga-world-model-4d-video-world-model-new/564dbf9b-4945-4fae-9b07-5f61b204fe96/scratchpad"
REL = dict(x=0.027083333333333334, y=0.03420208830058374,
           w=0.9458333333333333, h=0.602482940064129)
P = 230


def canvas(path):
    im = Image.open(path).convert("RGB")
    w, h = im.size
    return im.crop((int(REL["x"] * w), int(REL["y"] * h),
                    int((REL["x"] + REL["w"]) * w), int((REL["y"] + REL["h"]) * h)))


def content_box(im, tol=18, drop_inset=True, drop_banner=False):
    a = np.asarray(im).astype(np.int16)
    bg = np.median(a.reshape(-1, 3), axis=0)
    mask = np.abs(a - bg).sum(axis=2) > tol
    if drop_inset:
        mask[:int(mask.shape[0] * 0.33), int(mask.shape[1] * 0.62):] = False
    if drop_banner:
        # the viser viewer draws a "Software WebGL" notice top-left; it would
        # otherwise inflate the bounding box and shrink the cloud unfairly
        mask[:int(mask.shape[0] * 0.30), :int(mask.shape[1] * 0.40)] = False
    k = 3
    pad = np.pad(mask.astype(np.uint8), k)
    dens = sum(pad[i:i + mask.shape[0], j:j + mask.shape[1]]
               for i in range(2 * k + 1) for j in range(2 * k + 1))
    mask = dens > (2 * k + 1) ** 2 * 0.35
    ys, xs = np.nonzero(mask)
    if len(xs) < 50:
        return None
    return int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1


def norm(im, drop_inset=True, drop_banner=False):
    box = content_box(im, drop_inset=drop_inset, drop_banner=drop_banner)
    if box is None:
        return None
    im = im.crop(box)
    s = P / max(im.width, im.height)
    im = im.resize((max(1, int(im.width * s)), max(1, int(im.height * s))), Image.LANCZOS)
    out = Image.new("RGB", (P, P), (255, 255, 255))
    out.paste(im, ((P - im.width) // 2, (P - im.height) // 2))
    return out


recon = norm(Image.open(SP + "/recon_canvas.png").convert("RGB"), drop_inset=False, drop_banner=True)
scenes = []
for p in sorted(glob.glob(SP + "/cv_sample_*.png")):
    n = norm(canvas(p))
    if n is not None:
        scenes.append((p.split("cv_")[1][:-4], n))
print("pairs:", len(scenes))

PAIR_W = P * 2 + 6
cols = 5
rows = (len(scenes) + cols - 1) // cols
sheet = Image.new("RGB", (cols * (PAIR_W + 14), rows * (P + 14)), (235, 235, 235))
for i, (_, im) in enumerate(scenes):
    x = i % cols * (PAIR_W + 14) + 7
    y = i // cols * (P + 14) + 7
    sheet.paste(recon, (x, y))
    sheet.paste(im, (x + P + 6, y))
sheet.save(SP + "/browser_pairs45.png")
print("wrote", sheet.size, "(left of each pair = reconstruction viewer)")
