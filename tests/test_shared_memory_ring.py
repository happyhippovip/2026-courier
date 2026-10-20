"""Tests for courier_core.shared_memory_ring - Shared Memory Ring Buffer for Worker IPC."""

from __future__ import annotations

import secrets
import pytest

from courier_core.shared_memory_ring import (
    SharedMemoryRingBuffer,
    BufferFullError,
    BufferEmptyError,
    CorruptRingBufferError,
    MessageTooLargeError,
)


@pytest.fixture
def ring_name() -> str:
    return f"courier_ring_{secrets.token_hex(6)}"


def test_ring_buffer_create_and_connect(ring_name: str):
    # Creator
    ring1 = SharedMemoryRingBuffer.create(name=ring_name, capacity=512)
    try:
        assert ring1.capacity == 512
        assert ring1.available_write_bytes > 0
        assert ring1.available_read_bytes == 0

        # Reader connects to same segment
        ring2 = SharedMemoryRingBuffer.connect(name=ring_name)
        try:
            assert ring2.capacity == 512
            assert ring2.name == ring_name
        finally:
            ring2.close()
    finally:
        ring1.destroy()


def test_ring_buffer_write_and_read(ring_name: str):
    ring = SharedMemoryRingBuffer.create(name=ring_name, capacity=512)
    try:
        msg1 = b"Payload A for Worker Symphony"
        msg2 = b"Payload B for Worker Symphony"

        seq1 = ring.write(msg1)
        seq2 = ring.write(msg2)
        assert seq2 > seq1

        read1 = ring.read()
        assert read1 == msg1

        read2 = ring.read()
        assert read2 == msg2

        # Now empty
        assert ring.read() is None
    finally:
        ring.destroy()


def test_circular_wrap_around(ring_name: str):
    # Small buffer to force wrap-around
    ring = SharedMemoryRingBuffer.create(name=ring_name, capacity=128)
    try:
        chunk = b"X" * 30
        for i in range(10):
            ring.write(chunk)
            res = ring.read()
            assert res == chunk
    finally:
        ring.destroy()


def test_buffer_full_and_empty_guards(ring_name: str):
    ring = SharedMemoryRingBuffer.create(name=ring_name, capacity=128)
    try:
        # Fill buffer
        large_chunk = b"D" * 50
        ring.write(large_chunk)
        ring.write(large_chunk)

        # Buffer is full
        with pytest.raises(BufferFullError):
            ring.write(large_chunk)

        # Empty buffer
        assert ring.read() == large_chunk
        assert ring.read() == large_chunk

        # Buffer is empty -> block=False raises or returns None
        assert ring.read() is None
        with pytest.raises(BufferEmptyError):
            ring.read_or_raise()
    finally:
        ring.destroy()


def test_corrupt_magic_detection(ring_name: str):
    ring = SharedMemoryRingBuffer.create(name=ring_name, capacity=256)
    try:
        # Corrupt magic in header
        ring.shm.buf[0:4] = b"BADM"
        with pytest.raises(CorruptRingBufferError):
            SharedMemoryRingBuffer.connect(name=ring_name)
    finally:
        ring.destroy()


def test_frame_size_limit_rejection(ring_name: str):
    ring = SharedMemoryRingBuffer.create(name=ring_name, capacity=64)
    try:
        oversized = b"Z" * 100
        with pytest.raises(MessageTooLargeError):
            ring.write(oversized)
    finally:
        ring.destroy()


def test_cli_shared_memory_ring(ring_name: str, monkeypatch, capsys):
    from courier_core.shared_memory_ring import main

    # Create
    monkeypatch.setattr(
        "sys.argv",
        ["shared_memory_ring.py", "create", "--name", ring_name, "--capacity", "256"],
    )
    main()

    try:
        # Push
        monkeypatch.setattr(
            "sys.argv",
            ["shared_memory_ring.py", "push", "--name", ring_name, "--data", "IPC Message 123"],
        )
        main()

        # Pop
        monkeypatch.setattr(
            "sys.argv",
            ["shared_memory_ring.py", "pop", "--name", ring_name],
        )
        main()
        out = capsys.readouterr().out
        assert "IPC Message 123" in out
    finally:
        # Destroy
        monkeypatch.setattr(
            "sys.argv",
            ["shared_memory_ring.py", "destroy", "--name", ring_name],
        )
        main()
