"""Tests for courier_core.content_dedup - Content-Addressed Storage & Deduplication Engine."""

from __future__ import annotations

import json
from pathlib import Path
import pytest

from courier_core.content_dedup import (
    ContentAddressedStore,
    ArtifactManifest,
    CASIntegrityError,
    CASSecurityError,
)


@pytest.fixture
def cas_dir(tmp_path: Path) -> Path:
    d = tmp_path / "cas_store"
    d.mkdir(parents=True, exist_ok=True)
    return d


def test_cas_store_and_retrieve_bytes(cas_dir: Path):
    cas = ContentAddressedStore(cas_dir)
    data = b"Courier Symphony Titan Windows Worker CAS Block"

    digest = cas.store_bytes(data)
    assert len(digest) == 64
    assert isinstance(digest, str)

    # Check 2-level directory tree
    expected_path = cas_dir / "objects" / digest[:2] / digest[2:4] / digest
    assert expected_path.exists()
    assert expected_path.read_bytes() == data

    # Retrieve
    retrieved = cas.retrieve_bytes(digest)
    assert retrieved == data

    # Idempotent write
    digest_again = cas.store_bytes(data)
    assert digest_again == digest


def test_cas_integrity_verification_and_tamper_detection(cas_dir: Path):
    cas = ContentAddressedStore(cas_dir)
    data = b"Integrity Protected Content"
    digest = cas.store_bytes(data)

    # Tamper with stored object file directly
    obj_file = cas_dir / "objects" / digest[:2] / digest[2:4] / digest
    obj_file.write_bytes(b"Tampered Corrupted Data!")

    # Retrieval should detect tamper and raise CASIntegrityError
    with pytest.raises(CASIntegrityError):
        cas.retrieve_bytes(digest)


def test_file_chunking_and_manifest_reconstruction(cas_dir: Path, tmp_path: Path):
    cas = ContentAddressedStore(cas_dir, chunk_size=64)

    # Create a test file with repetitive chunks to test deduplication
    chunk_a = b"A" * 64
    chunk_b = b"B" * 64
    test_content = (chunk_a + chunk_b) * 4  # 8 chunks total, 2 unique
    src_file = tmp_path / "source_payload.bin"
    src_file.write_bytes(test_content)

    manifest = cas.store_file(src_file)

    assert manifest.total_size == len(test_content)
    assert len(manifest.chunks) == 8
    # Because of deduplication, unique chunk hashes should be exactly 2
    unique_hashes = set(manifest.chunks)
    assert len(unique_hashes) == 2

    # Restore to target file
    restored_file = tmp_path / "restored_payload.bin"
    cas.restore_file(manifest, restored_file)

    assert restored_file.exists()
    assert restored_file.read_bytes() == test_content


def test_security_path_traversal_prevention(cas_dir: Path):
    cas = ContentAddressedStore(cas_dir)

    invalid_hashes = [
        "../etc/passwd",
        "../../shadow",
        "a" * 62 + "/x",
        "bad\x00hash",
        "xyz",  # not 64 hex
        "G" * 64,  # invalid hex character
    ]

    for bad in invalid_hashes:
        with pytest.raises((CASSecurityError, ValueError)):
            cas.retrieve_bytes(bad)


def test_garbage_collection_pruning(cas_dir: Path, tmp_path: Path):
    cas = ContentAddressedStore(cas_dir, chunk_size=32)

    # Store 2 files
    f1 = tmp_path / "f1.txt"
    f1.write_bytes(b"First File Payload for CAS Engine")
    m1 = cas.store_file(f1)

    f2 = tmp_path / "f2.txt"
    f2.write_bytes(b"Second Unique File to be Orphaned and Pruned")
    m2 = cas.store_file(f2)

    stats_before = cas.get_stats()
    assert stats_before["unique_chunks"] >= 2

    # Run GC keeping only m1
    pruned_count = cas.garbage_collect(active_manifests=[m1])
    assert pruned_count > 0

    # m1 chunks still present
    restored_f1 = tmp_path / "restored_f1.txt"
    cas.restore_file(m1, restored_f1)
    assert restored_f1.read_bytes() == f1.read_bytes()

    # m2 chunks were pruned -> restore of m2 fails
    restored_f2 = tmp_path / "restored_f2.txt"
    with pytest.raises(FileNotFoundError):
        cas.restore_file(m2, restored_f2)


def test_storage_stats_and_compression_ratio(cas_dir: Path, tmp_path: Path):
    cas = ContentAddressedStore(cas_dir, chunk_size=64)

    # 10 identical files of 640 bytes (10 chunks each)
    content = (b"X" * 64) * 10
    manifests = []
    for i in range(5):
        f = tmp_path / f"dup_{i}.bin"
        f.write_bytes(content)
        manifests.append(cas.store_file(f))

    stats = cas.get_stats(manifests=manifests)
    assert stats["total_raw_bytes"] == 640 * 5  # 3200 bytes
    assert stats["stored_bytes"] == 64  # only 1 unique chunk stored!
    assert stats["unique_chunks"] == 1
    assert stats["dedup_ratio"] == 50.0  # 3200 / 64
    assert stats["savings_percent"] > 95.0


def test_cas_cli(cas_dir: Path, tmp_path: Path, monkeypatch, capsys):
    from courier_core.content_dedup import main

    src = tmp_path / "cli_src.txt"
    raw = b"CLI deduplication test payload\n"
    src.write_bytes(raw)

    # Store via CLI
    monkeypatch.setattr(
        "sys.argv",
        ["content_dedup.py", "--root", str(cas_dir), "store", str(src), "--chunk-size", "16"],
    )
    main()
    captured = capsys.readouterr()
    manifest_dict = json.loads(captured.out)
    assert manifest_dict["total_size"] == len(raw)

    # Save manifest
    m_path = tmp_path / "manifest.json"
    m_path.write_text(json.dumps(manifest_dict))

    # Restore via CLI
    dest = tmp_path / "cli_restored.txt"
    monkeypatch.setattr(
        "sys.argv",
        ["content_dedup.py", "--root", str(cas_dir), "restore", str(m_path), str(dest)],
    )
    main()
    capsys.readouterr()
    assert dest.read_bytes() == raw

    # Stats via CLI
    monkeypatch.setattr(
        "sys.argv",
        ["content_dedup.py", "--root", str(cas_dir), "stats"],
    )
    main()
    stats_out = capsys.readouterr()
    stats_json = json.loads(stats_out.out)
    assert stats_json["unique_chunks"] >= 2
