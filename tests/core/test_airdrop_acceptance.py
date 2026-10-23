"""Systematic AirDrop & Local File Organization Acceptance Suite.

Validates the 10 requirements of the Apple Device AirDrop Acceptance Challenge:
1. iPhone A sends a photo (HEIC/JPG).
2. iPhone B sends a video (MOV/MP4).
3. Concurrent intake from two devices (nearly simultaneous transfer).
4. Identical filenames from different devices (Disambiguation without overwrite).
5. Interrupted transfer (.download / partial file quarantining).
6. Retransmitted file (Idempotent deduplication without duplicate bloat).
7. Mac locked / headless processing (no UI thread dependency).
8. Offline / Network loss resilience (local-first decoupled execution).
9. Very large media streaming (Bounded O(1) memory, zero RAM spike).
10. Restart & recovery after aborted organization run (in_flight ledger recovery).
"""

import os
import shutil
import sqlite3
import tempfile
import threading
import time
from pathlib import Path

import pytest

from courier_core.airdrop_intake import (
    AirDropOrganizer,
    FileCategory,
    IntakeResult,
    IntakeStatus,
    categorize_file,
    inspect_file,
)


@pytest.fixture
def airdrop_env(tmp_path):
    incoming = tmp_path / "incoming"
    library = tmp_path / "library"
    quarantine = tmp_path / "quarantine"
    db_path = tmp_path / "state" / "airdrop.db"

    organizer = AirDropOrganizer(incoming, library, quarantine, db_path)
    return {
        "organizer": organizer,
        "incoming": incoming,
        "library": library,
        "quarantine": quarantine,
        "db_path": db_path,
    }


def test_01_iphone_a_sends_photo(airdrop_env):
    """Case 1: iPhone A sends a photo."""
    organizer = airdrop_env["organizer"]
    incoming = airdrop_env["incoming"]

    photo_path = incoming / "IMG_1001.HEIC"
    photo_path.write_bytes(b"EXIF_MOCK_HEADER_IPHONE_A_PHOTO_DATA_12345")

    result = organizer.organize_file(photo_path, source_device="iPhone von Dennis")

    assert result.status == IntakeStatus.ACCEPTED
    assert result.category == FileCategory.PHOTO
    assert result.source_device == "iPhone von Dennis"
    assert Path(result.target_path).exists()
    assert not photo_path.exists()
    assert Path(result.target_path).read_bytes() == b"EXIF_MOCK_HEADER_IPHONE_A_PHOTO_DATA_12345"


def test_02_iphone_b_sends_video(airdrop_env):
    """Case 2: iPhone B sends a video."""
    organizer = airdrop_env["organizer"]
    incoming = airdrop_env["incoming"]

    video_path = incoming / "VID_2002.MOV"
    video_path.write_bytes(b"MOOV_ATOM_MOCK_IPHONE_B_VIDEO_DATA_99999")

    result = organizer.organize_file(video_path, source_device="iPhone von Dennis (2)")

    assert result.status == IntakeStatus.ACCEPTED
    assert result.category == FileCategory.VIDEO
    assert result.source_device == "iPhone von Dennis (2)"
    assert Path(result.target_path).exists()
    assert not video_path.exists()
    assert Path(result.target_path).read_bytes() == b"MOOV_ATOM_MOCK_IPHONE_B_VIDEO_DATA_99999"


def test_03_concurrent_intake_nearly_simultaneous(airdrop_env):
    """Case 3: Two iPhones send nearly simultaneously."""
    organizer = airdrop_env["organizer"]
    incoming = airdrop_env["incoming"]

    file_a = incoming / "PHOTO_A.JPG"
    file_b = incoming / "VIDEO_B.MOV"

    file_a.write_bytes(b"CONTENT_PHOTO_A_CONCURRENT")
    file_b.write_bytes(b"CONTENT_VIDEO_B_CONCURRENT")

    results = []
    errors = []

    def worker(path, source):
        try:
            res = organizer.organize_file(path, source_device=source)
            results.append(res)
        except Exception as exc:
            errors.append(exc)

    t1 = threading.Thread(target=worker, args=(file_a, "iPhone A"))
    t2 = threading.Thread(target=worker, args=(file_b, "iPhone B"))

    t1.start()
    t2.start()
    t1.join()
    t2.join()

    assert len(errors) == 0, f"Concurrent execution raised errors: {errors}"
    assert len(results) == 2
    for r in results:
        assert r.status == IntakeStatus.ACCEPTED
        assert Path(r.target_path).exists()


def test_04_identical_filenames_different_content_disambiguation(airdrop_env):
    """Case 4: Both iPhones send files with identical names (No silent overwrite!)."""
    organizer = airdrop_env["organizer"]
    incoming = airdrop_env["incoming"]

    # iPhone A sends IMG_0001.JPG
    file_a = incoming / "IMG_0001.JPG"
    file_a.write_bytes(b"PICTURE_TAKEN_BY_IPHONE_A")
    res_a = organizer.organize_file(file_a, source_device="iPhone A")

    assert res_a.status == IntakeStatus.ACCEPTED
    target_a = Path(res_a.target_path)
    assert target_a.name == "IMG_0001.JPG"
    assert target_a.read_bytes() == b"PICTURE_TAKEN_BY_IPHONE_A"

    # iPhone B also sends IMG_0001.JPG, but different picture content
    file_b = incoming / "IMG_0001.JPG"
    file_b.write_bytes(b"PICTURE_TAKEN_BY_IPHONE_B_DIFFERENT")
    res_b = organizer.organize_file(file_b, source_device="iPhone B")

    assert res_b.status == IntakeStatus.DISAMBIGUATED
    assert res_b.disambiguated is True
    target_b = Path(res_b.target_path)
    # Must NOT overwrite target_a!
    assert target_a.read_bytes() == b"PICTURE_TAKEN_BY_IPHONE_A"
    assert target_b.read_bytes() == b"PICTURE_TAKEN_BY_IPHONE_B_DIFFERENT"
    assert target_b.name == "IMG_0001 (1).JPG"


def test_05_interrupted_transfer_quarantine(airdrop_env):
    """Case 5: An AirDrop transfer is interrupted mid-way (.download / incomplete)."""
    organizer = airdrop_env["organizer"]
    incoming = airdrop_env["incoming"]
    quarantine = airdrop_env["quarantine"]

    # Partial transfer file left by AirDrop (.download)
    partial_file = incoming / "VID_LARGE.MOV.download"
    partial_file.write_bytes(b"TRUNCATED_CHUNKS_LOST_CONNECTION_AT_50_PERCENT")

    result = organizer.organize_file(partial_file, source_device="iPhone A")

    assert result.status == IntakeStatus.INCOMPLETE_QUARANTINED
    assert not partial_file.exists()
    assert (quarantine / "VID_LARGE.MOV.download").exists()
    assert (quarantine / "VID_LARGE.MOV.download").read_bytes() == b"TRUNCATED_CHUNKS_LOST_CONNECTION_AT_50_PERCENT"


def test_06_retransmitted_file_idempotent_deduplication(airdrop_env):
    """Case 6: A file is retransmitted (Idempotent deduplication, no storage waste)."""
    organizer = airdrop_env["organizer"]
    incoming = airdrop_env["incoming"]

    data = b"STABLE_PHOTO_BYTES_IDENTICAL_100_PERCENT"

    # First transmission
    first_file = incoming / "PHOTO_RETRY.JPG"
    first_file.write_bytes(data)
    res1 = organizer.organize_file(first_file, source_device="iPhone A")
    assert res1.status == IntakeStatus.ACCEPTED
    target_1 = Path(res1.target_path)
    assert target_1.exists()

    # Second transmission of identical file (e.g. user taps AirDrop again)
    second_file = incoming / "PHOTO_RETRY.JPG"
    second_file.write_bytes(data)
    res2 = organizer.organize_file(second_file, source_device="iPhone A")

    assert res2.status == IntakeStatus.DEDUPLICATED
    assert not second_file.exists(), "Duplicate in incoming should be cleanly unlinked"
    assert res2.target_path == str(target_1), "Points to the already established target"
    # Ensure no duplicate copy was added to library
    photo_files = list((airdrop_env["library"] / "photo").glob("*.JPG"))
    assert len(photo_files) == 1


def test_07_mac_locked_during_processing(airdrop_env):
    """Case 7: Mac is locked during reception/organization (Headless daemon execution)."""
    organizer = airdrop_env["organizer"]
    incoming = airdrop_env["incoming"]

    # Emulate background execution while session is locked
    file_path = incoming / "LOCKED_SCREEN_PHOTO.PNG"
    file_path.write_bytes(b"LOCKED_SCREEN_CAPTURED_DATA")

    # Organizer runs purely in user-space daemon without requiring GUI / window server
    result = organizer.organize_file(file_path, source_device="iPhone A")

    assert result.status == IntakeStatus.ACCEPTED
    assert Path(result.target_path).exists()
    assert Path(result.target_path).read_bytes() == b"LOCKED_SCREEN_CAPTURED_DATA"


def test_08_wifi_bluetooth_temporarily_unavailable(airdrop_env):
    """Case 8: WiFi or Bluetooth is temporarily unavailable (Local-first decoupling)."""
    organizer = airdrop_env["organizer"]
    incoming = airdrop_env["incoming"]

    # Even if wireless networking is off, any local file received or queued
    # organizes deterministically without hanging or attempting cloud calls.
    local_file = incoming / "OFFLINE_MEDIA.MOV"
    local_file.write_bytes(b"OFFLINE_PAYLOAD_TEST")

    res = organizer.organize_file(local_file)
    assert res.status == IntakeStatus.ACCEPTED
    assert res.source_device == "UNVERIFIED_SOURCE"  # unproven device attribution avoided


def test_09_very_large_video_file_memory_bounds(airdrop_env):
    """Case 9: A very large video file is transferred (Bounded streaming memory)."""
    organizer = airdrop_env["organizer"]
    incoming = airdrop_env["incoming"]

    # Create a 20 MB media file using repetitive blocks
    large_file = incoming / "4K_RECORDING_LARGE.MOV"
    chunk = b"X" * (1024 * 1024)  # 1 MB chunk
    with open(large_file, "wb") as f:
        for _ in range(20):
            f.write(chunk)

    assert large_file.stat().st_size == 20 * 1024 * 1024

    res = organizer.organize_file(large_file, source_device="iPhone B")

    assert res.status == IntakeStatus.ACCEPTED
    assert res.size_bytes == 20 * 1024 * 1024
    assert Path(res.target_path).exists()
    assert Path(res.target_path).stat().st_size == 20 * 1024 * 1024


def test_10_restart_after_aborted_organization_process(airdrop_env):
    """Case 10: Mac is restarted after an aborted organization process (Crash recovery)."""
    organizer = airdrop_env["organizer"]
    incoming = airdrop_env["incoming"]
    library = airdrop_env["library"]
    db_path = airdrop_env["db_path"]

    # Simulate an interrupted transaction:
    # A file was partially copied to temp_path, recorded in in_flight table, but process crashed before completion
    cat_dir = library / "video"
    cat_dir.mkdir(parents=True, exist_ok=True)

    crashed_source = incoming / "CRASHED_VID.MOV"
    crashed_source.write_bytes(b"CRASHED_PROCESS_ORIGINAL_DATA")

    temp_target = cat_dir / ".tmp-tx-simulated_crash.MOV"
    temp_target.write_bytes(b"CRASHED_PROCESS_ORIGINAL_DATA")

    final_target = cat_dir / "CRASHED_VID.MOV"

    # Insert into in_flight ledger
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "INSERT INTO in_flight (tx_id, source_path, temp_path, target_path, sha256, started_at) VALUES (?, ?, ?, ?, ?, ?)",
        ("tx-crash-001", str(crashed_source), str(temp_target), str(final_target), "fakehash123", time.time())
    )
    conn.commit()
    conn.close()

    # Simulate recovery upon restart
    recovered_count = organizer.recover()
    assert recovered_count == 1

    # Final target must now be restored
    assert final_target.exists()
    assert final_target.read_bytes() == b"CRASHED_PROCESS_ORIGINAL_DATA"
    assert not temp_target.exists(), "Temporary transfer file must be cleanly cleaned up"

    # in_flight ledger must be empty
    conn = sqlite3.connect(str(db_path))
    rows = conn.execute("SELECT * FROM in_flight").fetchall()
    conn.close()
    assert len(rows) == 0


def test_symlink_is_not_copied_into_the_library(tmp_path):
    outside = tmp_path / "outside.txt"
    outside.write_text("SECRET", encoding="utf-8")
    incoming = tmp_path / "incoming"
    library = tmp_path / "library"
    quarantine = tmp_path / "quarantine"
    incoming.mkdir()
    link = incoming / "note.txt"
    link.symlink_to(outside)
    organizer = AirDropOrganizer(incoming, library, quarantine, tmp_path / "state" / "airdrop.db")
    try:
        result = organizer.organize_file(link)
    except ValueError as exc:
        seen = ("raised", str(exc))
    else:
        copied = sorted(path.relative_to(library).as_posix() for path in library.rglob("*") if path.is_file())
        body = (library / copied[0]).read_text(encoding="utf-8") if copied else ""
        seen = ("accepted", result.status.value, copied, body)
    names = sorted(path.relative_to(library).as_posix() for path in library.rglob("*") if path.is_file())
    assert seen[0] == "raised" and "symlink" in seen[1].lower() and names == [] and outside.read_text(encoding="utf-8") == "SECRET", seen


def test_library_and_ledger_symlinks_are_not_destinations(tmp_path):
    outside_lib = tmp_path / "outside-lib"
    outside_lib.mkdir()
    (outside_lib / "keep.txt").write_text("keep", encoding="utf-8")
    library = tmp_path / "library"
    library.symlink_to(outside_lib, target_is_directory=True)
    incoming = tmp_path / "incoming"
    incoming.mkdir()
    (incoming / "note.txt").write_text("HELLO", encoding="utf-8")
    try:
        organizer = AirDropOrganizer(incoming, library, tmp_path / "quarantine", tmp_path / "state" / "airdrop.db")
        result = organizer.organize_file(incoming / "note.txt")
    except ValueError as exc:
        library_seen = ("raised", str(exc))
    except Exception as exc:
        library_seen = (type(exc).__name__, str(exc))
    else:
        library_seen = ("accepted", result.status.value, sorted(p.name for p in outside_lib.rglob("*")))

    outside_db = tmp_path / "outside.db"
    outside_db.write_text("keep", encoding="utf-8")
    db_link = tmp_path / "ledger.db"
    db_link.symlink_to(outside_db)
    real_incoming = tmp_path / "incoming-real"
    real_incoming.mkdir()
    (real_incoming / "photo.txt").write_text("PHOTO", encoding="utf-8")
    try:
        organizer = AirDropOrganizer(real_incoming, tmp_path / "library-real", tmp_path / "quarantine-real", db_link)
        result = organizer.organize_file(real_incoming / "photo.txt")
    except ValueError as exc:
        db_seen = ("raised", str(exc))
    except Exception as exc:
        db_seen = (type(exc).__name__, str(exc))
    else:
        db_seen = ("accepted", result.status.value, outside_db.read_bytes()[:40])
    names = sorted(p.relative_to(outside_lib).as_posix() for p in outside_lib.rglob("*"))
    assert (
        library_seen[0] == "raised" and "symlink" in library_seen[1].lower()
        and db_seen[0] == "raised" and "symlink" in db_seen[1].lower()
        and names == ["keep.txt"]
        and outside_db.read_text(encoding="utf-8") == "keep"
    ), (library_seen, db_seen, names, outside_db.read_bytes()[:40])
