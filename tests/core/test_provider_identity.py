"""Provider identity capture, fingerprint, and strict record parsing."""

import json
import sys
from pathlib import Path

import pytest

from courier_core.provider_identity import (
    OUTPUT_CAP,
    SOURCE_CLI,
    SOURCE_UNKNOWN,
    VERSION_UNKNOWN,
    ProviderIdentity,
    ProviderIdentityError,
    capture_identity,
)

ROOT = Path(__file__).resolve().parents[2]
SCHEMA = ROOT / "courier_core" / "schemas" / "provider_identity.schema.json"


def _script(tmp_path, name, body):
    path = tmp_path / name
    path.write_text(body, encoding="utf-8")
    return [sys.executable, str(path)]


def _capture(tmp_path, body, name="tool.py", timeout=5):
    return capture_identity(
        "tool-a",
        _script(tmp_path, name, body),
        timeout,
        provider_kind="executable",
        captured_at="2026-10-08T07:00:00Z",
    )


def test_capture_records_reported_version(tmp_path):
    identity = _capture(tmp_path, "print('acme 1.2.3')\n")
    assert identity.provider_id == "tool-a"
    assert identity.provider_kind == "executable"
    assert identity.version == "acme 1.2.3"
    assert identity.version_source == SOURCE_CLI
    assert identity.binary_fingerprint is not None
    assert len(identity.binary_fingerprint) == 64
    assert identity.captured_at == "2026-10-08T07:00:00Z"


def test_timeout_is_unknown(tmp_path):
    identity = _capture(tmp_path, "import time\ntime.sleep(30)\nprint('late')\n", timeout=0.4)
    assert identity.version == VERSION_UNKNOWN
    assert identity.version_source == SOURCE_UNKNOWN


def test_nonzero_exit_is_unknown(tmp_path):
    identity = _capture(tmp_path, "import sys\nprint('nope')\nsys.exit(2)\n")
    assert identity.version == VERSION_UNKNOWN
    assert identity.version_source == SOURCE_UNKNOWN


def test_huge_output_is_capped(tmp_path):
    identity = _capture(tmp_path, "print('A' * 100000)\n")
    assert identity.version_source == SOURCE_CLI
    assert identity.version == "A" * OUTPUT_CAP
    assert len(identity.version) == OUTPUT_CAP


def test_round_trip(tmp_path):
    identity = _capture(tmp_path, "print('acme 1.2.3')\n")
    again = ProviderIdentity.from_dict(identity.to_dict())
    assert again == identity
    assert again.fingerprint() == identity.fingerprint()

    configured = ProviderIdentity.from_dict({
        "provider_id": "tool-b",
        "provider_kind": "executable",
        "version": "9.0",
        "version_source": "config",
        "binary_fingerprint": None,
        "captured_at": "2026-10-08T07:00:00Z",
    })
    assert ProviderIdentity.from_dict(configured.to_dict()) == configured


def test_unknown_key_rejected(tmp_path):
    data = _capture(tmp_path, "print('acme 1.2.3')\n").to_dict()
    data["extra"] = "no"
    with pytest.raises(ProviderIdentityError, match="unknown field"):
        ProviderIdentity.from_dict(data)


def test_fingerprint_changes_when_version_changes(tmp_path):
    identity = _capture(tmp_path, "print('acme 1.2.3')\n")
    changed = ProviderIdentity.from_dict({**identity.to_dict(), "version": "acme 1.2.4"})
    assert changed.fingerprint() != identity.fingerprint()
    later = ProviderIdentity.from_dict({**identity.to_dict(), "captured_at": "2026-10-08T08:00:00Z"})
    assert later.fingerprint() == identity.fingerprint()


def test_schema_rejects_unknown_fields():
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    assert schema["additionalProperties"] is False
    assert schema["required"] == [
        "provider_id",
        "provider_kind",
        "version",
        "version_source",
        "binary_fingerprint",
        "captured_at",
    ]
    assert schema["properties"]["version_source"]["enum"] == ["cli_reported", "config", "unknown"]
