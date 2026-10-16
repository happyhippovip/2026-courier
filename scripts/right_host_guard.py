#!/usr/bin/env python3
"""
Right-Host Guard (FRZ-01): Proves host identity before executing recovery or ops operations.
Prevents emergency or recovery commands intended for a specific host (e.g. local Windows machine)
from executing on the wrong machine (e.g. cloud VM or peer Mac).
"""
from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
import os
import platform
import sys
from pathlib import Path


class WrongHostError(RuntimeError):
    """Raised when an operation is executed on the wrong host or platform."""


@dataclasses.dataclass(frozen=True)
class HostIdentity:
    hostname: str
    os_platform: str
    machine: str
    device_id: str
    is_cloud_vm: bool
    user: str

    def to_dict(self) -> dict:
        return dataclasses.asdict(self)


def get_default_data_dir() -> Path:
    if os.environ.get("COURIER_HOME"):
        return Path(os.environ["COURIER_HOME"])
    if sys.platform == "win32":
        return Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / "Courier"
    elif sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "Courier"
    else:
        return Path.home() / ".courier"


def _read_os_native_device_id() -> str | None:
    if sys.platform == "win32":
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Cryptography") as key:
                val, _ = winreg.QueryValueEx(key, "MachineGuid")
                if val:
                    return str(val).strip()
        except Exception:
            pass
    elif sys.platform == "linux":
        for p in (Path("/etc/machine-id"), Path("/var/lib/dbus/machine-id")):
            if p.is_file():
                try:
                    val = p.read_text().strip()
                    if val:
                        return val
                except Exception:
                    pass
    return None


def get_device_id(app_data_dir: Path | None = None) -> str:
    native_id = _read_os_native_device_id()
    if native_id:
        return native_id

    if app_data_dir is None:
        app_data_dir = get_default_data_dir()

    device_file = app_data_dir / "device_id"
    if device_file.is_file():
        try:
            cached = device_file.read_text().strip()
            if cached:
                return cached
        except OSError:
            pass

    # Generate deterministic fallback ID from hostname, user and platform
    seed = f"{platform.node()}:{sys.platform}:{platform.machine()}:{os.environ.get('USER', os.environ.get('USERNAME', 'default'))}"
    dev_id = f"DEV-{hashlib.sha256(seed.encode()).hexdigest()[:16]}"

    try:
        app_data_dir.mkdir(parents=True, exist_ok=True)
        device_file.write_text(dev_id, encoding="utf-8")
    except OSError:
        pass

    return dev_id


def is_cloud_vm() -> bool:
    if os.environ.get("GITHUB_ACTIONS") == "true" or os.environ.get("CI") == "true":
        return True
    if os.environ.get("COURIER_IS_CLOUD") == "1":
        return True
    if Path("/.dockerenv").exists():
        return True
    hostname = platform.node().lower()
    if any(h in hostname for h in ("github", "runner", "codespaces", "gitpod")):
        return True
    return False


def get_current_host_identity(app_data_dir: Path | None = None) -> HostIdentity:
    hostname = platform.node()
    os_platform = sys.platform
    machine = platform.machine()
    device_id = get_device_id(app_data_dir)
    cloud = is_cloud_vm()
    user = os.environ.get("USERNAME", os.environ.get("USER", "unknown"))

    return HostIdentity(
        hostname=hostname,
        os_platform=os_platform,
        machine=machine,
        device_id=device_id,
        is_cloud_vm=cloud,
        user=user,
    )


def verify_right_host(
    expected_host: str | None = None,
    expected_os: str | None = None,
    expected_device_id: str | None = None,
    disallow_cloud: bool = False,
    app_data_dir: Path | None = None,
) -> tuple[bool, str]:
    current = get_current_host_identity(app_data_dir)

    if expected_os and expected_os.lower() != current.os_platform.lower():
        return False, (
            f"OS mismatch: expected '{expected_os}', but running on '{current.os_platform}'. "
            "Operation refused to prevent cross-platform control plane confusion."
        )

    if expected_host and expected_host.lower() != current.hostname.lower():
        return False, (
            f"Hostname mismatch: expected '{expected_host}', but running on '{current.hostname}'. "
            "Operation refused to prevent issuing recovery commands to the wrong machine."
        )

    if expected_device_id and expected_device_id.lower() != current.device_id.lower():
        return False, (
            f"Device ID mismatch: expected '{expected_device_id}', but running on '{current.device_id}'."
        )

    if disallow_cloud and current.is_cloud_vm:
        return False, (
            "Cloud VM detected: operation requires a physical target machine."
        )

    return True, "Host identity verified: right host proven."


def assert_right_host(
    expected_host: str | None = None,
    expected_os: str | None = None,
    expected_device_id: str | None = None,
    disallow_cloud: bool = False,
    app_data_dir: Path | None = None,
) -> HostIdentity:
    ok, reason = verify_right_host(
        expected_host=expected_host,
        expected_os=expected_os,
        expected_device_id=expected_device_id,
        disallow_cloud=disallow_cloud,
        app_data_dir=app_data_dir,
    )
    if not ok:
        raise WrongHostError(f"RIGHT-HOST GUARD REFUSAL: {reason}")
    return get_current_host_identity(app_data_dir)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Right-Host Guard: Proves host identity for ops/recovery")
    parser.add_argument("--require-os", help="Required operating system (e.g. win32, darwin, linux)")
    parser.add_argument("--require-host", help="Required hostname")
    parser.add_argument("--require-device", help="Required device ID")
    parser.add_argument("--disallow-cloud", action="store_true", help="Reject cloud or container runner environments")
    parser.add_argument("--json", action="store_true", help="Output machine-readable host identity JSON")
    args = parser.parse_args(argv)

    identity = get_current_host_identity()

    if args.json:
        print(json.dumps(identity.to_dict(), indent=2))

    ok, reason = verify_right_host(
        expected_host=args.require_host,
        expected_os=args.require_os,
        expected_device_id=args.require_device,
        disallow_cloud=args.disallow_cloud,
    )

    if not args.json:
        print(f"Host Identity: {identity.hostname} ({identity.os_platform}, {identity.machine})")
        print(f"Device ID:     {identity.device_id}")
        print(f"Cloud VM:      {identity.is_cloud_vm}")
        print(f"Status:        {'VERIFIED' if ok else 'REFUSED'}: {reason}")

    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
