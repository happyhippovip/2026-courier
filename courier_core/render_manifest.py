"""Render Manifest writer and verifier for Courier render tasks (P3).

Creates and cryptographically verifies an immutable manifest for one finished
render output directory, recording artifact hashes, frame counts, duration,
and scene metadata.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from courier_core.events import canonical_json


@dataclass(frozen=True)
class RenderArtifact:
    path: str
    size_bytes: int
    sha256: str


@dataclass(frozen=True)
class RenderManifest:
    render_id: str
    target_file: str
    target_sha256: str
    target_size_bytes: int
    duration_seconds: float
    fps: int
    frame_count: int
    scene: str | None
    created_at_utc: str
    artifacts: list[dict[str, Any]]
    manifest_sha256: str
    extra_metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "render_id": self.render_id,
            "target_file": self.target_file,
            "target_sha256": self.target_sha256,
            "target_size_bytes": self.target_size_bytes,
            "duration_seconds": self.duration_seconds,
            "fps": self.fps,
            "frame_count": self.frame_count,
            "scene": self.scene,
            "created_at_utc": self.created_at_utc,
            "artifacts": self.artifacts,
            "manifest_sha256": self.manifest_sha256,
            "extra_metadata": self.extra_metadata,
        }


def _file_sha256(path: Path) -> str:
    """Compute sha256 in chunks to support large render files safely."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def create_manifest(
    render_dir: Path | str,
    target_filename: str = "render.mp4",
    scene: str | None = None,
    duration_seconds: float = 0.0,
    fps: int = 30,
    frame_count: int | None = None,
    extra_metadata: dict[str, Any] | None = None,
) -> RenderManifest:
    """Create a verified RenderManifest for a finished render directory."""
    dir_path = Path(render_dir).resolve()
    if not dir_path.is_dir():
        raise FileNotFoundError(f"Render directory does not exist: {dir_path}")

    target_path = dir_path / target_filename
    if not target_path.is_file():
        raise FileNotFoundError(f"Target render file does not exist: {target_path}")

    target_sha256 = _file_sha256(target_path)
    target_size = target_path.stat().st_size

    calculated_frames = frame_count if frame_count is not None else round(duration_seconds * fps)

    # Collect all files in directory (excluding manifest.json itself)
    artifacts: list[dict[str, Any]] = []
    for item in sorted(dir_path.rglob("*")):
        if item.is_file() and item.name != "manifest.json":
            rel = str(item.relative_to(dir_path))
            artifacts.append({
                "path": rel,
                "size_bytes": item.stat().st_size,
                "sha256": _file_sha256(item),
            })

    created_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    render_id = "rnd-" + hashlib.sha256(f"{target_sha256}:{created_at}".encode("utf-8")).hexdigest()[:24]

    core_data = {
        "render_id": render_id,
        "target_file": target_filename,
        "target_sha256": target_sha256,
        "target_size_bytes": target_size,
        "duration_seconds": float(duration_seconds),
        "fps": int(fps),
        "frame_count": int(calculated_frames),
        "scene": scene,
        "created_at_utc": created_at,
        "artifacts": artifacts,
        "extra_metadata": extra_metadata or {},
    }

    manifest_hash = hashlib.sha256(canonical_json(core_data).encode("utf-8")).hexdigest()

    manifest = RenderManifest(
        render_id=render_id,
        target_file=target_filename,
        target_sha256=target_sha256,
        target_size_bytes=target_size,
        duration_seconds=float(duration_seconds),
        fps=int(fps),
        frame_count=int(calculated_frames),
        scene=scene,
        created_at_utc=created_at,
        artifacts=artifacts,
        manifest_sha256=manifest_hash,
        extra_metadata=extra_metadata or {},
    )

    # Write manifest.json atomically into render directory
    manifest_file = dir_path / "manifest.json"
    manifest_file.write_text(canonical_json(manifest.to_dict()), encoding="utf-8")

    return manifest


def verify_manifest(manifest_path_or_dict: Path | str | dict[str, Any], render_dir: Path | str | None = None) -> tuple[bool, str]:
    """Verify that a manifest matches the physical files in the render directory.

    Returns (is_valid, reason).
    """
    if isinstance(manifest_path_or_dict, (Path, str)):
        manifest_file = Path(manifest_path_or_dict).resolve()
        if not manifest_file.is_file():
            return False, f"Manifest file does not exist: {manifest_file}"
        try:
            data = json.loads(manifest_file.read_text(encoding="utf-8"))
        except Exception as exc:
            return False, f"Manifest JSON is malformed: {exc}"
        if render_dir is None:
            render_dir = manifest_file.parent
    else:
        data = manifest_path_or_dict
        if render_dir is None:
            return False, "render_dir must be specified when verifying raw manifest dictionary"

    dir_path = Path(render_dir).resolve()
    if not dir_path.is_dir():
        return False, f"Render directory does not exist: {dir_path}"

    target_name = data.get("target_file")
    if not target_name:
        return False, "Manifest missing target_file"

    target_path = dir_path / target_name
    if not target_path.is_file():
        return False, f"Target file does not exist: {target_path}"

    if _file_sha256(target_path) != data.get("target_sha256"):
        return False, "Target file sha256 mismatch"

    if target_path.stat().st_size != data.get("target_size_bytes"):
        return False, "Target file size mismatch"

    artifacts = data.get("artifacts")
    if not isinstance(artifacts, list):
        return False, "Manifest artifacts must be a list"

    for art in artifacts:
        rel = art.get("path")
        expected_sha = art.get("sha256")
        expected_size = art.get("size_bytes")
        if not rel or not expected_sha or expected_size is None:
            return False, f"Malformed artifact entry: {art}"

        art_file = dir_path / rel
        if not art_file.is_file():
            return False, f"Artifact file missing: {art_file}"

        if art_file.stat().st_size != expected_size:
            return False, f"Artifact size mismatch for {rel}"

        if _file_sha256(art_file) != expected_sha:
            return False, f"Artifact sha256 mismatch for {rel}"

    return True, "VERIFIED"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Courier Render Manifest Tool (P3)")
    subparsers = parser.add_subparsers(dest="command", required=True)

    create_p = subparsers.add_parser("create", help="Create a manifest for a render directory")
    create_p.add_argument("--dir", type=Path, required=True, help="Render directory")
    create_p.add_argument("--target", default="render.mp4", help="Target filename (default: render.mp4)")
    create_p.add_argument("--scene", default=None, help="Scene identifier (optional)")
    create_p.add_argument("--duration", type=float, default=0.0, help="Duration in seconds")
    create_p.add_argument("--fps", type=int, default=30, help="FPS")
    create_p.add_argument("--frames", type=int, default=None, help="Total frames")

    verify_p = subparsers.add_parser("verify", help="Verify an existing render manifest")
    verify_p.add_argument("--manifest", type=Path, required=True, help="Path to manifest.json")
    verify_p.add_argument("--dir", type=Path, default=None, help="Render directory (optional)")

    args = parser.parse_args(argv)

    if args.command == "create":
        try:
            manifest = create_manifest(
                render_dir=args.dir,
                target_filename=args.target,
                scene=args.scene,
                duration_seconds=args.duration,
                fps=args.fps,
                frame_count=args.frames,
            )
            print(f"Created render manifest: {manifest.render_id} (digest: {manifest.manifest_sha256})")
            return 0
        except Exception as exc:
            print(f"Error creating manifest: {exc}", file=sys.stderr)
            return 1

    if args.command == "verify":
        valid, reason = verify_manifest(args.manifest, render_dir=args.dir)
        if valid:
            print(f"VERIFIED: {args.manifest}")
            return 0
        else:
            print(f"FAILED: {reason}", file=sys.stderr)
            return 1

    return 2


if __name__ == "__main__":
    sys.exit(main())
