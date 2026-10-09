"""Unit tests for courier_core.render_manifest (P3)."""

import json
import pytest
from pathlib import Path

from courier_core.render_manifest import (
    create_manifest,
    verify_manifest,
    main,
    RenderManifest,
)


def test_create_manifest_missing_dir(tmp_path):
    with pytest.raises(FileNotFoundError, match="Render directory does not exist"):
        create_manifest(tmp_path / "nonexistent")


def test_create_manifest_missing_target(tmp_path):
    render_dir = tmp_path / "renders"
    render_dir.mkdir()
    with pytest.raises(FileNotFoundError, match="Target render file does not exist"):
        create_manifest(render_dir, target_filename="render.mp4")


def test_create_and_verify_manifest_happy_path(tmp_path):
    render_dir = tmp_path / "render_01"
    render_dir.mkdir()

    mp4 = render_dir / "render.mp4"
    mp4.write_bytes(b"FAKE MP4 CONTENT " * 100)

    avi = render_dir / "render.avi"
    avi.write_bytes(b"INTERMEDIATE AVI")

    meta = render_dir / "render_metadata.json"
    meta.write_text('{"scene": "hero", "renderer": "godot"}', encoding="utf-8")

    manifest = create_manifest(
        render_dir=render_dir,
        target_filename="render.mp4",
        scene="res://scenes/hero.tscn",
        duration_seconds=5.0,
        fps=60,
    )

    assert manifest.render_id.startswith("rnd-")
    assert manifest.frame_count == 300
    assert manifest.fps == 60
    assert manifest.duration_seconds == 5.0
    assert manifest.scene == "res://scenes/hero.tscn"
    assert len(manifest.artifacts) == 3
    assert len(manifest.manifest_sha256) == 64

    manifest_file = render_dir / "manifest.json"
    assert manifest_file.exists()

    # Verification passes
    valid, reason = verify_manifest(manifest_file)
    assert valid is True
    assert reason == "VERIFIED"


def test_verify_manifest_detects_tampered_target(tmp_path):
    render_dir = tmp_path / "render_tampered"
    render_dir.mkdir()
    mp4 = render_dir / "render.mp4"
    mp4.write_bytes(b"ORIGINAL VIDEO BYTES")

    manifest = create_manifest(render_dir, target_filename="render.mp4", duration_seconds=1.0)
    manifest_file = render_dir / "manifest.json"

    # Tamper with the video
    mp4.write_bytes(b"TAMPERED VIDEO BYTES")

    valid, reason = verify_manifest(manifest_file)
    assert valid is False
    assert "Target file sha256 mismatch" in reason


def test_verify_manifest_detects_missing_artifact(tmp_path):
    render_dir = tmp_path / "render_missing_art"
    render_dir.mkdir()
    mp4 = render_dir / "render.mp4"
    mp4.write_bytes(b"VIDEO")
    aux = render_dir / "aux.txt"
    aux.write_text("extra", encoding="utf-8")

    manifest = create_manifest(render_dir, target_filename="render.mp4")
    manifest_file = render_dir / "manifest.json"

    # Delete aux file
    aux.unlink()

    valid, reason = verify_manifest(manifest_file)
    assert valid is False
    assert "Artifact file missing" in reason


def test_verify_manifest_detects_tampered_artifact(tmp_path):
    render_dir = tmp_path / "render_tampered_art"
    render_dir.mkdir()
    mp4 = render_dir / "render.mp4"
    mp4.write_bytes(b"VIDEO")
    aux = render_dir / "aux.txt"
    aux.write_text("clean", encoding="utf-8")

    manifest = create_manifest(render_dir, target_filename="render.mp4")
    manifest_file = render_dir / "manifest.json"

    # Tamper with aux file without changing length if possible
    aux.write_text("dirty", encoding="utf-8")

    valid, reason = verify_manifest(manifest_file)
    assert valid is False
    assert "Artifact sha256 mismatch" in reason


def test_cli_create_and_verify(tmp_path, capsys):
    render_dir = tmp_path / "cli_render"
    render_dir.mkdir()
    mp4 = render_dir / "render.mp4"
    mp4.write_bytes(b"CLI VIDEO DATA")

    # CLI create
    ret = main(["create", "--dir", str(render_dir), "--target", "render.mp4", "--duration", "2.5", "--fps", "24"])
    assert ret == 0
    captured = capsys.readouterr()
    assert "Created render manifest:" in captured.out

    manifest_file = render_dir / "manifest.json"
    assert manifest_file.exists()

    # CLI verify
    ret_verify = main(["verify", "--manifest", str(manifest_file)])
    assert ret_verify == 0
    captured_verify = capsys.readouterr()
    assert "VERIFIED:" in captured_verify.out
