#!/usr/bin/env python3
"""Render a bound Godot scene with a deterministic Movie Maker frame limit.

This wrapper deliberately keeps the Godot project read-only.  It derives the
scene duration and capture FPS from the attached GDScript, then runs Movie
Maker with ``--quit-after round(duration * fps)``.  The AVI is only an
intermediate; the completed render is converted to a web-friendly MP4.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

try:
    CanonicalAuthority = None
except ImportError:
    pass

def _required_constant(script: Path, name: str) -> float:
    match = re.search(rf"^\s*const\s+{re.escape(name)}\s*:=\s*([0-9]+(?:\.[0-9]+)?)", script.read_text(encoding="utf-8"), re.MULTILINE)
    if not match:
        raise ValueError(f"Required constant {name} is missing from {script}")
    return float(match.group(1))


def scene_script(project: Path, scene: str) -> Path:
    if not scene.startswith("res://"):
        raise ValueError("Scene must use a res:// path")
    scene_file = project / scene.removeprefix("res://")
    text = scene_file.read_text(encoding="utf-8")
    match = re.search(r'path="res://([^"]+\.gd)"', text)
    if not match:
        raise ValueError(f"No attached GDScript found in {scene_file}")
    script = project / match.group(1)
    if not script.is_file():
        raise ValueError(f"Attached GDScript does not exist: {script}")
    return script


def movie_command(godot: str, project: Path, scene: str, avi: Path, fps: int, frames: int) -> list[str]:
    return [
        godot,
        "--rendering-driver", "opengl3",
        "--rendering-method", "gl_compatibility",
        "--path", str(project),
        "--write-movie", str(avi),
        "--fixed-fps", str(fps),
        "--quit-after", str(frames),
        "-d",
        scene,
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--scene", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--godot", default="/Users/user/Desktop/Godot.app/Contents/MacOS/Godot")
    parser.add_argument("--ffmpeg", default=shutil.which("ffmpeg") or "/usr/local/bin/ffmpeg")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    project = args.project.resolve()
    script = scene_script(project, args.scene)
    duration = _required_constant(script, "DURATION")
    fps = int(_required_constant(script, "CAPTURE_FPS"))
    frames = round(duration * fps)
    if duration <= 0 or fps <= 0 or frames <= 0:
        raise ValueError("Duration, FPS, and frame limit must be positive")
    if not Path(args.godot).is_file() or not Path(args.ffmpeg).is_file():
        raise FileNotFoundError("Godot or ffmpeg executable is unavailable")

    output_dir = args.output_dir.resolve()
    avi = output_dir / "render.avi"
    mp4 = output_dir / "render.mp4"
    metadata = output_dir / "render_metadata.json"

    command = movie_command(args.godot, project, args.scene, avi, fps, frames)
    print(json.dumps({"duration_seconds": duration, "fps": fps, "frame_limit": frames, "command": command}, separators=(",", ":")))
    if args.dry_run:
        return 0

    auth = CanonicalAuthority() if CanonicalAuthority else None
    owner_id = "render_godot_movie"
    task_id = f"godot_render_{output_dir.name}"
    if auth:
        success, gen, err = auth.acquire_heavy_authority(
            owner_id=owner_id,
            task_id=task_id,
            metadata={"project": str(project), "scene": args.scene},
        )
        if not success:
            print(f"CANONICAL_AUTHORITY_DENIED: {err}", file=sys.stderr)
            return 1
    else:
        success, gen, err = True, 1, None

    try:
        output_dir.mkdir(parents=True, exist_ok=True)
        if avi.exists() or mp4.exists() or metadata.exists():
            raise FileExistsError("Output directory must be empty for a deterministic render")

        godot_result = subprocess.run(command, check=False)
        if godot_result.returncode != 0 or not avi.is_file() or avi.stat().st_size == 0:
            print("Godot Movie Maker failed; AVI preserved for diagnosis.", file=sys.stderr)
            return 1

        ffmpeg_command = [
            args.ffmpeg, "-y", "-i", str(avi), "-map", "0:v:0", "-map", "0:a?",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-movflags", "+faststart", str(mp4),
        ]
        ffmpeg_result = subprocess.run(ffmpeg_command, check=False)
        if ffmpeg_result.returncode != 0 or not mp4.is_file() or mp4.stat().st_size == 0:
            print("MP4 conversion failed; AVI preserved for diagnosis.", file=sys.stderr)
            return 1

        probe = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "stream=codec_name,width,height:format=duration", "-of", "json", str(mp4)],
            text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
        )
        if probe.returncode != 0:
            print("MP4 probe failed; AVI preserved for diagnosis.", file=sys.stderr)
            return 1
        info = json.loads(probe.stdout)
        stream = (info.get("streams") or [{}])[0]
        actual_duration = float(info.get("format", {}).get("duration", 0.0))
        if stream.get("codec_name") != "h264" or (stream.get("width"), stream.get("height")) != (360, 640) or abs(actual_duration - duration) > 0.25:
            print("MP4 did not meet expected H.264 360x640 constraints; AVI preserved for diagnosis.", file=sys.stderr)
            return 1
        metadata.write_text(json.dumps({"duration_seconds": duration, "fps": fps, "frame_limit": frames, "mp4_duration_seconds": actual_duration, "mp4_probe": stream}, indent=2) + "\n", encoding="utf-8")
        avi.unlink()
        print(json.dumps({"status": "COMPLETE", "mp4": str(mp4), "metadata": str(metadata)}, separators=(",", ":")))
        return 0
    finally:
        if auth:
            auth.release_heavy_authority(
                owner_id=owner_id,
                task_id=task_id,
                generation=gen,
            )


if __name__ == "__main__":
    raise SystemExit(main())
