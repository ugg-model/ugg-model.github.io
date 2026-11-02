"""Shared media export helpers for the selected website gallery cases."""
import hashlib
import subprocess

import imageio_ffmpeg
import matplotlib
matplotlib.use("Agg")
import numpy as np


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def encode_frames(frames, output, fps):
    height, width = frames.shape[1:3]
    command = [imageio_ffmpeg.get_ffmpeg_exe(), "-hide_banner", "-loglevel", "error",
               "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{width}x{height}",
               "-r", str(fps), "-i", "-", "-an", "-c:v", "libx264", "-crf", "20",
               "-pix_fmt", "yuv420p", "-vf", "pad=ceil(iw/2)*2:ceil(ih/2)*2",
               "-movflags", "+faststart", str(output)]
    subprocess.run(command, input=frames.tobytes(), check=True)


def poster(video, output):
    subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-hide_banner", "-loglevel", "error",
                    "-y", "-i", str(video), "-frames:v", "1", str(output)], check=True)


def colors(values):
    return (matplotlib.colormaps["turbo"](values)[..., :3] * 255).astype(np.uint8)
