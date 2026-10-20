"""Incremental Artifact Delta Patcher.

Calculates binary/chunk diffs between artifacts and applies patches with
SHA-256 pre-verification of base files and post-verification of targets.
"""

from __future__ import annotations

import argparse
import base64
from dataclasses import asdict, dataclass
import hashlib
import json
import os
from pathlib import Path
import tempfile
from typing import Any


class BaseFileMismatchError(Exception):
    """Raised when base file SHA-256 does not match patch prerequisite."""


class TargetCorruptError(Exception):
    """Raised when reconstructed target file fails SHA-256 verification."""


class InvalidPatchError(Exception):
    """Raised when a patch format or operation is malformed."""


@dataclass
class DeltaPatch:
    """Descriptor and payload for an incremental artifact patch."""

    base_sha256: str
    base_size: int
    target_sha256: str
    target_size: int
    chunk_size: int
    operations: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DeltaPatch:
        return cls(
            base_sha256=str(data["base_sha256"]),
            base_size=int(data["base_size"]),
            target_sha256=str(data["target_sha256"]),
            target_size=int(data["target_size"]),
            chunk_size=int(data.get("chunk_size", 64)),
            operations=list(data["operations"]),
        )

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)

    @classmethod
    def from_json(cls, s: str) -> DeltaPatch:
        return cls.from_dict(json.loads(s))


class DeltaPatcher:
    """Engine for generating and applying binary delta patches."""

    def __init__(self, chunk_size: int = 64) -> None:
        self.chunk_size = max(8, chunk_size)

    def create_patch(self, base_file: str | Path, target_file: str | Path) -> DeltaPatch:
        """Create a delta patch transforming base_file into target_file."""
        base_path = Path(base_file).resolve()
        target_path = Path(target_file).resolve()

        if not base_path.is_file():
            raise FileNotFoundError(f"Base file not found: {base_path}")
        if not target_path.is_file():
            raise FileNotFoundError(f"Target file not found: {target_path}")

        base_bytes = base_path.read_bytes()
        target_bytes = target_path.read_bytes()

        base_sha256 = hashlib.sha256(base_bytes).hexdigest()
        target_sha256 = hashlib.sha256(target_bytes).hexdigest()

        base_size = len(base_bytes)
        target_size = len(target_bytes)

        # Fast path: identical content
        if base_bytes == target_bytes:
            ops = [{"type": "COPY", "offset": 0, "length": base_size}] if base_size > 0 else []
            return DeltaPatch(
                base_sha256=base_sha256,
                base_size=base_size,
                target_sha256=target_sha256,
                target_size=target_size,
                chunk_size=self.chunk_size,
                operations=ops,
            )

        # Index chunks of base_bytes
        chunk_index: dict[bytes, int] = {}
        if base_size >= self.chunk_size:
            step = max(1, self.chunk_size // 2)
            for i in range(0, base_size - self.chunk_size + 1, step):
                chunk = base_bytes[i : i + self.chunk_size]
                if chunk not in chunk_index:
                    chunk_index[chunk] = i

        operations: list[dict[str, Any]] = []
        pending_insert = bytearray()

        def flush_insert() -> None:
            if pending_insert:
                operations.append({
                    "type": "INSERT",
                    "data_b64": base64.b64encode(bytes(pending_insert)).decode("ascii"),
                })
                pending_insert.clear()

        pos = 0
        while pos < target_size:
            block = target_bytes[pos : pos + self.chunk_size]
            if len(block) == self.chunk_size and block in chunk_index:
                flush_insert()
                base_offset = chunk_index[block]
                match_len = self.chunk_size

                # Extend match
                while (
                    pos + match_len < target_size
                    and base_offset + match_len < base_size
                    and target_bytes[pos + match_len] == base_bytes[base_offset + match_len]
                ):
                    match_len += 1

                operations.append({
                    "type": "COPY",
                    "offset": base_offset,
                    "length": match_len,
                })
                pos += match_len
            else:
                pending_insert.append(target_bytes[pos])
                pos += 1

        flush_insert()

        return DeltaPatch(
            base_sha256=base_sha256,
            base_size=base_size,
            target_sha256=target_sha256,
            target_size=target_size,
            chunk_size=self.chunk_size,
            operations=operations,
        )

    def apply_patch(
        self,
        base_file: str | Path,
        patch: DeltaPatch,
        target_file: str | Path,
    ) -> Path:
        """Apply a delta patch to base_file and atomically write to target_file."""
        base_path = Path(base_file).resolve()
        target_path = Path(target_file).resolve()

        if not base_path.is_file():
            raise FileNotFoundError(f"Base file not found: {base_path}")

        base_bytes = base_path.read_bytes()
        actual_base_sha256 = hashlib.sha256(base_bytes).hexdigest()

        if actual_base_sha256 != patch.base_sha256:
            raise BaseFileMismatchError(
                f"Base file mismatch: expected {patch.base_sha256}, got {actual_base_sha256}"
            )

        target_path.parent.mkdir(parents=True, exist_ok=True)
        temp_fd, temp_path = tempfile.mkstemp(prefix="patch_", dir=target_path.parent)
        target_hasher = hashlib.sha256()

        try:
            with os.fdopen(temp_fd, "wb") as f_out:
                for op in patch.operations:
                    op_type = op.get("type")
                    if op_type == "COPY":
                        offset = int(op["offset"])
                        length = int(op["length"])
                        data = base_bytes[offset : offset + length]
                        f_out.write(data)
                        target_hasher.update(data)
                    elif op_type == "INSERT":
                        data = base64.b64decode(op["data_b64"])
                        f_out.write(data)
                        target_hasher.update(data)
                    else:
                        raise InvalidPatchError(f"Unsupported patch operation: {op_type}")

            actual_target_sha256 = target_hasher.hexdigest()
            if actual_target_sha256 != patch.target_sha256:
                raise TargetCorruptError(
                    f"Reconstructed target mismatch: expected {patch.target_sha256}, got {actual_target_sha256}"
                )

            os.replace(temp_path, target_path)
        except Exception:
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except OSError:
                    pass
            raise

        return target_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Incremental Artifact Delta Patcher")
    subparsers = parser.add_subparsers(dest="action", required=True)

    # diff
    diff_p = subparsers.add_parser("diff", help="Create a delta patch between base and target")
    diff_p.add_argument("--base", required=True, help="Base file path")
    diff_p.add_argument("--target", required=True, help="Target file path")
    diff_p.add_argument("--output", required=True, help="Output patch file path")
    diff_p.add_argument("--chunk-size", type=int, default=64, help="Chunk size for diffing")

    # patch
    patch_p = subparsers.add_parser("patch", help="Apply a delta patch to base file")
    patch_p.add_argument("--base", required=True, help="Base file path")
    patch_p.add_argument("--patch", required=True, help="Patch file path")
    patch_p.add_argument("--output", required=True, help="Output reconstructed file path")

    # info
    info_p = subparsers.add_parser("info", help="Inspect a delta patch file")
    info_p.add_argument("--patch", required=True, help="Patch file path")

    args = parser.parse_args()
    patcher = DeltaPatcher()

    if args.action == "diff":
        patcher.chunk_size = args.chunk_size
        patch = patcher.create_patch(args.base, args.target)
        Path(args.output).write_text(patch.to_json(), encoding="utf-8")
        print(f"Wrote patch to {args.output}")
    elif args.action == "patch":
        patch_data = Path(args.patch).read_text(encoding="utf-8")
        patch = DeltaPatch.from_json(patch_data)
        out = patcher.apply_patch(args.base, patch, args.output)
        print(f"Applied patch to {out}")
    elif args.action == "info":
        patch_data = Path(args.patch).read_text(encoding="utf-8")
        patch = DeltaPatch.from_json(patch_data)
        print(json.dumps({
            "base_sha256": patch.base_sha256,
            "base_size": patch.base_size,
            "target_sha256": patch.target_sha256,
            "target_size": patch.target_size,
            "operations_count": len(patch.operations),
        }, indent=2))


if __name__ == "__main__":
    main()
