import json
import time
import pytest
from pathlib import Path
from courier_core.ephemeral_cache import (
    EphemeralCache,
    CacheEntry,
    CacheIntegrityError,
)


def test_basic_set_and_get():
    cache = EphemeralCache(max_items=10)

    cache.set("task-1", {"result": "success", "score": 98})
    val = cache.get("task-1")

    assert val is not None
    assert val["result"] == "success"
    assert val["score"] == 98

    # Miss
    assert cache.get("non-existent") is None


def test_ttl_expiration():
    cache = EphemeralCache(max_items=10)

    # Set with TTL 0.1s
    cache.set("short-lived", "temp-val", ttl_seconds=0.1)

    assert cache.get("short-lived") == "temp-val"

    # Wait for expiration
    time.sleep(0.15)
    assert cache.get("short-lived") is None

    stats = cache.get_stats()
    assert stats["expirations"] == 1


def test_lru_eviction():
    cache = EphemeralCache(max_items=3)

    cache.set("k1", 1)
    cache.set("k2", 2)
    cache.set("k3", 3)

    # Access k1 to make k2 the least recently used
    _ = cache.get("k1")

    # Insert k4, which should evict k2
    cache.set("k4", 4)

    assert cache.get("k2") is None
    assert cache.get("k1") == 1
    assert cache.get("k3") == 3
    assert cache.get("k4") == 4

    stats = cache.get_stats()
    assert stats["evictions"] == 1


def test_checksum_integrity_and_tampering():
    cache = EphemeralCache(max_items=10)
    cache.set("secure-item", {"status": "AUTHENTIC"})

    # Intentionally corrupt internal cache payload
    entry = cache._entries["secure-item"]
    entry.value = {"status": "TAMPERED"}

    with pytest.raises(CacheIntegrityError):
        cache.get("secure-item")


def test_disk_persistence_and_restore(tmp_path):
    cache_file = tmp_path / "cache_store.json"
    cache = EphemeralCache(max_items=10, persistence_path=cache_file)

    cache.set("item-a", {"data": 100})
    cache.set("item-b", {"data": 200})

    assert cache_file.exists()

    # Load into a new cache instance
    restored = EphemeralCache.load_from_disk(cache_file, max_items=10)
    assert restored.get("item-a") == {"data": 100}
    assert restored.get("item-b") == {"data": 200}


def test_cache_statistics():
    cache = EphemeralCache(max_items=5)

    cache.set("a", 1)
    cache.set("b", 2)

    cache.get("a")  # hit 1
    cache.get("a")  # hit 2
    cache.get("c")  # miss 1

    stats = cache.get_stats()
    assert stats["hits"] == 2
    assert stats["misses"] == 1
    assert abs(stats["hit_ratio"] - 0.6667) < 0.01


def test_cli_invocation(tmp_path):
    import subprocess
    import sys

    store_file = tmp_path / "cli_cache.json"

    # Set via CLI
    cmd_set = [
        sys.executable,
        "-m",
        "courier_core.ephemeral_cache",
        "set",
        "--store",
        str(store_file),
        "--key",
        "my-key",
        "--value",
        json.dumps({"flag": True}),
        "--ttl",
        "10.0",
    ]
    proc_set = subprocess.run(cmd_set, capture_output=True, text=True, check=True)
    out_set = json.loads(proc_set.stdout)
    assert out_set["status"] == "STORED"

    # Get via CLI
    cmd_get = [
        sys.executable,
        "-m",
        "courier_core.ephemeral_cache",
        "get",
        "--store",
        str(store_file),
        "--key",
        "my-key",
    ]
    proc_get = subprocess.run(cmd_get, capture_output=True, text=True, check=True)
    out_get = json.loads(proc_get.stdout)
    assert out_get["found"] is True
    assert out_get["value"] == {"flag": True}
