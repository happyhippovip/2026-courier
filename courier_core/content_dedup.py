"""Content-Addressed Storage (CAS) and Deduplication Engine.

Provides zero-redundancy chunked storage, integrity verification,
manifest-based file reconstruction, and orphan garbage collection.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable

_HEX_DIGEST_REGEX = re.compile(r"^[0-9a-f]{64}$")


class CASIntegrityError(Exception):
    """Raised when data retrieved from CAS fails SHA-256 verification."""


class CASSecurityError(Exception):
    """Raised when an invalid or malicious digest/path is supplied."""


@dataclass
class ArtifactManifest:
    """Manifest describing a file decomposed into content-addressed chunks."""

    file_name: str
    root_hash: str
    total_size: int
    chunk_size: int
    chunks: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ArtifactManifest:
        return cls(
            file_name=data["file_name"],
            root_hash=data["root_hash"],
            total_size=int(data["total_size"]),
            chunk_size=int(data["chunk_size"]),
            chunks=list(data["chunks"]),
        )


class ContentAddressedStore:
    """Content-Addressed Storage (CAS) with 2-level directory sharding."""

    def __init__(self, root: str | Path, chunk_size: int = 65536) -> None:
        self.root = Path(root).resolve()
        self.objects_dir = self.root / "objects"
        self.objects_dir.mkdir(parents=True, exist_ok=True)
        self.chunk_size = chunk_size

    def _validate_digest(self, digest: str) -> str:
        if not isinstance(digest, str) or not _HEX_DIGEST_REGEX.match(digest):
            raise CASSecurityError(f"Invalid or unsafe SHA-256 digest: {digest!r}")
        return digest

    def _object_path(self, digest: str) -> Path:
        valid_digest = self._validate_digest(digest)
        return self.objects_dir / valid_digest[:2] / valid_digest[2:4] / valid_digest

    def has_object(self, digest: str) -> bool:
        """Check if an object is present in the store without reading it."""
        try:
            return self._object_path(digest).is_file()
        except (CASSecurityError, ValueError):
            return False

    def store_bytes(self, data: bytes) -> str:
        """Store bytes into CAS, returning its SHA-256 hex digest."""
        digest = hashlib.sha256(data).hexdigest()
        dest_path = self._object_path(digest)

        if dest_path.is_file():
            # Already exists (zero redundancy)
            return digest

        dest_dir = dest_path.parent
        dest_dir.mkdir(parents=True, exist_ok=True)

        # Atomic write via temporary file
        temp_fd, temp_path = tempfile.mkstemp(prefix="cas_", dir=dest_dir)
        try:
            with os.fdopen(temp_fd, "wb") as f:
                f.write(data)
            os.replace(temp_path, dest_path)
        except Exception:
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except OSError:
                    pass
            raise

        return digest

    def retrieve_bytes(self, digest: str, verify_integrity: bool = True) -> bytes:
        """Retrieve stored bytes for a given digest with optional integrity verification."""
        path = self._object_path(digest)
        if not path.is_file():
            raise FileNotFoundError(f"CAS object not found: {digest}")

        data = path.read_bytes()

        if verify_integrity:
            actual = hashlib.sha256(data).hexdigest()
            if actual != digest:
                raise CASIntegrityError(
                    f"Integrity check failed: expected {digest}, got {actual}"
                )

        return data

    def store_file(self, file_path: str | Path) -> ArtifactManifest:
        """Decompose a file into content-addressed chunks and return a manifest."""
        path = Path(file_path).resolve()
        if not path.is_file():
            raise FileNotFoundError(f"Source file not found: {path}")

        file_hasher = hashlib.sha256()
        total_size = 0
        chunks: list[str] = []

        with path.open("rb") as f:
            while True:
                block = f.read(self.chunk_size)
                if not block:
                    break
                file_hasher.update(block)
                total_size += len(block)
                chunk_hash = self.store_bytes(block)
                chunks.append(chunk_hash)

        return ArtifactManifest(
            file_name=path.name,
            root_hash=file_hasher.hexdigest(),
            total_size=total_size,
            chunk_size=self.chunk_size,
            chunks=chunks,
        )

    def restore_file(
        self,
        manifest: ArtifactManifest,
        target_path: str | Path,
        verify_integrity: bool = True,
    ) -> Path:
        """Reconstruct a file from its manifest by reassembling stored chunks."""
        dest = Path(target_path).resolve()
        dest.parent.mkdir(parents=True, exist_ok=True)

        temp_fd, temp_path = tempfile.mkstemp(prefix="restore_", dir=dest.parent)
        file_hasher = hashlib.sha256()

        try:
            with os.fdopen(temp_fd, "wb") as f_out:
                for chunk_hash in manifest.chunks:
                    chunk_bytes = self.retrieve_bytes(chunk_hash, verify_integrity=verify_integrity)
                    file_hasher.update(chunk_bytes)
                    f_out.write(chunk_bytes)

            actual_root = file_hasher.hexdigest()
            if verify_integrity and actual_root != manifest.root_hash:
                raise CASIntegrityError(
                    f"Manifest reconstruction mismatch: expected {manifest.root_hash}, got {actual_root}"
                )

            os.replace(temp_path, dest)
        except Exception:
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except OSError:
                    pass
            raise

        return dest

    def get_stats(self, manifests: list[ArtifactManifest] | None = None) -> dict[str, Any]:
        """Calculate storage utilization, chunk counts, and deduplication ratios."""
        unique_chunks = 0
        stored_bytes = 0

        for p in self.objects_dir.glob("*/*/*"):
            if p.is_file() and not p.name.endswith(".tmp"):
                unique_chunks += 1
                stored_bytes += p.stat().st_size

        total_raw_bytes = 0
        if manifests:
            total_raw_bytes = sum(m.total_size for m in manifests)
        else:
            total_raw_bytes = stored_bytes

        dedup_ratio = 1.0
        if stored_bytes > 0:
            dedup_ratio = round(total_raw_bytes / stored_bytes, 4)

        bytes_saved = max(0, total_raw_bytes - stored_bytes)
        savings_percent = 0.0
        if total_raw_bytes > 0:
            savings_percent = round((bytes_saved / total_raw_bytes) * 100.0, 2)

        return {
            "unique_chunks": unique_chunks,
            "stored_bytes": stored_bytes,
            "total_raw_bytes": total_raw_bytes,
            "bytes_saved": bytes_saved,
            "dedup_ratio": dedup_ratio,
            "savings_percent": savings_percent,
        }

    def garbage_collect(self, active_manifests: Iterable[ArtifactManifest]) -> int:
        """Prune unreferenced/orphan chunks from CAS storage."""
        active_digests: set[str] = set()
        for manifest in active_manifests:
            active_digests.update(manifest.chunks)

        pruned_count = 0
        for p in list(self.objects_dir.glob("*/*/*")):
            if p.is_file():
                digest = p.name
                if digest not in active_digests:
                    p.unlink(missing_ok=True)
                    pruned_count += 1
                    # Clean up empty parent directories
                    parent = p.parent
                    if parent != self.objects_dir and not any(parent.iterdir()):
                        parent.rmdir()
                        grandparent = parent.parent
                        if grandparent != self.objects_dir and not any(grandparent.iterdir()):
                            grandparent.rmdir()

        return pruned_count


def main() -> None:
    parser = argparse.ArgumentParser(description="Artifact Content Deduplication Engine (CAS)")
    parser.add_argument("--root", default="./cas_storage", help="Root directory for CAS")
    subparsers = parser.add_subparsers(dest="action", required=True)

    # store
    store_p = subparsers.add_parser("store", help="Store a file into CAS")
    store_p.add_argument("file", help="File to store")
    store_p.add_argument("--chunk-size", type=int, default=65536, help="Chunk size in bytes")

    # restore
    restore_p = subparsers.add_parser("restore", help="Restore a file from manifest")
    restore_p.add_argument("manifest", help="Path to manifest JSON file")
    restore_p.add_argument("dest", help="Destination path for restored file")

    # stats
    subparsers.add_parser("stats", help="Show CAS statistics")

    # gc
    gc_p = subparsers.add_parser("gc", help="Run garbage collection")
    gc_p.add_argument("--manifests", nargs="+", required=True, help="Active manifest JSON files")

    args = parser.parse_args()
    store = ContentAddressedStore(args.root)

    if args.action == "store":
        store.chunk_size = args.chunk_size
        manifest = store.store_file(args.file)
        print(json.dumps(manifest.to_dict(), indent=2))
    elif args.action == "restore":
        manifest_data = json.loads(Path(args.manifest).read_text(encoding="utf-8"))
        manifest = ArtifactManifest.from_dict(manifest_data)
        out = store.restore_file(manifest, args.dest)
        print(f"Restored to {out}")
    elif args.action == "stats":
        stats = store.get_stats()
        print(json.dumps(stats, indent=2))
    elif args.action == "gc":
        manifests = [
            ArtifactManifest.from_dict(json.loads(Path(p).read_text(encoding="utf-8")))
            for p in args.manifests
        ]
        pruned = store.garbage_collect(manifests)
        print(f"Pruned {pruned} orphan chunks.")


if __name__ == "__main__":
    main()
