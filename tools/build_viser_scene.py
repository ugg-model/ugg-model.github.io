#!/usr/bin/env python
"""Serialize the per-frame point clouds into a .viser recording.

Playback model: one point cloud node that is REPLACED each frame, with a sleep
between frames, so the client's time scrubber steps through frames. The GT
camera path is a static spline; a frustum marks the current camera.
"""
import numpy as np, os, argparse, viser

def mat2wxyz(R):
    """Rotation matrix -> (w,x,y,z). Shepperd's method, branch on the largest term."""
    m00,m01,m02 = R[0]; m10,m11,m12 = R[1]; m20,m21,m22 = R[2]
    tr = m00+m11+m22
    if tr > 0:
        s = np.sqrt(tr+1.0)*2;  w=0.25*s; x=(m21-m12)/s; y=(m02-m20)/s; z=(m10-m01)/s
    elif m00 > m11 and m00 > m22:
        s = np.sqrt(1.0+m00-m11-m22)*2; w=(m21-m12)/s; x=0.25*s; y=(m01+m10)/s; z=(m02+m20)/s
    elif m11 > m22:
        s = np.sqrt(1.0+m11-m00-m22)*2; w=(m02-m20)/s; x=(m01+m10)/s; y=0.25*s; z=(m12+m21)/s
    else:
        s = np.sqrt(1.0+m22-m00-m11)*2; w=(m10-m01)/s; x=(m02+m20)/s; y=(m12+m21)/s; z=0.25*s
    q = np.array([w,x,y,z]); return q/np.linalg.norm(q)

ap = argparse.ArgumentParser()
ap.add_argument("--npz", default="/n/lab_storage/ydu_lab/Lab/akiruga/world_model_4d/final-website/assets/pointcloud/scannetpp_scene_44.npz")
ap.add_argument("--out", default="/n/lab_storage/ydu_lab/Lab/akiruga/world_model_4d/final-website/assets/pointcloud/scannetpp_scene_44.viser")
ap.add_argument("--fps", type=float, default=10.0)
ap.add_argument("--point_size", type=float, default=0.012)
ap.add_argument("--html", action="store_true", help="emit standalone HTML instead of .viser")
a = ap.parse_args()

z = np.load(a.npz)
P, C, cnt, c2w, K = z["points"], z["colors"], z["counts"], z["c2w"], z["K"]
off = np.concatenate([[0], np.cumsum(cnt)])
F = len(cnt)
H, W = 288, 384
fov = float(2*np.arctan((H/2)/K[0][1,1]))
print(f"{F} frames, {cnt.sum()} points, fov={np.degrees(fov):.1f} deg")

server = viser.ViserServer(port=0)
try:
    ser = server.get_scene_serializer()

    # static GT camera path
    server.scene.add_spline_catmull_rom(
        "/gt_path", positions=c2w[:, :3, 3].astype(np.float32),
        line_width=2.0, color=(250, 190, 60),
    ) if "positions" in viser.SceneApi.add_spline_catmull_rom.__doc__ or True else None

    for i in range(F):
        pts = P[off[i]:off[i+1]]
        col = C[off[i]:off[i+1]]
        server.scene.add_point_cloud(
            "/cloud", points=pts, colors=col,
            point_size=a.point_size, point_shape="rounded", precision="float16",
        )
        server.scene.add_camera_frustum(
            "/camera", fov=fov, aspect=W/H, scale=0.12, line_width=2.0,
            color=(255, 90, 90),
            wxyz=mat2wxyz(c2w[i, :3, :3]), position=c2w[i, :3, 3],
        )
        ser.insert_sleep(1.0 / a.fps)

    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    # serialize() may only be called once per serializer, so pick one output per run
    if a.html:
        hp = a.out.replace(".viser", "_standalone.html")
        html = ser.as_html(dark_mode=True)
        open(hp, "w").write(html)
        print(f"wrote {hp}  ({len(html)/1e6:.1f} MB)")
    else:
        data = ser.serialize()
        open(a.out, "wb").write(data)
        print(f"wrote {a.out}  ({len(data)/1e6:.1f} MB)")
finally:
    server.stop()
