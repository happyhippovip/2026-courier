"""Tests for courier_core.immutable_cas_cache - Content-Addressable Immutable Cache Store with TTL & LRU Pruning."""

from __future__ import annotations

import json
import pytest

from courier_core.immutable_cas_cache import (
    ImmutableCasCache,
    DigestMismatchError,
    ImmutableCollisionError,
    main,
)


def test_put_and_get_content_addressable(tmp_path):
    cache_dir = tmp_path / "cas_cache"
    cache = ImmutableCasCache(cache_dir=cache_dir, max_bytes=1024 * 1024)

    payload = b"Hello Courier Symphony Artifact"
    digest = cache.put(payload)
    assert len(digest) == 64

    # Fetch back
    data = cache.get(digest)
    assert data == payload

    # Re-putting identical content is idempotent and returns same digest
    assert cache.put(payload) == digest


def test_immutability_and_tamper_detection(tmp_path):
    cache_dir = tmp_path / "cas_cache"
    cache = ImmutableCasCache(cache_dir=cache_dir, max_bytes=1024 * 1024)

    payload = b"Original Immutable Bytes"
    digest = cache.put(payload)

    # Tamper with the raw file on disk
    file_path = cache.get_path(digest)
    file_path.write_bytes(b"Tampered Corrupt Bytes")

    # Accessing should detect digest mismatch and raise
    with pytest.raises(DigestMismatchError, match="Cache entry corrupted"):
        cache.get(digest)


def test_ttl_expiration_and_pruning(tmp_path):
    cache_dir = tmp_path / "cas_cache"
    cache = ImmutableCasCache(cache_dir=cache_dir, max_bytes=1024 * 1024, default_ttl_seconds=10.0)

    t0 = 1000.0
    payload = b"Ephemeral Test Artifact"
    digest = cache.put(payload, ttl_seconds=5.0, now=t0)

    # At t0 + 2s -> valid
    assert cache.get(digest, now=t0 + 2.0) == payload

    # At t0 + 6s -> expired (returns None)
    assert cache.get(digest, now=t0 + 6.0) is None

    # Prune expired
    pruned = cache.prune_expired(now=t0 + 6.0)
    assert digest in pruned
    assert not cache.get_path(digest).exists()


def test_lru_capacity_eviction(tmp_path):
    cache_dir = tmp_path / "cas_cache"
    # Small capacity: 150 bytes max
    cache = ImmutableCasCache(cache_dir=cache_dir, max_bytes=150)

    chunk_a = b"A" * 60
    chunk_b = b"B" * 60
    chunk_c = b"C" * 60

    digest_a = cache.put(chunk_a, now=100.0)
    digest_b = cache.put(chunk_b, now=101.0)

    # Touch A to make B the least recently used
    assert cache.get(digest_a, now=102.0) == chunk_a

    # Putting C exceeds 150 bytes (60 + 60 + 60 = 180 > 150) -> B should be evicted
    digest_c = cache.put(chunk_c, now=103.0)

    assert cache.get(digest_a, now=104.0) == chunk_a
    assert cache.get(digest_c, now=104.0) == chunk_c
    assert cache.get(digest_b, now=104.0) is None


def test_metadata_inspection_and_access_counter(tmp_path):
    cache_dir = tmp_path / "cas_cache"
    cache = ImmutableCasCache(cache_dir=cache_dir, max_bytes=1024)

    digest = cache.put(b"Sample payload", tags={"type": "build_artifact"})
    entry = cache.inspect(digest)
    assert entry is not None
    assert entry["size_bytes"] == len(b"Sample payload")
    assert entry["tags"] == {"type": "build_artifact"}
    assert entry["access_count"] == 0

    # Get increments counter
    cache.get(digest)
    entry_updated = cache.inspect(digest)
    assert entry_updated["access_count"] == 1


def test_cli_immutable_cas_cache(tmp_path, monkeypatch, capsys):
    cache_dir = tmp_path / "cli_cache"

    # Put
    monkeypatch.setattr(
        "sys.argv",
        [
            "immutable_cas_cache.py",
            "put",
            "--dir",
            str(cache_dir),
            "--data",
            "CLI CAS Payload Content",
        ],
    )
    main()
    out = capsys.readouterr().out
    digest = out.strip().split()[-1]
    assert len(digest) == 64

    # Get
    monkeypatch.setattr(
        "sys.argv",
        [
            "immutable_cas_cache.py",
            "get",
            "--dir",
            str(cache_dir),
            "--digest",
            digest,
        ],
    )
    main()
    out = capsys.readouterr().out
    assert "CLI CAS Payload Content" in out
