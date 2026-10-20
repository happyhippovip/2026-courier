"""Cryptographic Event Receipt Signer and Verifier.

Provides HMAC-SHA256 based cryptographic authenticity, tamper-detection,
and timestamp verification for task event receipts across trust boundaries.
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

TIME_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


def _canonical_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def _parse_time(ts: str) -> datetime:
    return datetime.strptime(ts, TIME_FORMAT).replace(tzinfo=timezone.utc)


def _format_time(dt: datetime) -> str:
    return dt.strftime(TIME_FORMAT)


@dataclass
class SignedReceipt:
    """Cryptographically signed receipt envelope."""

    payload: dict[str, Any]
    signed_at: str
    signature: str
    key_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SignedReceipt":
        sig = data.get("signature")
        if not sig or not isinstance(sig, str):
            raise ValueError("Missing or invalid signature in receipt data")
        return cls(
            payload=data.get("payload", {}),
            signed_at=data.get("signed_at", ""),
            signature=sig,
            key_id=data.get("key_id"),
        )


@dataclass
class VerificationResult:
    """Outcome of signature and clock validation."""

    is_valid: bool
    reason: str  # "VALID" | "SIGNATURE_MISMATCH" | "CLOCK_SKEW_EXCEEDED" | "MALFORMED_RECEIPT"


class ReceiptSigner:
    """Signs receipts and verifies authenticity against a shared secret."""

    def __init__(
        self,
        secret_key: str,
        key_id: str | None = None,
        max_skew_sec: int = 300,
    ):
        self.secret_key = secret_key
        self.key_id = key_id
        self.max_skew_sec = max_skew_sec

    def _compute_digest(self, payload: dict[str, Any], signed_at: str) -> str:
        message = f"{signed_at}:{_canonical_json(payload)}"
        return hmac.new(
            self.secret_key.encode("utf-8"),
            message.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

    def sign(
        self,
        payload: dict[str, Any],
        now: datetime | None = None,
    ) -> SignedReceipt:
        cur_now = now or datetime.now(timezone.utc)
        ts_str = _format_time(cur_now)
        digest = self._compute_digest(payload, ts_str)
        return SignedReceipt(
            payload=payload,
            signed_at=ts_str,
            signature=f"hmac-sha256:{digest}",
            key_id=self.key_id,
        )

    def verify(
        self,
        receipt: SignedReceipt | dict[str, Any],
        now: datetime | None = None,
    ) -> VerificationResult:
        if isinstance(receipt, dict):
            try:
                signed_rcpt = SignedReceipt.from_dict(receipt)
            except Exception:
                return VerificationResult(is_valid=False, reason="MALFORMED_RECEIPT")
        else:
            signed_rcpt = receipt

        # 1. Clock skew check
        cur_now = now or datetime.now(timezone.utc)
        try:
            rcpt_time = _parse_time(signed_rcpt.signed_at)
            skew = abs((cur_now - rcpt_time).total_seconds())
            if skew > self.max_skew_sec:
                return VerificationResult(is_valid=False, reason="CLOCK_SKEW_EXCEEDED")
        except Exception:
            return VerificationResult(is_valid=False, reason="MALFORMED_RECEIPT")

        # 2. Signature verification
        expected_digest = self._compute_digest(signed_rcpt.payload, signed_rcpt.signed_at)
        expected_sig = f"hmac-sha256:{expected_digest}"

        if hmac.compare_digest(signed_rcpt.signature, expected_sig):
            return VerificationResult(is_valid=True, reason="VALID")
        return VerificationResult(is_valid=False, reason="SIGNATURE_MISMATCH")


def sign_receipt(
    payload: dict[str, Any],
    secret_key: str,
    key_id: str | None = None,
    now: datetime | None = None,
) -> SignedReceipt:
    signer = ReceiptSigner(secret_key=secret_key, key_id=key_id)
    return signer.sign(payload, now=now)


def verify_receipt(
    receipt: SignedReceipt | dict[str, Any],
    secret_key: str,
    max_skew_sec: int = 300,
    now: datetime | None = None,
) -> VerificationResult:
    signer = ReceiptSigner(secret_key=secret_key, max_skew_sec=max_skew_sec)
    return signer.verify(receipt, now=now)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Cryptographic Receipt Signer & Verifier.")
    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    # sign
    p_sign = subparsers.add_parser("sign")
    p_sign.add_argument("--input", required=True, help="Input receipt JSON file")
    p_sign.add_argument("--output", required=True, help="Output signed JSON file")
    p_sign.add_argument("--key", required=True, help="Secret HMAC key")
    p_sign.add_argument("--key-id", help="Optional key identifier")

    # verify
    p_ver = subparsers.add_parser("verify")
    p_ver.add_argument("--input", required=True, help="Signed receipt JSON file")
    p_ver.add_argument("--key", required=True, help="Secret HMAC key")
    p_ver.add_argument("--max-skew", type=int, default=300, help="Max clock skew seconds")

    args = parser.parse_args(argv)

    if args.subcommand == "sign":
        data = json.loads(Path(args.input).read_text(encoding="utf-8"))
        signer = ReceiptSigner(secret_key=args.key, key_id=args.key_id)
        signed = signer.sign(data)
        out_p = Path(args.output)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        out_p.write_text(json.dumps(signed.to_dict(), indent=2), encoding="utf-8")
        print(json.dumps({"status": "SIGNED", "signature": signed.signature}))
        return 0

    elif args.subcommand == "verify":
        data = json.loads(Path(args.input).read_text(encoding="utf-8"))
        signer = ReceiptSigner(secret_key=args.key, max_skew_sec=args.max_skew)
        result = signer.verify(data)
        print(json.dumps({"status": "VERIFIED", "is_valid": result.is_valid, "reason": result.reason}))
        return 0 if result.is_valid else 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
