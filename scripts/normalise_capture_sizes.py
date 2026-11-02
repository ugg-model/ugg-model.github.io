"""Browser captures with apparent size normalised.

Each viewer picks its own default camera distance, so raw captures are not
comparable in apparent size. Crop every capture to the cloud's own bounding box
and scale to a common panel: what remains comparable is how completely and
solidly each cloud fills its own extent, which is the thing being judged.

Sources are all real-viewer captures: recon_canvas.png is the viser
reconstruction viewer, cv_sample_*.png are the text-to-4D viewer.
"""
import glob
import numpy as np
from PIL import Image

SP = "/tmp/claude-67408/-n-lab-storage-ydu-lab-Lab-akiruga-world-model-4d-video-world-model-new/564dbf9b-4945-4fae-9b07-5f61b204fe96/scratchpad"
REL = dict(x=0.027083333333333334, y=0.03420208830058374,
           w=0.9458333333333333, h=0.602482940064129)
PANEL = 300


def canvas(path):
    im = Image.open(path).convert("RGB")
    w, h = im.size
    return im.crop((int(REL["x"] * w), int(REL["y"] * h),
                    int((REL["x"] + REL["w"]) * w), int((REL["y"] + REL["h"]) * h)))


def content_box(im, tol=18):
    """Bounding box of everything that is not background, ignoring the inset
    thumbnail the viewer draws in the top-right and the thin trajectory line."""
    a = np.asarray(im).astype(np.int16)
    bg = np.median(a.reshape(-1, 3), axis=0)
    d = np.abs(a - bg).sum(axis=2)
    mask = d > tol
    mask[:int(mask.shape[0] * 0.33), int(mask.shape[1] * 0.62):] = False  # inset
    # drop isolated thin structures (the orange path) by requiring local support
    k = 3
    pad = np.pad(mask.astype(np.uint8), k)
    dens = sum(pad[i:i + mask.shape[0], j:j + mask.shape[1]]
               for i in range(2 * k + 1) for j in range(2 * k + 1))
    mask = dens > (2 * k + 1) ** 2 * 0.35
    ys, xs = np.nonzero(mask)
    if len(xs) < 50:
        return None
    return int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1


def normalise(im):
    box = content_box(im)
    if box is None:
        return None
    im = im.crop(box)
    s = PANEL / max(im.width, im.height)
    im = im.resize((max(1, int(im.width * s)), max(1, int(im.height * s))), Image.LANCZOS)
    out = Image.new("RGB", (PANEL, PANEL), (255, 255, 255))
    out.paste(im, ((PANEL - im.width) // 2, (PANEL - im.height) // 2))
    return out


cells = []
r = normalise(Image.open(SP + "/recon_canvas.png").convert("RGB"))
cells.append(("RECON", r))
for p in sorted(glob.glob(SP + "/cv_sample_*.png")):
    n = normalise(canvas(p))
    if n is not None:
        cells.append((p.split("cv_")[1][:-4], n))
print("panels:", len(cells))

cols = 8
rows = (len(cells) + cols - 1) // cols
sheet = Image.new("RGB", (cols * PANEL, rows * PANEL), (245, 245, 245))
for i, (_, im) in enumerate(cells):
    sheet.paste(im, (i % cols * PANEL, i // cols * PANEL))
sheet.save(SP + "/browser_normalised.png")
print("wrote", sheet.size)
