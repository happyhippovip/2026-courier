"""Tests for courier_core.media_verify (P1).

Fixtures are tiny synthetic mp4s generated locally with ffmpeg (no network,
no committed binaries). Skipped when ffmpeg/ffprobe are unavailable.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from courier_core.media_verify import verify_mp4

HAVE_TOOLS = shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None

needs_tools = pytest.mark.skipif(not HAVE_TOOLS, reason="ffmpeg/ffprobe not on PATH")


def _run_ffmpeg(args: list[str]) -> None:
    subprocess.run(["ffmpeg", "-y", *args], capture_output=True, check=True, timeout=120)


@needs_tools
def test_good_mp4_passes(tmp_path: Path) -> None:
    out = tmp_path / "good.mp4"
    _run_ffmpeg(["-f", "lavfi", "-i", "testsrc=size=64x64:rate=10:duration=1",
                 "-f", "lavfi", "-i", "sine=frequency=440:duration=1",
                 "-c:v", "libx264", "-pix_fmt", "yuv420p",
                 "-c:a", "aac", "-shortest", str(out)])
    res = verify_mp4(out)
    assert res.ok, res.reason
    assert res.duration is not None and res.duration >= 0.5
    assert (res.width, res.height) == (64, 64)
    assert res.has_audio is True
    assert res.solid_color is False


@needs_tools
def test_missing_audio_fails(tmp_path: Path) -> None:
    out = tmp_path / "noaudio.mp4"
    _run_ffmpeg(["-f", "lavfi", "-i", "testsrc=size=64x64:rate=10:duration=1",
                 "-c:v", "libx264", "-pix_fmt", "yuv420p", str(out)])
    res = verify_mp4(out)
    assert not res.ok
    assert "audio" in res.reason.lower()


@needs_tools
def test_audio_optional_passes_without_audio(tmp_path: Path) -> None:
    out = tmp_path / "noaudio-ok.mp4"
    _run_ffmpeg(["-f", "lavfi", "-i", "testsrc=size=64x64:rate=10:duration=1",
                 "-c:v", "libx264", "-pix_fmt", "yuv420p", str(out)])
    res = verify_mp4(out, require_audio=False)
    assert res.ok, res.reason


@needs_tools
def test_solid_color_fails(tmp_path: Path) -> None:
    out = tmp_path / "solid.mp4"
    _run_ffmpeg(["-f", "lavfi", "-i", "color=c=red:size=64x64:rate=10:duration=1",
                 "-f", "lavfi", "-i", "sine=frequency=440:duration=1",
                 "-c:v", "libx264", "-pix_fmt", "yuv420p",
                 "-c:a", "aac", "-shortest", str(out)])
    res = verify_mp4(out)
    assert not res.ok
    assert "solid" in res.reason.lower()


@needs_tools
def test_short_duration_fails(tmp_path: Path) -> None:
    out = tmp_path / "short.mp4"
    _run_ffmpeg(["-f", "lavfi", "-i", "testsrc=size=64x64:rate=10:duration=0.2",
                 "-f", "lavfi", "-i", "sine=frequency=440:duration=0.2",
                 "-c:v", "libx264", "-pix_fmt", "yuv420p",
                 "-c:a", "aac", "-shortest", str(out)])
    res = verify_mp4(out, min_duration_s=0.5)
    assert not res.ok
    assert "duration" in res.reason.lower()


@needs_tools
def test_small_resolution_fails(tmp_path: Path) -> None:
    out = tmp_path / "small.mp4"
    _run_ffmpeg(["-f", "lavfi", "-i", "testsrc=size=32x32:rate=10:duration=1",
                 "-f", "lavfi", "-i", "sine=frequency=440:duration=1",
                 "-c:v", "libx264", "-pix_fmt", "yuv420p",
                 "-c:a", "aac", "-shortest", str(out)])
    res = verify_mp4(out, min_width=64, min_height=64)
    assert not res.ok
    assert "resolution" in res.reason.lower()


def test_missing_file_fails(tmp_path: Path) -> None:
    res = verify_mp4(tmp_path / "does-not-exist.mp4")
    assert not res.ok
    assert "not found" in res.reason.lower()


@needs_tools
def test_not_video_fails(tmp_path: Path) -> None:
    fake = tmp_path / "fake.mp4"
    fake.write_text("this is not a video", encoding="utf-8")
    res = verify_mp4(fake)
    assert not res.ok


def test_bad_parameters_raise(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        verify_mp4(tmp_path / "x.mp4", min_duration_s=-1)
    with pytest.raises(ValueError):
        verify_mp4(tmp_path / "x.mp4", min_width=0)
    with pytest.raises(ValueError):
        verify_mp4(tmp_path / "x.mp4", sample_frames=0)
