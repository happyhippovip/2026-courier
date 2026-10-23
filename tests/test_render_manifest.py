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


def test_create_manifest_refuses_a_symlinked_parent(tmp_path):
    outside = tmp_path / "outside"
    render = outside / "render"
    render.mkdir(parents=True)
    (render / "render.mp4").write_bytes(b"video")
    link = tmp_path / "home"
    link.symlink_to(outside, target_is_directory=True)
    with pytest.raises(OSError, match="symlink"):
        create_manifest(link / "render")
    assert not (render / "manifest.json").exists()


def test_create_manifest_refuses_a_symlinked_directory(tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "render.mp4").write_bytes(b"video")
    link = tmp_path / "render"
    link.symlink_to(outside, target_is_directory=True)
    with pytest.raises(OSError, match="symlink"):
        create_manifest(link)
    assert not (outside / "manifest.json").exists()


def test_create_manifest_refuses_a_symlinked_manifest(tmp_path):
    render_dir = tmp_path / "render"
    render_dir.mkdir()
    (render_dir / "render.mp4").write_bytes(b"video")
    outside = tmp_path / "outside.json"
    outside.write_text("keep", encoding="utf-8")
    (render_dir / "manifest.json").symlink_to(outside)
    try:
        create_manifest(render_dir)
    except OSError as exc:
        assert "symlink" in str(exc).lower()
    else:
        raise AssertionError(outside.read_text(encoding="utf-8"))
    assert outside.read_text(encoding="utf-8") == "keep"


def test_bool_duration_is_not_recorded_as_one_second(tmp_path):
    render_dir = tmp_path / "render_bool"
    render_dir.mkdir()
    (render_dir / "render.mp4").write_bytes(b"VIDEO")
    with pytest.raises(ValueError, match="Bool"):
        got = create_manifest(render_dir, duration_seconds=True, fps=30)
        raise AssertionError(
            f"recorded duration {got.duration_seconds} frames {got.frame_count}"
        )
    assert not (render_dir / "manifest.json").exists()
    with pytest.raises(ValueError, match="Bool"):
        create_manifest(render_dir, duration_seconds=1.0, fps=True)
    with pytest.raises(ValueError, match="Bool"):
        create_manifest(render_dir, duration_seconds=1.0, fps=30, frame_count=True)
    assert not (render_dir / "manifest.json").exists()


def test_bool_size_does_not_verify_as_one_byte(tmp_path):
    render_dir = tmp_path / "render_size"
    render_dir.mkdir()
    (render_dir / "render.mp4").write_bytes(b"X")
    manifest = create_manifest(render_dir, duration_seconds=1.0, fps=30)
    data = json.loads((render_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest.target_size_bytes == 1
    data["target_size_bytes"] = True
    valid, reason = verify_manifest(data, render_dir=render_dir)
    assert valid is False, (valid, reason)

    fresh = json.loads((render_dir / "manifest.json").read_text(encoding="utf-8"))
    for art in fresh["artifacts"]:
        if art["path"] == "render.mp4":
            art["size_bytes"] = True
    valid, reason = verify_manifest(fresh, render_dir=render_dir)
    assert valid is False, (valid, reason)

    measured = json.loads((render_dir / "manifest.json").read_text(encoding="utf-8"))
    measured["duration_seconds"] = True
    valid, reason = verify_manifest(measured, render_dir=render_dir)
    assert valid is False, (valid, reason)


def _sha(data: bytes) -> str:
    import hashlib
    return hashlib.sha256(data).hexdigest()


def test_create_does_not_adopt_a_symlinked_target(tmp_path):
    outside = tmp_path / "outside.mp4"
    outside.write_bytes(b"FOREIGN-VIDEO")
    render_dir = tmp_path / "render"
    render_dir.mkdir()
    (render_dir / "render.mp4").symlink_to(outside)
    with pytest.raises(OSError, match="symlink"):
        got = create_manifest(render_dir)
        raise AssertionError(
            f"adopted {got.target_sha256} outside={outside.read_bytes()!r}"
        )
    assert outside.read_bytes() == b"FOREIGN-VIDEO"
    assert not (render_dir / "manifest.json").exists()


def test_create_does_not_adopt_a_symlinked_artifact(tmp_path):
    outside = tmp_path / "secret.txt"
    outside.write_bytes(b"SECRET")
    render_dir = tmp_path / "render"
    render_dir.mkdir()
    (render_dir / "render.mp4").write_bytes(b"VIDEO")
    (render_dir / "notes.txt").symlink_to(outside)
    with pytest.raises(OSError, match="symlink"):
        got = create_manifest(render_dir)
        adopted = [art for art in got.artifacts if art["sha256"] == _sha(b"SECRET")]
        raise AssertionError(f"adopted {adopted}")
    assert outside.read_bytes() == b"SECRET"
    assert not (render_dir / "manifest.json").exists()


def test_verify_does_not_accept_an_escaped_artifact(tmp_path):
    render_dir = tmp_path / "render"
    render_dir.mkdir()
    (render_dir / "render.mp4").write_bytes(b"VIDEO")
    outside = tmp_path / "secret.txt"
    outside.write_bytes(b"SECRET")
    create_manifest(render_dir)
    data = json.loads((render_dir / "manifest.json").read_text(encoding="utf-8"))
    data["artifacts"].append({
        "path": "../secret.txt",
        "size_bytes": len(b"SECRET"),
        "sha256": _sha(b"SECRET"),
    })
    valid, reason = verify_manifest(data, render_dir=render_dir)
    assert valid is False, (valid, reason)
    assert outside.read_bytes() == b"SECRET"


def test_verify_does_not_follow_a_manifest_symlink(tmp_path):
    render_dir = tmp_path / "render"
    render_dir.mkdir()
    (render_dir / "render.mp4").write_bytes(b"VIDEO")
    create_manifest(render_dir)
    link = tmp_path / "linked.json"
    link.symlink_to(render_dir / "manifest.json")
    valid, reason = verify_manifest(link)
    assert valid is False, (valid, reason)


def test_verify_does_not_follow_a_symlinked_target(tmp_path):
    outside = tmp_path / "outside.mp4"
    payload = b"FOREIGN-VIDEO"
    outside.write_bytes(payload)
    render_dir = tmp_path / "render"
    render_dir.mkdir()
    (render_dir / "render.mp4").symlink_to(outside)
    data = {
        "target_file": "render.mp4",
        "target_sha256": _sha(payload),
        "target_size_bytes": len(payload),
        "duration_seconds": 1.0,
        "fps": 30,
        "frame_count": 30,
        "artifacts": [],
    }
    valid, reason = verify_manifest(data, render_dir=render_dir)
    assert valid is False, (valid, reason)
    assert outside.read_bytes() == payload
