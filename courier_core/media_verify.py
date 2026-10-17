"""ffprobe-based verification for a rendered mp4 (lane L4).

Checks, fail-closed, that a file is a real rendered video:

- the file exists and ffprobe can parse it;
- duration is at least ``min_duration_s`` seconds;
- the first video stream is at least ``min_width`` x ``min_height``;
- an audio stream is present when ``require_audio`` is true;
- the picture is not a single solid color (sampled frames decoded with
  ffmpeg must show color spread above ``solid_tolerance``).

Only the local ``ffprobe``/``ffmpeg`` binaries are used. No network access,
no credentials. On unparseable media the result is ``ok=False``, never an
exception; exceptions are reserved for programming errors (bad parameters)
and for missing ``ffprobe``/``ffmpeg`` binaries.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

__all__ = ["MediaCheck", "verify_mp4", "DEFAULT_MIN_DURATION_S",
           "DEFAULT_MIN_WIDTH", "DEFAULT_MIN_HEIGHT"]

DEFAULT_MIN_DURATION_S = 0.5
DEFAULT_MIN_WIDTH = 16
DEFAULT_MIN_HEIGHT = 16
_DEFAULT_SAMPLE_FRAMES = 4
_DEFAULT_SOLID_TOLERANCE = 4
_PROBE_TIMEOUT_S = 30
_DECODE_TIMEOUT_S = 60


@dataclass(frozen=True)
class MediaCheck:
    """Outcome of :func:`verify_mp4`."""

    ok: bool
    reason: str = ""
    duration: float | None = None
    width: int | None = None
    height: int | None = None
    has_audio: bool = False
    solid_color: bool | None = None
    details: dict = field(default_factory=dict)


def _resolve_binary(name: str, override: str | None) -> str:
    if override:
        return override
    found = shutil.which(name)
    if not found:
        raise FileNotFoundError(f"required binary not found on PATH: {name}")
    return found


def _probe(path: Path, ffprobe_exe: str) -> dict:
    cmd = [ffprobe_exe, "-v", "error", "-show_format", "-show_streams",
           "-of", "json", str(path)]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True,
                              timeout=_PROBE_TIMEOUT_S, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"error": f"ffprobe could not run: {type(exc).__name__}"}
    if proc.returncode != 0:
        err = (proc.stderr or "").strip()[:300]
        return {"error": f"ffprobe failed for {path.name}: {err or 'unreadable file'}"}
    try:
        return json.loads(proc.stdout or "{}")
    except json.JSONDecodeError:
        return {"error": "ffprobe returned invalid JSON"}


def _first_video_stream(streams: list) -> dict | None:
    for stream in streams:
        if isinstance(stream, dict) and stream.get("codec_type") == "video":
            return stream
    return None


def _has_audio_stream(streams: list) -> bool:
    return any(isinstance(s, dict) and s.get("codec_type") == "audio"
               for s in streams)


def _parse_duration(probe: dict, video: dict | None) -> float | None:
    for candidate in (probe.get("format", {}).get("duration"),
                      (video or {}).get("duration")):
        if candidate is None:
            continue
        try:
            value = float(candidate)
        except (TypeError, ValueError):
            continue
        if value >= 0:
            return value
    return None


def _sampled_color_spread(path: Path, ffmpeg_exe: str,
                          sample_frames: int) -> int | None:
    """Max per-channel spread over sampled decoded frames; None on failure."""
    cmd = [ffmpeg_exe, "-v", "error", "-i", str(path),
           "-vf", "fps=2,scale=32:32", "-frames:v", str(sample_frames),
           "-f", "rawvideo", "-pix_fmt", "rgb24", "-"]
    try:
        proc = subprocess.run(cmd, capture_output=True, timeout=_DECODE_TIMEOUT_S,
                              check=False)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if proc.returncode != 0 or not proc.stdout:
        return None
    data = proc.stdout
    frame_size = 32 * 32 * 3
    usable = (len(data) // frame_size) * frame_size
    if usable == 0:
        return None
    data = data[:usable]
    spread_r = max(data[0::3]) - min(data[0::3])
    spread_g = max(data[1::3]) - min(data[1::3])
    spread_b = max(data[2::3]) - min(data[2::3])
    return max(spread_r, spread_g, spread_b)


def verify_mp4(path: str | Path,
               *,
               min_duration_s: float = DEFAULT_MIN_DURATION_S,
               min_width: int = DEFAULT_MIN_WIDTH,
               min_height: int = DEFAULT_MIN_HEIGHT,
               require_audio: bool = True,
               sample_frames: int = _DEFAULT_SAMPLE_FRAMES,
               solid_tolerance: int = _DEFAULT_SOLID_TOLERANCE,
               ffprobe_exe: str | None = None,
               ffmpeg_exe: str | None = None) -> MediaCheck:
    """Verify a rendered mp4 file with ffprobe/ffmpeg.

    Returns a :class:`MediaCheck` with ``ok=True`` only when every enabled
    check passes. Unparseable or missing media yields ``ok=False``.
    """
    if min_duration_s < 0:
        raise ValueError("min_duration_s must be >= 0")
    if min_width < 1 or min_height < 1:
        raise ValueError("min_width and min_height must be >= 1")
    if sample_frames < 1:
        raise ValueError("sample_frames must be >= 1")
    if solid_tolerance < 0:
        raise ValueError("solid_tolerance must be >= 0")

    target = Path(path)
    if not target.is_file():
        return MediaCheck(ok=False, reason=f"file not found: {target.name}")

    ffprobe = _resolve_binary("ffprobe", ffprobe_exe)
    ffmpeg = _resolve_binary("ffmpeg", ffmpeg_exe)

    probe = _probe(target, ffprobe)
    if "error" in probe:
        return MediaCheck(ok=False, reason=str(probe["error"])[:300])

    streams = probe.get("streams")
    if not isinstance(streams, list):
        return MediaCheck(ok=False, reason="ffprobe returned no streams")

    video = _first_video_stream(streams)
    if video is None:
        return MediaCheck(ok=False, reason="no video stream found",
                          has_audio=_has_audio_stream(streams))
    try:
        width = int(video.get("width"))
        height = int(video.get("height"))
    except (TypeError, ValueError):
        return MediaCheck(ok=False, reason="video stream has no resolution",
                          has_audio=_has_audio_stream(streams))
    has_audio = _has_audio_stream(streams)
    duration = _parse_duration(probe, video)

    if duration is None:
        return MediaCheck(ok=False, reason="could not determine duration",
                          duration=None, width=width, height=height,
                          has_audio=has_audio)
    if duration < min_duration_s:
        return MediaCheck(ok=False,
                          reason=f"duration {duration:.2f}s below minimum {min_duration_s:.2f}s",
                          duration=duration, width=width, height=height,
                          has_audio=has_audio)
    if width < min_width or height < min_height:
        return MediaCheck(ok=False,
                          reason=f"resolution {width}x{height} below minimum {min_width}x{min_height}",
                          duration=duration, width=width, height=height,
                          has_audio=has_audio)
    if require_audio and not has_audio:
        return MediaCheck(ok=False, reason="no audio stream found",
                          duration=duration, width=width, height=height,
                          has_audio=False)

    spread = _sampled_color_spread(target, ffmpeg, sample_frames)
    if spread is None:
        return MediaCheck(ok=False, reason="could not decode video frames",
                          duration=duration, width=width, height=height,
                          has_audio=has_audio)
    solid = spread <= solid_tolerance
    if solid:
        return MediaCheck(ok=False, reason="video is a single solid color",
                          duration=duration, width=width, height=height,
                          has_audio=has_audio, solid_color=True,
                          details={"color_spread": spread})
    return MediaCheck(ok=True, reason="mp4 passed all media checks",
                      duration=duration, width=width, height=height,
                      has_audio=has_audio, solid_color=False,
                      details={"color_spread": spread})
