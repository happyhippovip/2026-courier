"""Distributed Ephemeral Storage Cache with TTL and Cryptographic Integrity (P34)

Provides in-memory and disk-backed caching with LRU eviction, time-to-live (TTL)
expiration, SHA-256 cryptographic tampering detection, and hit-ratio telemetry.
"""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
import os
import sys
import tempfile
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


class CacheIntegrityError(Exception):
    """Raised when an entry's stored value fails cryptographic checksum validation."""
    pass


def _compute_value_hash(value: Any) -> str:
    try:
        canonical_json = json.dumps(value, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()
    except (TypeError, ValueError):
        # Fallback to string representation
        return hashlib.sha256(repr(value).encode("utf-8")).hexdigest()


@dataclass
class CacheEntry:
    key: str
    value: Any
    created_at: float
    expires_at: Optional[float] = None
    checksum_sha256: str = ""
    access_count: int = 0
    last_accessed: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "key": self.key,
            "value": self.value,
            "created_at": self.created_at,
            "expires_at": self.expires_at,
            "checksum_sha256": self.checksum_sha256,
            "access_count": self.access_count,
            "last_accessed": self.last_accessed,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> CacheEntry:
        return cls(
            key=str(data.get("key", "")),
            value=data.get("value"),
            created_at=float(data.get("created_at", 0.0)),
            expires_at=data.get("expires_at"),
            checksum_sha256=str(data.get("checksum_sha256", "")),
            access_count=int(data.get("access_count", 0)),
            last_accessed=float(data.get("last_accessed", 0.0)),
        )


class EphemeralCache:
    """Thread-safe LRU cache with TTL expiration, cryptographic verification, and disk persistence."""

    def __init__(
        self,
        max_items: int = 100,
        default_ttl: Optional[float] = None,
        persistence_path: Optional[Path | str] = None,
    ) -> None:
        self.max_items = max_items
        self.default_ttl = default_ttl
        self.persistence_path = Path(persistence_path) if persistence_path else None
        self._entries: collections.OrderedDict[str, CacheEntry] = collections.OrderedDict()
        self._lock = threading.Lock()
        self._hits = 0
        self._misses = 0
        self._evictions = 0
        self._expirations = 0

        if self.persistence_path:
            self.persistence_path.parent.mkdir(parents=True, exist_ok=True)

    def get(self, key: str, default: Any = None) -> Any:
        with self._lock:
            if key not in self._entries:
                self._misses += 1
                return default

            entry = self._entries[key]
            now = time.time()

            # Check expiration
            if entry.expires_at is not None and now > entry.expires_at:
                del self._entries[key]
                self._expirations += 1
                self._misses += 1
                if self.persistence_path:
                    self._persist()
                return default

            # Check cryptographic integrity
            computed_hash = _compute_value_hash(entry.value)
            if computed_hash != entry.checksum_sha256:
                raise CacheIntegrityError(
                    f"Integrity check failed for key '{key}': stored '{entry.checksum_sha256}' != computed '{computed_hash}'"
                )

            # Move to end (mark as most recently used)
            self._entries.move_to_end(key)
            entry.access_count += 1
            entry.last_accessed = now
            self._hits += 1
            return entry.value

    def set(
        self,
        key: str,
        value: Any,
        ttl_seconds: Optional[float] = None,
    ) -> None:
        with self._lock:
            now = time.time()
            ttl = ttl_seconds if ttl_seconds is not None else self.default_ttl
            expires_at = (now + ttl) if ttl is not None else None
            checksum = _compute_value_hash(value)

            if key in self._entries:
                self._entries.move_to_end(key)
            elif len(self._entries) >= self.max_items:
                # Evict LRU (first element in OrderedDict)
                self._entries.popitem(last=False)
                self._evictions += 1

            self._entries[key] = CacheEntry(
                key=key,
                value=value,
                created_at=now,
                expires_at=expires_at,
                checksum_sha256=checksum,
                access_count=0,
                last_accessed=now,
            )

            if self.persistence_path:
                self._persist()

    def purge_expired(self) -> int:
        with self._lock:
            now = time.time()
            expired_keys = [
                k for k, e in self._entries.items()
                if e.expires_at is not None and now > e.expires_at
            ]
            for k in expired_keys:
                del self._entries[k]
                self._expirations += 1

            if expired_keys and self.persistence_path:
                self._persist()

            return len(expired_keys)

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            total_lookups = self._hits + self._misses
            ratio = (self._hits / total_lookups) if total_lookups > 0 else 0.0
            return {
                "hits": self._hits,
                "misses": self._misses,
                "evictions": self._evictions,
                "expirations": self._expirations,
                "total_items": len(self._entries),
                "hit_ratio": round(ratio, 4),
            }

    def _persist(self) -> None:
        if not self.persistence_path:
            return
        data = {
            "stats": {
                "hits": self._hits,
                "misses": self._misses,
                "evictions": self._evictions,
                "expirations": self._expirations,
            },
            "entries": {k: e.to_dict() for k, e in self._entries.items()},
        }
        tmp_fd, tmp_file = tempfile.mkstemp(
            prefix="cache_tmp_",
            suffix=".json",
            dir=str(self.persistence_path.parent)
        )
        try:
            with open(tmp_fd, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            os.replace(tmp_file, str(self.persistence_path))
        except Exception:
            if os.path.exists(tmp_file):
                try:
                    os.unlink(tmp_file)
                except OSError:
                    pass
            raise

    @classmethod
    def load_from_disk(
        cls,
        path: Path | str,
        max_items: int = 100,
        default_ttl: Optional[float] = None,
    ) -> EphemeralCache:
        p = Path(path)
        cache = cls(max_items=max_items, default_ttl=default_ttl, persistence_path=p)
        if not p.exists():
            return cache

        data = json.loads(p.read_text(encoding="utf-8"))
        stats = data.get("stats", {})
        cache._hits = int(stats.get("hits", 0))
        cache._misses = int(stats.get("misses", 0))
        cache._evictions = int(stats.get("evictions", 0))
        cache._expirations = int(stats.get("expirations", 0))

        entries_data = data.get("entries", {})
        for k, v in entries_data.items():
            cache._entries[k] = CacheEntry.from_dict(v)

        return cache


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Ephemeral Cache CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    set_parser = subparsers.add_parser("set", help="Store a key-value in cache")
    set_parser.add_argument("--store", required=True, help="Path to cache store JSON")
    set_parser.add_argument("--key", required=True, help="Cache key")
    set_parser.add_argument("--value", required=True, help="JSON value string")
    set_parser.add_argument("--ttl", type=float, default=None, help="TTL in seconds")

    get_parser = subparsers.add_parser("get", help="Retrieve a key-value from cache")
    get_parser.add_argument("--store", required=True, help="Path to cache store JSON")
    get_parser.add_argument("--key", required=True, help="Cache key")

    args = parser.parse_args(argv)

    if args.command == "set":
        cache = EphemeralCache.load_from_disk(args.store)
        val = json.loads(args.value)
        cache.set(args.key, val, ttl_seconds=args.ttl)
        print(json.dumps({
            "status": "STORED",
            "key": args.key,
            "ttl": args.ttl,
        }, indent=2))
        return 0

    elif args.command == "get":
        cache = EphemeralCache.load_from_disk(args.store)
        val = cache.get(args.key)
        print(json.dumps({
            "key": args.key,
            "found": val is not None,
            "value": val,
        }, indent=2))
        return 0 if val is not None else 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
