"""Tests for Cryptographic Event Receipt Signer and Verifier."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
import pytest

from courier_core.receipt_signer import (
    ReceiptSigner,
    SignedReceipt,
    VerificationResult,
    sign_receipt,
    verify_receipt,
    main,
)


def test_sign_and_verify_valid_receipt():
    secret = "secret-token-key-2026"
    event_payload = {
        "event_id": "evt-1234",
        "item_id": "P20",
        "holder": "windows-titan",
        "status": "DONE",
        "result_hash": "sha256:abc123def456",
    }
    now = datetime(2026, 10, 18, 12, 0, 0, tzinfo=timezone.utc)

    signer = ReceiptSigner(secret_key=secret)
    signed = signer.sign(event_payload, now=now)

    assert signed.signature.startswith("hmac-sha256:")
    assert signed.signed_at == "2026-10-18T12:00:00Z"
    assert signed.payload == event_payload

    # Verify
    result = signer.verify(signed, now=now)
    assert result.is_valid is True
    assert result.reason == "VALID"


def test_tampered_payload_fails_verification():
    secret = "secret-token-key-2026"
    event_payload = {
        "event_id": "evt-tamper",
        "item_id": "P20",
        "status": "DONE",
    }
    signer = ReceiptSigner(secret_key=secret)
    signed = signer.sign(event_payload)

    # Tamper with the payload
    signed.payload["status"] = "BLOCKED"

    result = signer.verify(signed)
    assert result.is_valid is False
    assert result.reason == "SIGNATURE_MISMATCH"


def test_wrong_secret_key_fails_verification():
    signer_legit = ReceiptSigner(secret_key="legit-key-1")
    signer_fake = ReceiptSigner(secret_key="attacker-key-2")

    signed = signer_legit.sign({"event_id": "evt-key", "item_id": "P20"})

    result = signer_fake.verify(signed)
    assert result.is_valid is False
    assert result.reason == "SIGNATURE_MISMATCH"


def test_clock_skew_tolerance_and_rejection():
    secret = "secret-token-key-2026"
    signer = ReceiptSigner(secret_key=secret, max_skew_sec=300)

    t0 = datetime(2026, 10, 18, 12, 0, 0, tzinfo=timezone.utc)
    signed = signer.sign({"event_id": "evt-time"}, now=t0)

    # Within tolerance (200 seconds later)
    t_ok = t0 + timedelta(seconds=200)
    assert signer.verify(signed, now=t_ok).is_valid is True

    # Beyond tolerance (400 seconds later)
    t_late = t0 + timedelta(seconds=400)
    res_late = signer.verify(signed, now=t_late)
    assert res_late.is_valid is False
    assert res_late.reason == "CLOCK_SKEW_EXCEEDED"


def test_canonical_json_ordering_invariance():
    secret = "secret-key"
    signer = ReceiptSigner(secret_key=secret)

    dict_a = {"alpha": 1, "beta": 2, "gamma": [3, 4]}
    dict_b = {"gamma": [3, 4], "beta": 2, "alpha": 1}

    t = datetime(2026, 10, 18, 12, 0, 0, tzinfo=timezone.utc)
    signed_a = signer.sign(dict_a, now=t)
    signed_b = signer.sign(dict_b, now=t)

    assert signed_a.signature == signed_b.signature


def test_missing_or_corrupt_signature():
    signer = ReceiptSigner(secret_key="secret-key")
    invalid_data = {
        "payload": {"item_id": "P20"},
        "signed_at": "2026-10-18T12:00:00Z",
        # signature missing
    }
    with pytest.raises(ValueError, match="Missing or invalid signature"):
        SignedReceipt.from_dict(invalid_data)


def test_cli_invocation_sign_and_verify(tmp_path):
    receipt_file = tmp_path / "receipt.json"
    signed_file = tmp_path / "signed_receipt.json"

    data = {"event_id": "evt-cli", "item_id": "P20", "status": "DONE"}
    receipt_file.write_text(json.dumps(data), encoding="utf-8")

    # 1. Sign
    code_sign = main([
        "sign",
        "--input", str(receipt_file),
        "--output", str(signed_file),
        "--key", "cli-test-token",
    ])
    assert code_sign == 0
    assert signed_file.exists()

    # 2. Verify valid
    code_verify = main([
        "verify",
        "--input", str(signed_file),
        "--key", "cli-test-token",
    ])
    assert code_verify == 0

    # 3. Verify with wrong key fails with non-zero
    code_verify_wrong = main([
        "verify",
        "--input", str(signed_file),
        "--key", "wrong-key",
    ])
    assert code_verify_wrong != 0
