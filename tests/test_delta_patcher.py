"""Tests for courier_core.delta_patcher - Incremental Artifact Delta Patcher."""

from __future__ import annotations

import json
from pathlib import Path
import pytest

from courier_core.delta_patcher import (
    DeltaPatcher,
    DeltaPatch,
    BaseFileMismatchError,
    TargetCorruptError,
    InvalidPatchError,
)


@pytest.fixture
def patcher() -> DeltaPatcher:
    return DeltaPatcher(chunk_size=32)


def test_generate_and_apply_delta_patch(patcher: DeltaPatcher, tmp_path: Path):
    base_data = b"HEAD" + (b"A" * 64) + b"MID" + (b"B" * 64) + b"TAIL"
    target_data = b"HEAD" + (b"A" * 64) + b"MODIFIED_MID" + (b"B" * 64) + b"TAIL_APPENDED"

    base_file = tmp_path / "base.bin"
    base_file.write_bytes(base_data)

    target_file = tmp_path / "target.bin"
    target_file.write_bytes(target_data)

    patch = patcher.create_patch(base_file, target_file)

    assert patch.base_size == len(base_data)
    assert patch.target_size == len(target_data)
    assert len(patch.operations) > 0

    # Reconstruct target
    restored_file = tmp_path / "restored.bin"
    patcher.apply_patch(base_file, patch, restored_file)

    assert restored_file.exists()
    assert restored_file.read_bytes() == target_data


def test_patch_operations_copy_and_insert(patcher: DeltaPatcher, tmp_path: Path):
    base = tmp_path / "base.bin"
    base.write_bytes(b"StaticBlock" * 5)

    target = tmp_path / "target.bin"
    target.write_bytes(b"StaticBlock" * 5 + b"BrandNewInsertedContent")

    patch = patcher.create_patch(base, target)
    op_types = [op["type"] for op in patch.operations]
    assert "COPY" in op_types
    assert "INSERT" in op_types

    # Test serialization
    serialized = patch.to_json()
    deserialized = DeltaPatch.from_json(serialized)
    assert deserialized.base_sha256 == patch.base_sha256
    assert deserialized.target_sha256 == patch.target_sha256
    assert len(deserialized.operations) == len(patch.operations)


def test_fail_closed_base_mismatch_rejection(patcher: DeltaPatcher, tmp_path: Path):
    base_correct = tmp_path / "base_correct.bin"
    base_correct.write_bytes(b"Correct Base Content")

    target = tmp_path / "target.bin"
    target.write_bytes(b"Correct Base Content with Delta")

    patch = patcher.create_patch(base_correct, target)

    # Wrong base file
    base_wrong = tmp_path / "base_wrong.bin"
    base_wrong.write_bytes(b"Wrong Base Content")

    out_file = tmp_path / "out.bin"
    with pytest.raises(BaseFileMismatchError):
        patcher.apply_patch(base_wrong, patch, out_file)

    assert not out_file.exists()


def test_fail_closed_tampered_patch_detection(patcher: DeltaPatcher, tmp_path: Path):
    base = tmp_path / "base.bin"
    base.write_bytes(b"Base Data For Patching")

    target = tmp_path / "target.bin"
    target.write_bytes(b"Base Data For Patching + Delta")

    patch = patcher.create_patch(base, target)

    # Tamper with target_sha256 in patch
    patch.target_sha256 = "0" * 64

    out_file = tmp_path / "tampered_out.bin"
    with pytest.raises(TargetCorruptError):
        patcher.apply_patch(base, patch, out_file)

    assert not out_file.exists()


def test_empty_and_identical_files(patcher: DeltaPatcher, tmp_path: Path):
    f_same1 = tmp_path / "same1.bin"
    f_same1.write_bytes(b"IdenticalContent" * 10)
    f_same2 = tmp_path / "same2.bin"
    f_same2.write_bytes(b"IdenticalContent" * 10)

    patch_same = patcher.create_patch(f_same1, f_same2)
    # Identical content: should have COPY and 0 INSERT bytes
    assert all(op["type"] == "COPY" for op in patch_same.operations)

    out_same = tmp_path / "out_same.bin"
    patcher.apply_patch(f_same1, patch_same, out_same)
    assert out_same.read_bytes() == f_same1.read_bytes()


def test_cli_diff_and_patch(tmp_path: Path, monkeypatch, capsys):
    from courier_core.delta_patcher import main

    base = tmp_path / "cli_base.bin"
    base.write_bytes(b"Courier Symphony Base Worker State")

    target = tmp_path / "cli_target.bin"
    target.write_bytes(b"Courier Symphony Base Worker State - Incremental Delta")

    patch_file = tmp_path / "delta.patch"
    out_file = tmp_path / "cli_restored.bin"

    # Diff
    monkeypatch.setattr(
        "sys.argv",
        ["delta_patcher.py", "diff", "--base", str(base), "--target", str(target), "--output", str(patch_file)],
    )
    main()
    assert patch_file.exists()

    # Info
    monkeypatch.setattr(
        "sys.argv",
        ["delta_patcher.py", "info", "--patch", str(patch_file)],
    )
    main()
    info_out = capsys.readouterr().out
    assert "target_size" in info_out

    # Patch
    monkeypatch.setattr(
        "sys.argv",
        ["delta_patcher.py", "patch", "--base", str(base), "--patch", str(patch_file), "--output", str(out_file)],
    )
    main()
    assert out_file.read_bytes() == target.read_bytes()


def test_multiple_insert_and_copy_segments(patcher: DeltaPatcher, tmp_path: Path):
    # Interleaved pattern of existing and new data
    part1 = b"PART_ONE_BLOCK_DATA_PADDING_1234"
    part2 = b"PART_TWO_BLOCK_DATA_PADDING_5678"
    base = tmp_path / "multi_base.bin"
    base.write_bytes(part1 + part2)

    # Inserted at front, middle, and end
    target_data = b"FRONT_INSERT_" + part2 + b"_MIDDLE_INSERT_" + part1 + b"_END_INSERT"
    target = tmp_path / "multi_target.bin"
    target.write_bytes(target_data)

    patch = patcher.create_patch(base, target)
    restored = tmp_path / "multi_restored.bin"
    patcher.apply_patch(base, patch, restored)
    assert restored.read_bytes() == target_data
