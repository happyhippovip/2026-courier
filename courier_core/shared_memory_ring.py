"""Zero-Copy Shared Memory Ring Buffer for High-Throughput Worker IPC.

Uses native multiprocessing.shared_memory for lock-free circular framing between
worker processes on Windows and POSIX systems.
"""

from __future__ import annotations

import argparse
from multiprocessing import shared_memory
import struct
import sys
from typing import Any

_MAGIC = b"CSRB"
_VERSION = 1
_HEADER_FORMAT = ">4sHIIIQ"
_HEADER_RAW_SIZE = struct.calcsize(_HEADER_FORMAT)
_HEADER_SIZE = 32  # Aligned to 32 bytes


class RingBufferError(Exception):
    """Base exception for shared memory ring buffer."""


class BufferFullError(RingBufferError):
    """Raised when writing to ring buffer exceeds available write capacity."""


class BufferEmptyError(RingBufferError):
    """Raised when reading from an empty ring buffer."""


class CorruptRingBufferError(RingBufferError):
    """Raised when shared memory segment magic or header is invalid."""


class MessageTooLargeError(RingBufferError):
    """Raised when a message frame exceeds maximum buffer capacity."""


class SharedMemoryRingBuffer:
    """Circular ring buffer allocated in shared memory with framed read/write operations."""

    def __init__(self, shm: shared_memory.SharedMemory, is_creator: bool = False) -> None:
        self.shm = shm
        self.is_creator = is_creator
        self.name = shm.name
        self.buf = shm.buf

        if not is_creator:
            self._validate_header()

    @classmethod
    def create(cls, name: str, capacity: int = 65536) -> SharedMemoryRingBuffer:
        """Create a new shared memory ring buffer segment."""
        total_size = _HEADER_SIZE + capacity
        shm = shared_memory.SharedMemory(name=name, create=True, size=total_size)
        instance = cls(shm, is_creator=True)
        instance._init_header(capacity)
        return instance

    @classmethod
    def connect(cls, name: str) -> SharedMemoryRingBuffer:
        """Connect to an existing shared memory ring buffer segment."""
        shm = shared_memory.SharedMemory(name=name, create=False)
        return cls(shm, is_creator=False)

    def _init_header(self, capacity: int) -> None:
        header_bytes = struct.pack(
            _HEADER_FORMAT,
            _MAGIC,
            _VERSION,
            capacity,
            0,  # head
            0,  # tail
            0,  # sequence
        )
        self.buf[0:_HEADER_RAW_SIZE] = header_bytes
        # Zero out the rest of the header padding
        self.buf[_HEADER_RAW_SIZE:_HEADER_SIZE] = b"\x00" * (_HEADER_SIZE - _HEADER_RAW_SIZE)

    def _validate_header(self) -> None:
        if len(self.buf) < _HEADER_SIZE:
            raise CorruptRingBufferError("Shared memory segment too small for ring header")
        magic, version, capacity, head, tail, seq = struct.unpack_from(_HEADER_FORMAT, self.buf, 0)
        if magic != _MAGIC:
            raise CorruptRingBufferError(f"Invalid magic: {magic!r} != {_MAGIC!r}")
        if version != _VERSION:
            raise CorruptRingBufferError(f"Unsupported version: {version}")

    def _read_header(self) -> tuple[int, int, int, int]:
        _, _, capacity, head, tail, seq = struct.unpack_from(_HEADER_FORMAT, self.buf, 0)
        return capacity, head, tail, seq

    def _update_head(self, head: int, seq: int) -> None:
        struct.pack_into(">I", self.buf, 10, head)
        struct.pack_into(">Q", self.buf, 18, seq)

    def _update_tail(self, tail: int) -> None:
        struct.pack_into(">I", self.buf, 14, tail)

    @property
    def capacity(self) -> int:
        capacity, _, _, _ = self._read_header()
        return capacity

    @property
    def available_read_bytes(self) -> int:
        capacity, head, tail, _ = self._read_header()
        if head >= tail:
            return head - tail
        return capacity - (tail - head)

    @property
    def available_write_bytes(self) -> int:
        capacity, _, _, _ = self._read_header()
        used = self.available_read_bytes
        return max(0, (capacity - 1) - used)

    def write(self, data: bytes) -> int:
        """Frame and write payload into circular buffer. Returns monotonic sequence ID."""
        if not isinstance(data, (bytes, bytearray)):
            raise TypeError("Data must be bytes or bytearray")

        frame_len = len(data)
        total_frame_size = 4 + frame_len

        capacity, head, tail, seq = self._read_header()

        if total_frame_size > capacity - 1:
            raise MessageTooLargeError(
                f"Message size {total_frame_size} exceeds maximum capacity {capacity - 1}"
            )

        if total_frame_size > self.available_write_bytes:
            raise BufferFullError(
                f"Buffer full: needed {total_frame_size} bytes, available {self.available_write_bytes}"
            )

        frame_bytes = struct.pack(">I", frame_len) + data
        data_base = _HEADER_SIZE

        # Write circularly
        if head + total_frame_size <= capacity:
            self.buf[data_base + head : data_base + head + total_frame_size] = frame_bytes
        else:
            part1_len = capacity - head
            part2_len = total_frame_size - part1_len
            self.buf[data_base + head : data_base + head + part1_len] = frame_bytes[:part1_len]
            self.buf[data_base : data_base + part2_len] = frame_bytes[part1_len:]

        new_head = (head + total_frame_size) % capacity
        new_seq = seq + 1
        self._update_head(new_head, new_seq)
        return new_seq

    def _read_bytes_circular(self, offset: int, length: int, capacity: int) -> bytes:
        data_base = _HEADER_SIZE
        if offset + length <= capacity:
            return bytes(self.buf[data_base + offset : data_base + offset + length])
        part1_len = capacity - offset
        part2_len = length - part1_len
        p1 = bytes(self.buf[data_base + offset : data_base + offset + part1_len])
        p2 = bytes(self.buf[data_base : data_base + part2_len])
        return p1 + p2

    def read(self) -> bytes | None:
        """Read next framed message from circular buffer. Returns None if empty."""
        capacity, head, tail, _ = self._read_header()
        if head == tail:
            return None

        # Read 4-byte length prefix
        len_bytes = self._read_bytes_circular(tail, 4, capacity)
        (msg_len,) = struct.unpack(">I", len_bytes)

        # Read payload
        msg_offset = (tail + 4) % capacity
        payload = self._read_bytes_circular(msg_offset, msg_len, capacity)

        # Advance tail
        new_tail = (tail + 4 + msg_len) % capacity
        self._update_tail(new_tail)
        return payload

    def read_or_raise(self) -> bytes:
        """Read next framed message, raising BufferEmptyError if empty."""
        msg = self.read()
        if msg is None:
            raise BufferEmptyError("Ring buffer is empty")
        return msg

    def close(self) -> None:
        """Detach from shared memory segment."""
        try:
            self.shm.close()
        except Exception:
            pass

    def destroy(self) -> None:
        """Unlink shared memory segment and close handle."""
        try:
            self.shm.unlink()
        except Exception:
            pass
        self.close()


_CLI_ACTIVE_RINGS: dict[str, SharedMemoryRingBuffer] = {}


def main() -> None:
    parser = argparse.ArgumentParser(description="Zero-Copy Shared Memory Ring Buffer")
    subparsers = parser.add_subparsers(dest="action", required=True)

    # create
    cr_p = subparsers.add_parser("create", help="Create shared memory ring buffer")
    cr_p.add_argument("--name", required=True, help="Ring buffer name")
    cr_p.add_argument("--capacity", type=int, default=65536, help="Capacity in bytes")

    # push
    push_p = subparsers.add_parser("push", help="Push data into ring buffer")
    push_p.add_argument("--name", required=True, help="Ring buffer name")
    push_p.add_argument("--data", required=True, help="Data string to push")

    # pop
    pop_p = subparsers.add_parser("pop", help="Pop data from ring buffer")
    pop_p.add_argument("--name", required=True, help="Ring buffer name")

    # inspect
    ins_p = subparsers.add_parser("inspect", help="Inspect ring buffer status")
    ins_p.add_argument("--name", required=True, help="Ring buffer name")

    # destroy
    des_p = subparsers.add_parser("destroy", help="Destroy shared memory ring buffer")
    des_p.add_argument("--name", required=True, help="Ring buffer name")

    args = parser.parse_args()

    if args.action == "create":
        ring = SharedMemoryRingBuffer.create(name=args.name, capacity=args.capacity)
        _CLI_ACTIVE_RINGS[args.name] = ring
        print(f"Created ring buffer {args.name} with capacity {ring.capacity}")
    elif args.action == "push":
        ring = SharedMemoryRingBuffer.connect(name=args.name)
        try:
            seq = ring.write(args.data.encode("utf-8"))
            print(f"Wrote message (seq={seq}) to {args.name}")
        finally:
            ring.close()
    elif args.action == "pop":
        ring = SharedMemoryRingBuffer.connect(name=args.name)
        try:
            msg = ring.read()
            if msg is not None:
                print(msg.decode("utf-8", errors="replace"))
            else:
                print("<EMPTY>")
        finally:
            ring.close()
    elif args.action == "inspect":
        ring = SharedMemoryRingBuffer.connect(name=args.name)
        try:
            print(f"Capacity: {ring.capacity}")
            print(f"Available read: {ring.available_read_bytes}")
            print(f"Available write: {ring.available_write_bytes}")
        finally:
            ring.close()
    elif args.action == "destroy":
        active = _CLI_ACTIVE_RINGS.pop(args.name, None)
        if active is not None:
            active.destroy()
            print(f"Destroyed ring buffer {args.name}")
        else:
            try:
                ring = SharedMemoryRingBuffer.connect(name=args.name)
                ring.destroy()
                print(f"Destroyed ring buffer {args.name}")
            except Exception as e:
                print(f"Error destroying ring buffer {args.name}: {e}")


if __name__ == "__main__":
    main()
