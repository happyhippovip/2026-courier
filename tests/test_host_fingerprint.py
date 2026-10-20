"""Tests for courier_core.host_fingerprint - Dynamic Capability Self-Discovery and Host Fingerprinter."""

from __future__ import annotations

import json
import pytest

from courier_core.host_fingerprint import (
    HostCapabilities,
    HostFingerprint,
    probe_host_capabilities,
    generate_fingerprint,
    verify_fingerprint,
    TamperedFingerprintError,
    main,
)


def test_probe_host_capabilities():
    caps = probe_host_capabilities()
    assert isinstance(caps, HostCapabilities)
    assert caps.os_name in ("Windows", "Linux", "Darwin")
    assert caps.cpu_count >= 1
    assert caps.memory_bytes > 0
    assert caps.arch != ""
    assert "shared_memory" in caps.features
    assert "multiprocessing" in caps.features


def test_generate_and_verify_fingerprint_unattested():
    fp = generate_fingerprint()
    assert isinstance(fp, HostFingerprint)
    assert len(fp.fingerprint_hash) == 64  # SHA-256 hex string
    assert fp.signature is None

    # Verification should succeed
    assert verify_fingerprint(fp) is True


def test_generate_and_verify_fingerprint_with_hmac():
    secret = "courier-titan-secret-key-2026"
    fp = generate_fingerprint(secret_key=secret)
    assert fp.signature is not None
    assert len(fp.signature) == 64

    # Verify with correct secret succeeds
    assert verify_fingerprint(fp, secret_key=secret) is True

    # Verify with incorrect secret raises or returns False
    with pytest.raises(TamperedFingerprintError, match="Invalid attestation signature"):
        verify_fingerprint(fp, secret_key="wrong-secret-key")


def test_tampered_payload_detection():
    fp = generate_fingerprint(secret_key="secure-key")
    data = fp.to_dict()

    # Tamper with memory or cpu count
    data["capabilities"]["cpu_count"] += 999
    tampered_fp = HostFingerprint.from_dict(data)

    with pytest.raises(TamperedFingerprintError, match="Fingerprint hash mismatch"):
        verify_fingerprint(tampered_fp, secret_key="secure-key")


def test_serialization_roundtrip():
    fp = generate_fingerprint(secret_key="my-key")
    raw = json.dumps(fp.to_dict())
    loaded = HostFingerprint.from_dict(json.loads(raw))

    assert loaded.fingerprint_hash == fp.fingerprint_hash
    assert loaded.signature == fp.signature
    assert loaded.capabilities.os_name == fp.capabilities.os_name
    assert loaded.capabilities.cpu_count == fp.capabilities.cpu_count


def test_cli_host_fingerprint_inspect(monkeypatch, capsys):
    monkeypatch.setattr("sys.argv", ["host_fingerprint.py", "inspect"])
    main()
    out = capsys.readouterr().out
    data = json.loads(out)
    assert "capabilities" in data
    assert "fingerprint_hash" in data
    assert len(data["fingerprint_hash"]) == 64


def test_cli_host_fingerprint_attest_and_verify(tmp_path, monkeypatch, capsys):
    fp_path = tmp_path / "fingerprint.json"
    secret = "audit-key-xyz"

    # Attest
    monkeypatch.setattr(
        "sys.argv",
        ["host_fingerprint.py", "attest", "--secret", secret, "--output", str(fp_path)],
    )
    main()
    assert fp_path.exists()

    # Verify
    monkeypatch.setattr(
        "sys.argv",
        ["host_fingerprint.py", "verify", "--file", str(fp_path), "--secret", secret],
    )
    main()
    out = capsys.readouterr().out
    assert "VERIFIED_OK" in out
