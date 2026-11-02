"""Opening view aligned to a frame's OpenCV camera, with a small axial setback."""
import numpy as np

BACKOFF_FRACTION = 0.40


def first_frame_camera(points, c2w, intrinsics, width=384, height=288):
    pose = np.asarray(c2w, dtype=np.float64)
    k = np.asarray(intrinsics, dtype=np.float64)
    forward = pose[:3, 2] / np.linalg.norm(pose[:3, 2])
    up = -pose[:3, 1] / np.linalg.norm(pose[:3, 1])
    origin = pose[:3, 3]
    depths = (np.asarray(points) - origin) @ forward
    valid = depths[np.isfinite(depths) & (depths > 0)]
    if not len(valid):
        raise ValueError('First frame contains no positive camera-space depths')
    depth = float(np.median(valid))
    return {
        'position': (origin - forward * depth * BACKOFF_FRACTION).tolist(),
        'look_at': (origin + forward * depth).tolist(),
        'up': up.tolist(),
        'fov': float(2 * np.arctan(height / (2 * k[1, 1]))),
        'horizontal_fov': float(2 * np.arctan(width / (2 * k[0, 0]))),
        'framing': 'first_frame_camera',
        'backoff_fraction': BACKOFF_FRACTION,
        'median_depth': depth,
    }
