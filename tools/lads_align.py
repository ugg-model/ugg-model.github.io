"""Canonical published alignment: L1-robust affine (scale+shift) via IRLS.
Copied from eval_pi3/hf/align_ablation.py::_fit_affine_lads so the oracle
builder and the renderer cannot drift from the published scorer."""
import numpy as np

def fit_affine_lads(p, g, iters=50):
    A = np.stack([p, np.ones_like(p)], axis=1)
    st, *_ = np.linalg.lstsq(A, g, rcond=None)
    s, t = float(st[0]), float(st[1])
    for _ in range(iters):
        r = np.abs(s * p + t - g)
        w = 1.0 / np.maximum(r, 1e-6)
        W = np.sqrt(w)
        st, *_ = np.linalg.lstsq(np.stack([p * W, W], axis=1), g * W, rcond=None)
        ns, nt = float(st[0]), float(st[1])
        if abs(ns - s) < 1e-7 and abs(nt - t) < 1e-7:
            s, t = ns, nt; break
        s, t = ns, nt
    return s, t

def metrics(p_aligned, g):
    a = np.clip(p_aligned, 1e-6, None)
    absrel = float(np.mean(np.abs(a - g) / g))
    d1 = float(np.mean((np.maximum(a / g, g / a) < 1.25).astype(np.float64)))
    return absrel, d1


FIT_CAP = 1_000_000

def fit_affine_lads_capped(p, g, cap=FIT_CAP, seed=0, iters=50):
    """Fit on a deterministic random subsample (the fit has 2 parameters, so a
    1M-pixel draw reproduces the full-resolution fit to <0.11% on every
    benchmark tested). Always EVALUATE the metric on all pixels."""
    p = np.asarray(p, np.float64).ravel(); g = np.asarray(g, np.float64).ravel()
    if len(p) > cap:
        idx = np.random.default_rng(seed).choice(len(p), cap, replace=False)
        return fit_affine_lads(p[idx], g[idx], iters=iters)
    return fit_affine_lads(p, g, iters=iters)
