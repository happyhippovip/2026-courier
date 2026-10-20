"""Dynamic Capability Self-Discovery and Host Fingerprinter for Courier Symphony.

Provides deterministic host capability probing, machine identification,
and tamper-evident SHA-256 / HMAC-SHA256 attestation tokens for worker environments.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import hashlib
import hmac
import json
import os
import platform
import sys
from typing import Any


class FingerprintError(Exception):
    """Base exception for host fingerprint operations."""


class TamperedFingerprintError(FingerprintError):
    """Raised when a fingerprint or attestation signature fails validation."""


@dataclass(frozen=True)
class HostCapabilities:
    """Probed system hardware and runtime capabilities."""

    os_name: str
    os_version: str
    arch: str
    cpu_count: int
    memory_bytes: int
    python_version: str
    python_implementation: str
    features: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> HostCapabilities:
        return cls(
            os_name=str(data.get("os_name", "")),
            os_version=str(data.get("os_version", "")),
            arch=str(data.get("arch", "")),
            cpu_count=int(data.get("cpu_count", 1)),
            memory_bytes=int(data.get("memory_bytes", 0)),
            python_version=str(data.get("python_version", "")),
            python_implementation=str(data.get("python_implementation", "")),
            features=list(data.get("features", [])),
        )


@dataclass(frozen=True)
class HostFingerprint:
    """Attested host fingerprint containing capabilities, machine identifier, and hash."""

    capabilities: HostCapabilities
    machine_id: str
    timestamp: str
    fingerprint_hash: str
    signature: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "capabilities": self.capabilities.to_dict(),
            "machine_id": self.machine_id,
            "timestamp": self.timestamp,
            "fingerprint_hash": self.fingerprint_hash,
            "signature": self.signature,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> HostFingerprint:
        return cls(
            capabilities=HostCapabilities.from_dict(data["capabilities"]),
            machine_id=str(data["machine_id"]),
            timestamp=str(data["timestamp"]),
            fingerprint_hash=str(data["fingerprint_hash"]),
            signature=data.get("signature"),
        )


def _get_system_memory() -> int:
    """Cross-platform physical RAM discovery without external dependencies."""
    # Windows native API
    if sys.platform == "win32":
        try:
            import ctypes
            from ctypes import wintypes

            class MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [
                    ("dwLength", wintypes.DWORD),
                    ("dwMemoryLoad", wintypes.DWORD),
                    ("ullTotalPhys", ctypes.c_uint64),
                    ("ullAvailPhys", ctypes.c_uint64),
                    ("ullTotalPageFile", ctypes.c_uint64),
                    ("ullAvailPageFile", ctypes.c_uint64),
                    ("ullTotalVirtual", ctypes.c_uint64),
                    ("ullAvailVirtual", ctypes.c_uint64),
                    ("sullAvailExtendedVirtual", ctypes.c_uint64),
                ]

            stat = MEMORYSTATUSEX()
            stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat)):
                return int(stat.ullTotalPhys)
        except Exception:
            pass

    # POSIX sysconf
    try:
        pages = os.sysconf("SC_PHYS_PAGES")
        page_size = os.sysconf("SC_PAGE_SIZE")
        if pages > 0 and page_size > 0:
            return int(pages * page_size)
    except Exception:
        pass

    # Linux /proc/meminfo fallback
    try:
        with open("/proc/meminfo", "r", encoding="utf-8") as f:
            for line in f:
                if line.startswith("MemTotal:"):
                    parts = line.split()
                    return int(parts[1]) * 1024
    except Exception:
        pass

    # Default fallback: 8GB
    return 8 * 1024 * 1024 * 1024


def _discover_features() -> list[str]:
    """Discover available Python and operating system features."""
    features = []

    # Multiprocessing
    try:
        import multiprocessing
        features.append("multiprocessing")
    except ImportError:
        pass

    # Shared memory
    try:
        from multiprocessing import shared_memory
        features.append("shared_memory")
    except ImportError:
        pass

    # SQLite3
    try:
        import sqlite3
        features.append("sqlite3")
    except ImportError:
        pass

    # SSL / TLS
    try:
        import ssl
        features.append("ssl")
    except ImportError:
        pass

    # Ctypes
    try:
        import ctypes
        features.append("ctypes")
    except ImportError:
        pass

    # Asyncio
    try:
        import asyncio
        features.append("asyncio")
    except ImportError:
        pass

    return sorted(features)


def _compute_machine_id() -> str:
    """Generate a deterministic machine identifier."""
    raw = f"{platform.node()}:{platform.system()}:{platform.machine()}:{sys.byteorder}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def probe_host_capabilities() -> HostCapabilities:
    """Probe the current host machine and runtime environment."""
    cpu_count = os.cpu_count() or 1
    memory_bytes = _get_system_memory()
    features = _discover_features()

    return HostCapabilities(
        os_name=platform.system(),
        os_version=platform.version(),
        arch=platform.machine(),
        cpu_count=cpu_count,
        memory_bytes=memory_bytes,
        python_version=platform.python_version(),
        python_implementation=platform.python_implementation(),
        features=features,
    )


def _canonical_bytes(capabilities: HostCapabilities, machine_id: str) -> bytes:
    """Produce deterministic canonical byte representation for hashing."""
    payload = {
        "capabilities": capabilities.to_dict(),
        "machine_id": machine_id,
    }
    canonical_json = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return canonical_json.encode("utf-8")


def generate_fingerprint(secret_key: str | None = None) -> HostFingerprint:
    """Generate a host fingerprint with optional HMAC-SHA256 attestation."""
    import datetime

    caps = probe_host_capabilities()
    mach_id = _compute_machine_id()
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()

    canon_bytes = _canonical_bytes(caps, mach_id)
    fp_hash = hashlib.sha256(canon_bytes).hexdigest()

    signature = None
    if secret_key:
        signature = hmac.new(
            secret_key.encode("utf-8"),
            canon_bytes,
            hashlib.sha256,
        ).hexdigest()

    return HostFingerprint(
        capabilities=caps,
        machine_id=mach_id,
        timestamp=now_iso,
        fingerprint_hash=fp_hash,
        signature=signature,
    )


def verify_fingerprint(fingerprint: HostFingerprint, secret_key: str | None = None) -> bool:
    """Verify integrity of host fingerprint and optional HMAC signature.

    Raises TamperedFingerprintError if invalid.
    """
    canon_bytes = _canonical_bytes(fingerprint.capabilities, fingerprint.machine_id)
    expected_hash = hashlib.sha256(canon_bytes).hexdigest()

    if not hmac.compare_digest(fingerprint.fingerprint_hash, expected_hash):
        raise TamperedFingerprintError(
            f"Fingerprint hash mismatch: expected {expected_hash}, got {fingerprint.fingerprint_hash}"
        )

    if secret_key:
        if not fingerprint.signature:
            raise TamperedFingerprintError("Fingerprint lacks attestation signature")

        expected_sig = hmac.new(
            secret_key.encode("utf-8"),
            canon_bytes,
            hashlib.sha256,
        ).hexdigest()

        if not hmac.compare_digest(fingerprint.signature, expected_sig):
            raise TamperedFingerprintError(
                f"Invalid attestation signature: expected {expected_sig}, got {fingerprint.signature}"
            )

    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="Host Capability Discovery & Fingerprinter")
    subparsers = parser.add_subparsers(dest="action", required=True)

    # inspect
    subparsers.add_parser("inspect", help="Inspect host capabilities and fingerprint")

    # attest
    att_p = subparsers.add_parser("attest", help="Generate attested host fingerprint")
    att_p.add_argument("--secret", required=True, help="HMAC secret key")
    att_p.add_argument("--output", help="Optional output JSON file path")

    # verify
    ver_p = subparsers.add_parser("verify", help="Verify fingerprint integrity")
    ver_p.add_argument("--file", required=True, help="Path to fingerprint JSON file")
    ver_p.add_argument("--secret", help="Optional HMAC secret key")

    args = parser.parse_args()

    if args.action == "inspect":
        fp = generate_fingerprint()
        print(json.dumps(fp.to_dict(), indent=2))
    elif args.action == "attest":
        fp = generate_fingerprint(secret_key=args.secret)
        raw = json.dumps(fp.to_dict(), indent=2)
        if args.output:
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(raw)
            print(f"Attested fingerprint written to {args.output}")
        else:
            print(raw)
    elif args.action == "verify":
        with open(args.file, "r", encoding="utf-8") as f:
            data = json.load(f)
        fp = HostFingerprint.from_dict(data)
        try:
            verify_fingerprint(fp, secret_key=args.secret)
            print("VERIFIED_OK")
        except TamperedFingerprintError as e:
            print(f"VERIFICATION_FAILED: {e}")
            sys.exit(1)


if __name__ == "__main__":
    main()
