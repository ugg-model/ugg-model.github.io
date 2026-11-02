#!/usr/bin/env python
"""Serialize each selected point cloud into a .viser recording and frame its camera.

Playback model (unchanged from the three published scenes): ONE point-cloud node that
is replaced every frame with a sleep between frames, so the client's time scrubber
steps through the 50 frames. The GT camera path is a static spline and a frustum marks
the current camera.

Opening camera: retain the first camera's forward/up axes and stand behind it by
15% of the first-frame median depth. Calibration supplies the field of view.
"""
import argparse, json, os, sys
import numpy as np, viser
from first_frame_camera import first_frame_camera


def mat2wxyz(R):
    """Rotation matrix -> (w,x,y,z). Shepperd's method, branch on the largest term."""
    m00, m01, m02 = R[0]; m10, m11, m12 = R[1]; m20, m21, m22 = R[2]
    tr = m00 + m11 + m22
    if tr > 0:
        s = np.sqrt(tr + 1.0) * 2; w = 0.25*s; x = (m21-m12)/s; y = (m02-m20)/s; z = (m10-m01)/s
    elif m00 > m11 and m00 > m22:
        s = np.sqrt(1.0+m00-m11-m22)*2; w = (m21-m12)/s; x = 0.25*s; y = (m01+m10)/s; z = (m02+m20)/s
    elif m11 > m22:
        s = np.sqrt(1.0+m11-m00-m22)*2; w = (m02-m20)/s; x = (m01+m10)/s; y = 0.25*s; z = (m12+m21)/s
    else:
        s = np.sqrt(1.0+m22-m00-m11)*2; w = (m10-m01)/s; x = (m02+m20)/s; y = (m12+m21)/s; z = 0.25*s
    q = np.array([w, x, y, z]); return q / np.linalg.norm(q)


def build(npz_path, out_path, fps, point_size, draw_path=True):
    z = np.load(npz_path, allow_pickle=True)
    P, C, cnt, c2w, K = z["points"], z["colors"], z["counts"], z["c2w"], z["K"]
    off = np.concatenate([[0], np.cumsum(cnt)])
    F = len(cnt)
    initial_camera = first_frame_camera(P[:int(cnt[0])], c2w[0], K[0] if K.ndim == 3 else K)
    fov = initial_camera["fov"]

    server = viser.ViserServer(port=0)
    try:
        ser = server.get_scene_serializer()
        # A driving scene's path is tens of metres of spline across the frame and
        # swamps the cloud; the moving frustum still shows where the camera is.
        if draw_path:
            server.scene.add_spline_catmull_rom(
                "/gt_path", positions=c2w[:, :3, 3].astype(np.float32),
                line_width=2.0, color=(250, 190, 60))
        for i in range(F):
            server.scene.add_point_cloud(
                "/cloud", points=P[off[i]:off[i+1]], colors=C[off[i]:off[i+1]],
                point_size=point_size, point_shape="rounded", precision="float16")
            server.scene.add_camera_frustum(
                "/camera", fov=fov, aspect=384/288, scale=max(0.12, 0.05*np.linalg.norm(
                    c2w[-1, :3, 3]-c2w[0, :3, 3])/10), line_width=2.0, color=(255, 90, 90),
                wxyz=mat2wxyz(c2w[i, :3, :3]), position=c2w[i, :3, 3])
            ser.insert_sleep(1.0 / fps)
        data = ser.serialize()
        os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
        open(out_path, "wb").write(data)
    finally:
        server.stop()
    return dict(bytes=len(data), frames=F, points_per_frame=int(cnt.mean()),
                initial_camera=initial_camera,
                point_size=point_size, fps=fps)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--npz", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--meta", required=True, help="where to write this scene's camera/size json")
    ap.add_argument("--fps", type=float, default=10.0)
    # 0.006 is what every published export used. At 0.012 the same cloud renders as
    # fused blobs instead of fine stipple and reads as noise -- it is the single
    # biggest knob on how the gallery looks, and it is NOT the script's old default.
    ap.add_argument("--point_size", type=float, default=0.006)
    ap.add_argument("--no-path", dest="draw_path", action="store_false",
                    help="omit the camera-path spline (driving scenes)")
    a = ap.parse_args()
    info = build(a.npz, a.out, a.fps, a.point_size, a.draw_path)
    json.dump(info, open(a.meta, "w"), indent=1)
    print(f"{os.path.basename(a.out)}  {info['bytes']/1e6:.1f} MB  "
          f"{info['points_per_frame']} pts/frame  cam {info['initial_camera']}")


if __name__ == "__main__":
    main()
