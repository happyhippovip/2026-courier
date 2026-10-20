"""Content-Addressable Immutable Cache Store with TTL & LRU Pruning.

Provides SHA-256 keyed content-addressable storage with tamper detection,
strict immutability guarantees, LRU capacity eviction, and TTL expiration pruning.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import hashlib
import json
import os
from pathlib import Path
import sys
import time
from typing import Any, Optional


class CasCacheError(Exception):
    """Base exception for CAS cache operations."""


class DigestMismatchError(CasCacheError):
    """Raised when an on-disk artifact digest does not match its expected hash."""


class ImmutableCollisionError(CasCacheError):
    """Raised when attempting to store divergent content under an existing digest."""


@dataclass
class CacheEntryMetadata:
    """Metadata tracking timestamps, sizes, and access counters for a CAS entry."""

    digest: str
    size_bytes: int
    created_at: float
    expires_at: Optional[float]
    last_accessed_at: float
    access_count: int
    tags: dict[str, str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CacheEntryMetadata:
        return cls(
            digest=str(data["digest"]),
            size_bytes=int(data["size_bytes"]),
            created_at=float(data["created_at"]),
            expires_at=float(data["expires_at"]) if data.get("expires_at") is not None else None,
            last_accessed_at=float(data["last_accessed_at"]),
            access_count=int(data.get("access_count", 0)),
            tags=dict(data.get("tags", {})),
        )


class ImmutableCasCache:
    """Content-Addressable Storage cache with LRU eviction and TTL pruning."""

    def __init__(
        self,
        cache_dir: str | Path,
        max_bytes: int = 100 * 1024 * 1024,
        default_ttl_seconds: Optional[float] = None,
    ) -> None:
        self.cache_dir = Path(cache_dir)
        self.objects_dir = self.cache_dir / "objects"
        self.index_path = self.cache_dir / "cas_index.json"
        self.max_bytes = max_bytes
        self.default_ttl_seconds = default_ttl_seconds

        self.objects_dir.mkdir(parents=True, exist_ok=True)
        self._index: dict[str, CacheEntryMetadata] = {}
        self._load_index()

    def _load_index(self) -> None:
        if not self.index_path.exists():
            return
        try:
            with open(self.index_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._index = {
                k: CacheEntryMetadata.from_dict(v) for k, v in data.get("entries", {}).items()
            }
        except Exception:
            self._index = {}

    def _save_index(self) -> None:
        payload = {
            "entries": {k: v.to_dict() for k, v in self._index.items()},
            "updated_at": time.time(),
        }
        tmp_file = self.index_path.with_suffix(".tmp")
        with open(tmp_file, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
        tmp_file.replace(self.index_path)

    def get_path(self, digest: str) -> Path:
        """Return the physical path for a content digest."""
        return self.objects_dir / digest

    def put(
        self,
        data: bytes,
        ttl_seconds: Optional[float] = None,
        tags: Optional[dict[str, str]] = None,
        now: Optional[float] = None,
    ) -> str:
        """Store bytes into CAS, returning SHA-256 digest."""
        if not isinstance(data, (bytes, bytearray)):
            raise TypeError("Data must be bytes or bytearray")

        curr_time = now if now is not None else time.time()
        digest = hashlib.sha256(data).hexdigest()
        file_path = self.get_path(digest)

        # Existing entry check
        if digest in self._index and file_path.exists():
            # Check immutability
            existing = file_path.read_bytes()
            if existing != data:
                raise ImmutableCollisionError(
                    f"Divergent payload detected for existing digest: {digest}"
                )
            return digest

        # Enforce LRU capacity limit
        incoming_size = len(data)
        self._evict_lru_if_needed(incoming_size, now=curr_time)

        # Determine TTL
        ttl = ttl_seconds if ttl_seconds is not None else self.default_ttl_seconds
        expires_at = (curr_time + ttl) if ttl is not None else None

        # Write to disk
        file_path.write_bytes(data)

        # Record metadata
        entry = CacheEntryMetadata(
            digest=digest,
            size_bytes=incoming_size,
            created_at=curr_time,
            expires_at=expires_at,
            last_accessed_at=curr_time,
            access_count=0,
            tags=tags or {},
        )
        self._index[digest] = entry
        self._save_index()

        return digest

    def get(self, digest: str, now: Optional[float] = None) -> Optional[bytes]:
        """Fetch bytes from CAS by digest, verifying integrity."""
        curr_time = now if now is not None else time.time()
        entry = self._index.get(digest)
        if not entry:
            return None

        # Check TTL
        if entry.expires_at is not None and curr_time > entry.expires_at:
            return None

        file_path = self.get_path(digest)
        if not file_path.exists():
            return None

        content = file_path.read_bytes()
        actual_hash = hashlib.sha256(content).hexdigest()
        if actual_hash != digest:
            raise DigestMismatchError(
                f"Cache entry corrupted: expected {digest}, got {actual_hash}"
            )

        # Update access stats
        entry.last_accessed_at = curr_time
        entry.access_count += 1
        self._save_index()

        return content

    def inspect(self, digest: str) -> Optional[dict[str, Any]]:
        """Retrieve metadata for a cached entry."""
        entry = self._index.get(digest)
        return entry.to_dict() if entry else None

    def prune_expired(self, now: Optional[float] = None) -> list[str]:
        """Remove all expired entries from disk and index."""
        curr_time = now if now is not None else time.time()
        pruned = []

        for digest, entry in list(self._index.items()):
            if entry.expires_at is not None and curr_time > entry.expires_at:
                pruned.append(digest)
                file_path = self.get_path(digest)
                if file_path.exists():
                    try:
                        file_path.unlink()
                    except Exception:
                        pass
                del self._index[digest]

        if pruned:
            self._save_index()

        return pruned

    def _evict_lru_if_needed(self, incoming_bytes: int, now: float) -> None:
        """Evict oldest accessed entries if total size exceeds max_bytes."""
        current_total = sum(e.size_bytes for e in self._index.values())

        if current_total + incoming_bytes <= self.max_bytes:
            return

        # Sort entries by last_accessed_at ascending
        sorted_entries = sorted(self._index.values(), key=lambda e: e.last_accessed_at)

        for entry in sorted_entries:
            if current_total + incoming_bytes <= self.max_bytes:
                break

            file_path = self.get_path(entry.digest)
            if file_path.exists():
                try:
                    file_path.unlink()
                except Exception:
                    pass

            current_total -= entry.size_bytes
            del self._index[entry.digest]

        self._save_index()


def main() -> None:
    parser = argparse.ArgumentParser(description="Content-Addressable Immutable Cache Store")
    subparsers = parser.add_subparsers(dest="action", required=True)

    # put
    put_p = subparsers.add_parser("put", help="Store content into CAS")
    put_p.add_argument("--dir", required=True, help="Cache directory")
    put_p.add_argument("--data", required=True, help="Data string to store")
    put_p.add_argument("--ttl", type=float, help="TTL in seconds")

    # get
    get_p = subparsers.add_parser("get", help="Retrieve content from CAS")
    get_p.add_argument("--dir", required=True, help="Cache directory")
    get_p.add_argument("--digest", required=True, help="SHA-256 digest")

    # inspect
    ins_p = subparsers.add_parser("inspect", help="Inspect CAS entry metadata")
    ins_p.add_argument("--dir", required=True, help="Cache directory")
    ins_p.add_argument("--digest", required=True, help="SHA-256 digest")

    # prune
    pru_p = subparsers.add_parser("prune", help="Prune expired CAS entries")
    pru_p.add_argument("--dir", required=True, help="Cache directory")

    args = parser.parse_args()
    cache = ImmutableCasCache(cache_dir=args.dir)

    if args.action == "put":
        digest = cache.put(args.data.encode("utf-8"), ttl_seconds=args.ttl)
        print(f"Stored object with digest: {digest}")

    elif args.action == "get":
        data = cache.get(args.digest)
        if data is not None:
            print(data.decode("utf-8", errors="replace"))
        else:
            print("<NOT_FOUND_OR_EXPIRED>")
            sys.exit(1)

    elif args.action == "inspect":
        info = cache.inspect(args.digest)
        print(json.dumps(info or {}, indent=2))

    elif args.action == "prune":
        pruned = cache.prune_expired()
        print(f"Pruned {len(pruned)} entries")


if __name__ == "__main__":
    main()
