"""Optional real Godot movie. Skips when the Godot binary is absent."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.godot_real

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "godot_sample"
REPO = Path(__file__).resolve().parents[1]


def _json_rows(text: str):
    rows = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("{"):
            continue
        try:
            rows.append(json.loads(stripped))
        except json.JSONDecodeError:
            continue
    return rows


def _tool(name: str):
    found = shutil.which(name)
    if found and Path(found).is_file():
        return found
    return None


def _godot():
    override = os.environ.get("COURIER_GODOT")
    if override and Path(override).is_file():
        return override
    return _tool("godot")


def _raw_frame(ffmpeg: str, mp4: Path, index: int) -> bytes:
    proc = subprocess.run(
        [
            ffmpeg, "-v", "error", "-i", str(mp4),
            "-vf", f"select=eq(n\\,{index})", "-frames:v", "1",
            "-f", "rawvideo", "-pix_fmt", "rgb24", "pipe:1",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if proc.returncode != 0 or not proc.stdout:
        raise AssertionError(proc.stderr.decode("utf-8", "replace")[:500])
    return proc.stdout


def _mean_abs(left: bytes, right: bytes) -> float:
    count = min(len(left), len(right))
    if count == 0:
        return 0.0
    return sum(abs(left[i] - right[i]) for i in range(count)) / count


def test_real_godot_movie_is_not_a_solid_clip(tmp_path):
    godot = _godot()
    if not godot:
        pytest.skip("godot is absent")
    xvfb = _tool("xvfb-run")
    ffmpeg = _tool("ffmpeg")
    ffprobe = _tool("ffprobe")
    if not xvfb or not ffmpeg or not ffprobe:
        pytest.skip("xvfb-run, ffmpeg, or ffprobe is absent")

    project = tmp_path / "project"
    shutil.copytree(FIXTURE, project)
    output = tmp_path / "out"
    env = os.environ.copy()
    env["LIBGL_ALWAYS_SOFTWARE"] = "1"
    env["GALLIUM_DRIVER"] = "llvmpipe"
    command = [
        xvfb, "-a", "-s", "-screen 0 800x1400x24",
        sys.executable, str(REPO / "scripts" / "render_godot_movie.py"),
        "--project", str(project),
        "--scene", "res://sample.tscn",
        "--output-dir", str(output),
        "--godot", godot,
        "--ffmpeg", ffmpeg,
        "--ffprobe", ffprobe,
        "--width", "720",
        "--height", "1280",
        "--lock-file", str(tmp_path / "heavy.lock"),
    ]
    proc = subprocess.run(command, cwd=REPO, env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "--headless" not in proc.stdout
    # Godot and ffmpeg write to the same stdout pipe, and the wrapper's print
    # is block-buffered there, so the JSON lines are not required to be first.
    launched = next(row for row in _json_rows(proc.stdout) if "command" in row)
    assert launched["command"][1:5] == ["--rendering-driver", "opengl3", "--rendering-method", "gl_compatibility"]
    assert "--write-movie" in launched["command"]
    assert launched["frame_limit"] == 90

    mp4 = output / "render.mp4"
    assert mp4.is_file() and mp4.stat().st_size > 0
    probe = subprocess.run(
        [
            ffprobe, "-v", "error", "-count_frames",
            "-show_entries", "format=duration:stream=codec_name,width,height,nb_read_frames,avg_frame_rate",
            "-of", "json", str(mp4),
        ],
        text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
    )
    assert probe.returncode == 0, probe.stderr
    info = json.loads(probe.stdout)
    video = next(stream for stream in info["streams"] if stream.get("codec_name") == "h264" or stream.get("width"))
    duration = float(info["format"]["duration"])
    frames = int(video["nb_read_frames"])
    assert video["width"] == 720 and video["height"] == 1280
    assert abs(duration - 3.0) <= 0.25
    assert frames >= 60

    early = _raw_frame(ffmpeg, mp4, 0)
    later = _raw_frame(ffmpeg, mp4, min(60, frames - 1))
    difference = _mean_abs(early, later)
    assert hashlib.sha256(early).hexdigest() != hashlib.sha256(later).hexdigest()
    assert difference > 5.0
    print(json.dumps({
        "duration": duration,
        "width": video["width"],
        "height": video["height"],
        "frames": frames,
        "codec": video.get("codec_name"),
        "frame_rate": video.get("avg_frame_rate"),
        "mean_abs_diff": round(difference, 3),
        "early_sha256": hashlib.sha256(early).hexdigest(),
        "later_sha256": hashlib.sha256(later).hexdigest(),
        "mp4_bytes": mp4.stat().st_size,
    }))
