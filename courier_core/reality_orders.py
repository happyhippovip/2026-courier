"""Order book for the Repo Reality Check beta.

Receipts are an append-only JSONL log. Each line is hashed into a chain the
same way the v1 journal hashes an event (canonical JSON, previous hash, sha256).
The order file is a projection of that log. A receipt is made durable before
the projection is replaced, so a crash between the two is repaired by folding
the log again on the next open.

Payment becomes PAYMENT_CONFIRMED only through confirm_payment. A report
runner is passed in by the caller. This module does not import one.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
import urllib.parse
from pathlib import Path
from typing import Any, Callable, Mapping

from courier_core.events import GENESIS_HASH, canonical_json, utc_now

PRODUCT = "Repo Reality Check beta"
PRICE_CENTS = 500
CURRENCY = "EUR"
ZIP_UPLOAD = "zip-upload"

NEW = "NEW"
PAYMENT_CONFIRMED = "PAYMENT_CONFIRMED"
RUNNING = "RUNNING"
DELIVERED = "DELIVERED"
REFUNDED = "REFUNDED"
FAILED = "FAILED"

STATUSES = frozenset({NEW, PAYMENT_CONFIRMED, RUNNING, DELIVERED, REFUNDED, FAILED})

# NEW -> PAYMENT_CONFIRMED is legal in the log, and confirm_payment is the
# only method that may append it.
_NEXT = {
    NEW: frozenset({PAYMENT_CONFIRMED, FAILED}),
    PAYMENT_CONFIRMED: frozenset({RUNNING, REFUNDED, FAILED}),
    RUNNING: frozenset({DELIVERED, REFUNDED, FAILED}),
    DELIVERED: frozenset({REFUNDED}),
    REFUNDED: frozenset(),
    FAILED: frozenset(),
}

_EVIDENCE_REQUIRED = frozenset({PAYMENT_CONFIRMED, DELIVERED, REFUNDED, FAILED})
_PENDING = frozenset({PAYMENT_CONFIRMED, RUNNING})
_MAX_ID = 80
_MAX_EVIDENCE = 200


class OrderError(ValueError):
    """The order cannot take this step. Nothing new is written."""


def contact_hash(contact: str, salt: bytes) -> str:
    """Salted hash of a contact address. The address itself is not returned."""
    material = b"courier-reality-order-v1\0" + salt + b"\0" + contact.encode("utf-8")
    return hashlib.sha256(material).hexdigest()


class OrderBook:
    """One directory: receipts.jsonl is the log, orders.json is the projection."""

    def __init__(self, directory: str | os.PathLike, *, on_receipt_durable: Callable[[], None] | None = None):
        self.root = Path(directory)
        self.receipts_path = self.root / "receipts.jsonl"
        self.state_path = self.root / "orders.json"
        self._on_receipt_durable = on_receipt_durable
        self._orders: dict[str, dict[str, Any]] = {}
        self._receipts: list[dict[str, Any]] = []
        self._seen: set[str] = set()
        self._head_hash = GENESIS_HASH
        self._closed = False
        self._load()

    def create_order(self, order_id: str, repo_ref: str, contact: str) -> dict[str, Any]:
        order_id = _order_id(order_id)
        repo_ref = _repo_ref(repo_ref)
        normalized = _contact(contact)
        existing = self._orders.get(order_id)
        if existing is not None:
            digest = contact_hash(normalized, bytes.fromhex(existing["contact_salt"]))
            if (
                digest != existing["contact_hash"]
                or repo_ref != existing["repo_ref"]
                or existing["product"] != PRODUCT
                or existing["price_cents"] != PRICE_CENTS
                or existing["currency"] != CURRENCY
            ):
                raise OrderError("order already exists with a different identity")
            return _public(existing)
        salt = os.urandom(16)
        order = {
            "order_id": order_id,
            "product": PRODUCT,
            "price_cents": PRICE_CENTS,
            "currency": CURRENCY,
            "repo_ref": repo_ref,
            "contact_hash": contact_hash(normalized, salt),
            "contact_salt": salt.hex(),
            "status": NEW,
            "payment_evidence": None,
            "delivery_evidence": None,
            "refund_evidence": None,
            "failure_evidence": None,
        }
        self._commit(order, NEW, None, from_status=None)
        return _public(order)

    def confirm_payment(self, order_id: str, evidence_ref: str) -> dict[str, Any]:
        """Record that payment was confirmed. This is never inferred from a later step."""
        return self._move(order_id, PAYMENT_CONFIRMED, evidence_ref, allow_payment=True)

    def mark_running(self, order_id: str) -> dict[str, Any]:
        return self._move(order_id, RUNNING, None, allow_payment=False)

    def mark_delivered(self, order_id: str, evidence_ref: str) -> dict[str, Any]:
        return self._move(order_id, DELIVERED, evidence_ref, allow_payment=False)

    def mark_refunded(self, order_id: str, evidence_ref: str) -> dict[str, Any]:
        return self._move(order_id, REFUNDED, evidence_ref, allow_payment=False)

    def mark_failed(self, order_id: str, evidence_ref: str) -> dict[str, Any]:
        return self._move(order_id, FAILED, evidence_ref, allow_payment=False)

    def run_report(self, order_id: str, runner: Callable[[Mapping[str, Any]], str]) -> dict[str, Any]:
        """Run an injected report callable and deliver its evidence reference.

        The callable is not imported here. A second call after delivery does
        not call it again.
        """
        if not callable(runner):
            raise OrderError("runner must be a callable")
        order = self._require(order_id)
        if order["status"] == DELIVERED:
            return _public(order)
        if order["status"] == PAYMENT_CONFIRMED:
            order = self._stored(self.mark_running(order_id))
        if order["status"] != RUNNING:
            raise OrderError(f"{order['status']} cannot run a report")
        evidence = runner(_public(order))
        return self.mark_delivered(order_id, evidence)

    def get(self, order_id: str) -> dict[str, Any]:
        return _public(self._require(order_id))

    def revenue_summary(self) -> dict[str, Any]:
        """Verified revenue is delivered work that has not been refunded.

        Pending is payment that is confirmed and not yet delivered, refunded,
        or failed. An unpaid order is neither.
        """
        verified = [order for order in self._orders.values() if order["status"] == DELIVERED]
        pending = [order for order in self._orders.values() if order["status"] in _PENDING]
        return {
            "currency": CURRENCY,
            "verified_count": len(verified),
            "verified_cents": sum(order["price_cents"] for order in verified),
            "pending_count": len(pending),
            "pending_cents": sum(order["price_cents"] for order in pending),
        }

    def _move(self, order_id: str, status: str, evidence_ref: str | None, *, allow_payment: bool) -> dict[str, Any]:
        if status == PAYMENT_CONFIRMED and not allow_payment:
            raise OrderError("payment is confirmed only by confirm_payment")
        if status not in STATUSES or status == NEW:
            raise OrderError("unknown status")
        order_id = _order_id(order_id)
        key = f"{order_id}:{status}"
        if key in self._seen:
            return _public(self._require(order_id))
        order = self._require(order_id)
        if status not in _NEXT[order["status"]]:
            raise OrderError(f"{order['status']} cannot move to {status}")
        evidence = _evidence(evidence_ref) if status in _EVIDENCE_REQUIRED else None
        updated = dict(order)
        updated["status"] = status
        if status == PAYMENT_CONFIRMED:
            updated["payment_evidence"] = evidence
        elif status == DELIVERED:
            updated["delivery_evidence"] = evidence
        elif status == REFUNDED:
            updated["refund_evidence"] = evidence
        elif status == FAILED:
            updated["failure_evidence"] = evidence
        self._commit(updated, status, evidence, from_status=order["status"])
        return _public(updated)

    def _commit(self, order: dict[str, Any], transition: str, evidence_ref: str | None, *, from_status: str | None) -> None:
        if self._closed:
            raise OrderError("order book stopped after a receipt and must be reopened")
        key = f"{order['order_id']}:{transition}"
        if key in self._seen:
            return
        receipt = {
            "schema_v": 1,
            "seq": len(self._receipts) + 1,
            "order_id": order["order_id"],
            "transition": transition,
            "from_status": from_status,
            "to_status": transition,
            "dedupe_key": key,
            "evidence_ref": evidence_ref,
            "order": _public(order),
            "ts_utc": utc_now(),
            "prev_hash": self._head_hash,
        }
        receipt["hash"] = _receipt_hash(receipt)
        _reject_contact_text(canonical_json(receipt))
        self._replace(self.receipts_path, _log_bytes(self._receipts + [receipt]))
        if self._on_receipt_durable is not None:
            try:
                self._on_receipt_durable()
            except Exception:
                self._closed = True
                raise
        self._receipts.append(receipt)
        self._seen.add(key)
        self._head_hash = receipt["hash"]
        self._orders[order["order_id"]] = order
        self._write_state()

    def _load(self) -> None:
        receipts = _read_receipts(self.receipts_path)
        orders: dict[str, dict[str, Any]] = {}
        seen: set[str] = set()
        prev = GENESIS_HASH
        for index, receipt in enumerate(receipts, start=1):
            if receipt.get("seq") != index or receipt.get("prev_hash") != prev:
                raise OrderError("receipt chain does not match the log")
            if receipt.get("hash") != _receipt_hash(receipt):
                raise OrderError("receipt hash does not match the log")
            key = receipt.get("dedupe_key")
            if key in seen:
                prev = receipt["hash"]
                continue
            _fold_one(orders, receipt)
            seen.add(key)
            prev = receipt["hash"]
        self._orders = orders
        self._receipts = receipts
        self._seen = seen
        self._head_hash = prev
        state = _read_state(self.state_path)
        head_seq = len(receipts)
        if state is None or state.get("head_seq") != head_seq or state.get("head_hash") != prev:
            if receipts or state is not None:
                self._write_state()

    def _write_state(self) -> None:
        document = {
            "head_hash": self._head_hash,
            "head_seq": len(self._receipts),
            "orders": {order_id: _public(order) for order_id, order in sorted(self._orders.items())},
        }
        text = canonical_json(document)
        _reject_contact_text(text)
        self._replace(self.state_path, (text + "\n").encode("utf-8"))

    def _replace(self, path: Path, payload: bytes) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(dir=self.root, prefix=path.name + ".")
        tmp = Path(tmp_name)
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp, path)
        except Exception:
            if tmp.exists():
                tmp.unlink()
            raise

    def _require(self, order_id: str) -> dict[str, Any]:
        if self._closed:
            raise OrderError("order book stopped after a receipt and must be reopened")
        order_id = _order_id(order_id)
        order = self._orders.get(order_id)
        if order is None:
            raise OrderError("unknown order")
        return order

    def _stored(self, public: Mapping[str, Any]) -> dict[str, Any]:
        return self._orders[public["order_id"]]


def _fold_one(orders: dict[str, dict[str, Any]], receipt: Mapping[str, Any]) -> None:
    order_id = receipt.get("order_id")
    status = receipt.get("to_status")
    snapshot = receipt.get("order")
    if not isinstance(order_id, str) or status not in STATUSES or not isinstance(snapshot, Mapping):
        raise OrderError("receipt is not an order transition")
    if snapshot.get("order_id") != order_id or snapshot.get("status") != status:
        raise OrderError("receipt does not match its order snapshot")
    _reject_contact_text(canonical_json(snapshot))
    current = orders.get(order_id)
    if status == NEW:
        if current is not None:
            raise OrderError("duplicate create in the log")
        orders[order_id] = dict(snapshot)
        return
    if current is None or status not in _NEXT[current["status"]]:
        raise OrderError("receipt log contains a transition the order cannot take")
    orders[order_id] = dict(snapshot)


def _public(order: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "order_id": order["order_id"],
        "product": order["product"],
        "price_cents": order["price_cents"],
        "currency": order["currency"],
        "repo_ref": order["repo_ref"],
        "contact_hash": order["contact_hash"],
        "contact_salt": order["contact_salt"],
        "status": order["status"],
        "payment_evidence": order["payment_evidence"],
        "delivery_evidence": order["delivery_evidence"],
        "refund_evidence": order["refund_evidence"],
        "failure_evidence": order["failure_evidence"],
    }


def _receipt_hash(receipt: Mapping[str, Any]) -> str:
    material = {key: receipt[key] for key in (
        "schema_v", "seq", "order_id", "transition", "from_status", "to_status",
        "dedupe_key", "evidence_ref", "order", "ts_utc", "prev_hash",
    )}
    return hashlib.sha256(canonical_json(material).encode("utf-8")).hexdigest()


def _log_bytes(receipts: list[dict[str, Any]]) -> bytes:
    return b"".join((canonical_json(receipt) + "\n").encode("utf-8") for receipt in receipts)


def _read_receipts(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    raw = path.read_bytes()
    if not raw:
        return []
    text = raw.decode("utf-8")
    lines = text.splitlines()
    if text.endswith("\n"):
        kept = lines
    else:
        # A torn final line is not part of the log. Anything before it must parse.
        kept = lines[:-1]
    receipts = []
    for line in kept:
        if not line:
            raise OrderError("receipt log has an empty line")
        try:
            receipt = json.loads(line)
        except ValueError as exc:
            raise OrderError("receipt log is not json") from exc
        if not isinstance(receipt, dict):
            raise OrderError("receipt log is not json")
        receipts.append(receipt)
    return receipts


def _read_state(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError) as exc:
        raise OrderError("order projection is unreadable") from exc
    if not isinstance(document, dict):
        raise OrderError("order projection is unreadable")
    return document


def _reject_contact_text(text: str) -> None:
    if "@" in text:
        raise OrderError("persisted order data must not contain a contact address")


def _order_id(value: Any) -> str:
    if not isinstance(value, str) or not value or len(value) > _MAX_ID:
        raise OrderError("order id must be a short non-empty string")
    if any(ch not in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789._:-" for ch in value):
        raise OrderError("order id must be a short non-empty string")
    return value


def _repo_ref(value: Any) -> str:
    if value == ZIP_UPLOAD:
        return value
    if not isinstance(value, str) or "@" in value or len(value) > 300:
        raise OrderError("repo ref must be a public url or zip-upload")
    parsed = urllib.parse.urlsplit(value)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise OrderError("repo ref must be a public url or zip-upload")
    if parsed.username or parsed.password:
        raise OrderError("repo ref must be a public url or zip-upload")
    return value


def _contact(value: Any) -> str:
    if not isinstance(value, str):
        raise OrderError("contact is required")
    normalized = value.strip().casefold()
    if "@" not in normalized or len(normalized) > 320 or any(ch.isspace() for ch in normalized):
        raise OrderError("contact is required")
    return normalized


def _evidence(value: Any) -> str:
    if not isinstance(value, str):
        raise OrderError("evidence ref is required")
    cleaned = value.strip()
    if not cleaned or len(cleaned) > _MAX_EVIDENCE or "@" in cleaned or any(ch.isspace() for ch in cleaned):
        raise OrderError("evidence ref is required")
    return cleaned
