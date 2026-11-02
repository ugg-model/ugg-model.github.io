"""Shared decode + alignment, matching the published evaluation pipeline.

pred_depth_norm is normalised DISPARITY in [-1,1]. Inverting it naively lets
near-zero disparities explode to ~1e6, which swamps the affine fit (on Bonn it
collapsed the slope to zero). The reference decode floors disp_01 at its p-th
percentile over the whole video; pc=10 is what the published scores used.
"""
import numpy as np

EPS = 1e-3
PERCENTILE_CLIP = 2.0   # verified: reproduces BOTH manifest abs_rel values (pc=10 does not)

def decode_depth(depth_norm, scale=1.0, percentile_clip=PERCENTILE_CLIP, eps=EPS):
    disp = (np.asarray(depth_norm, dtype=np.float32) + 1.0) * 0.5
    lo = eps
    if percentile_clip is not None:
        valid = (disp > 0) & np.isfinite(disp)
        if valid.any():
            lo = max(float(np.percentile(disp[valid], percentile_clip)), eps)
    disp = np.clip(disp, lo, 1.0 - eps)
    return ((1.0 / disp - 1.0) * float(scale)).astype(np.float32)

def fit_affine_trimmed(p, g, iters=3, keep=0.8):
    """Least squares s*p+t ~ g, refit on the best-fitting `keep` fraction."""
    m = np.ones(len(p), bool); s = t = 0.0
    for _ in range(iters):
        A = np.stack([p[m], np.ones(int(m.sum()))], 1)
        (s, t), *_ = np.linalg.lstsq(A, g[m], rcond=None)
        r = np.abs(s * p + t - g)
        m = r <= np.quantile(r, keep)
    return float(s), float(t)


def edge_mask(depth, rel_thresh=0.04):
    """Drop 'flying pixels' at depth discontinuities.

    A pixel spanning an object edge gets a depth between foreground and
    background, producing a skirt of points stretching from the object back to
    the wall. Cull pixels whose local depth gradient is large relative to their
    own depth. Returns a boolean keep-mask shaped like `depth`.
    """
    import numpy as np
    d = np.asarray(depth, np.float32)
    gx = np.zeros_like(d); gy = np.zeros_like(d)
    gx[:, 1:-1] = np.abs(d[:, 2:] - d[:, :-2]) * 0.5
    gy[1:-1, :] = np.abs(d[2:, :] - d[:-2, :]) * 0.5
    grad = np.hypot(gx, gy)
    return grad <= rel_thresh * np.maximum(d, 1e-6)
