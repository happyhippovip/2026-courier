"""Order book for the Repo Reality Check beta.

Receipts are an append-only JSONL log. Each line is hashed into a chain the
same way the v1 journal hashes an event (canonical JSON, previous hash, sha256).
The order file is a projection of that log. A receipt is made durable before
the projection is replaced, so a crash between the two is repaired by folding
the log again on the next open.

Payment becomes PAYMENT_CONFIRMED only through confirm_payment. ``fulfill``
fetches a public GitHub repository and writes the report. The order becomes
DELIVERED only after ``deliver --confirm-sent``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
import tempfile
import urllib.parse
import uuid
from pathlib import Path
from typing import Any, Callable, Mapping

from courier_core.events import GENESIS_HASH, canonical_json, utc_now
from courier_core.repo_reality_fetch import FetchError, fetch_public
from courier_core.repo_reality_report import build_report

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
_MAX_EVIDENCE = 500
_MAX_PAYMENT_EVIDENCE = 100
REPO_INPUT_MESSAGE = (
    "Beta nimmt nur öffentliche GitHub-Links an (https://github.com/owner/repo), keine ZIP-Dateien. "
    "/ The beta accepts public GitHub links only (https://github.com/owner/repo), no ZIP files."
)
PAYMENT_EVIDENCE_MESSAGE = (
    "Zahlungsbeleg: Transaktionsnummer des Anbieters, ohne Leerzeichen, höchstens 100 Zeichen. "
    "/ Payment evidence: the provider transaction id, no whitespace, at most 100 characters."
)
_GITHUB_HOST = "github.com"
_SHA40 = re.compile(r"^[0-9a-f]{40}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
FETCH_FAIL_REASON = "public repository could not be fetched"
REFUND_TEMPLATE = Path(__file__).resolve().parents[1] / "docs" / "REPO_REALITY_CHECK_DELIVERY.md"


class OrderError(ValueError):
    """The order cannot take this step. Nothing new is written."""


class FulfillmentError(OrderError):
    """The report was not written. ``template`` is the refund mail document."""

    def __init__(self, message: str, template: Path):
        super().__init__(message)
        self.template = template


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

    def create_order(
        self, order_id: str, repo_ref: str, contact: str, *, test: bool = False,
    ) -> dict[str, Any]:
        """Create an order. ``test=True`` marks a probe order that never counts as revenue."""
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
                or bool(existing.get("test")) != bool(test)
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
            "ready_evidence": None,
        }
        if test:
            order["test"] = True
        self._commit(order, NEW, None, from_status=None)
        return _public(order)

    def confirm_payment(self, order_id: str, evidence_ref: str) -> dict[str, Any]:
        """Record that payment was confirmed. This is never inferred from a later step."""
        _payment_evidence(evidence_ref)
        return self._move(order_id, PAYMENT_CONFIRMED, evidence_ref, allow_payment=True)

    def mark_running(self, order_id: str) -> dict[str, Any]:
        return self._move(order_id, RUNNING, None, allow_payment=False)

    def mark_delivered(self, order_id: str, evidence_ref: str) -> dict[str, Any]:
        return self._move(order_id, DELIVERED, evidence_ref, allow_payment=False)

    def mark_refunded(self, order_id: str, evidence_ref: str) -> dict[str, Any]:
        return self._move(order_id, REFUNDED, evidence_ref, allow_payment=False)

    def mark_failed(self, order_id: str, evidence_ref: str) -> dict[str, Any]:
        return self._move(order_id, FAILED, evidence_ref, allow_payment=False)

    def record_delivery_ready(self, order_id: str, evidence_ref: str) -> dict[str, Any]:
        """Remember report evidence while the order stays in progress."""
        order_id = _order_id(order_id)
        key = f"{order_id}:DELIVERY_READY"
        if key in self._seen:
            return _public(self._require(order_id))
        order = self._require(order_id)
        if order["status"] != RUNNING:
            raise OrderError("report evidence requires a started order")
        evidence = _evidence(evidence_ref)
        updated = dict(order)
        updated["ready_evidence"] = evidence
        self._commit(
            updated, "DELIVERY_READY", evidence, from_status=RUNNING, to_status=RUNNING,
        )
        return _public(updated)

    def fulfill(self, order_id: str, out_dir: str | os.PathLike) -> dict[str, Any]:
        """Prepare a report for a paid order. Delivery waits for confirm-sent.

        A started order that already has ``<order_id>-report.md`` reuses that
        file and does not fetch the repository again.
        """
        order = self._require(order_id)
        if order["status"] == NEW:
            raise OrderError("order is not paid")
        if order["status"] in {REFUNDED, FAILED, DELIVERED}:
            raise OrderError(f"{order['status']} cannot be fulfilled")
        report_path = Path(out_dir) / f"{order['order_id']}-report.md"
        if order["status"] == PAYMENT_CONFIRMED:
            self.mark_running(order_id)
            order = self._require(order_id)
        if order["status"] != RUNNING:
            raise OrderError(f"{order['status']} cannot be fulfilled")
        if report_path.is_file():
            if not order.get("ready_evidence"):
                self.record_delivery_ready(order_id, _ready_evidence(report_path))
            return _public(self._require(order_id))
        spec = _github_spec(order["repo_ref"])
        try:
            fetched = fetch_public(spec)
        except FetchError as exc:
            self.mark_failed(order_id, FETCH_FAIL_REASON)
            raise FulfillmentError(FETCH_FAIL_REASON, REFUND_TEMPLATE) from exc
        try:
            markdown = build_report(
                fetched.root,
                None,
                {
                    "source": f"github.com/{fetched.owner}/{fetched.repo}@{fetched.ref}",
                    "sha": fetched.sha,
                    "tarball_sha256": fetched.tarball_sha256,
                },
            )
        finally:
            shutil.rmtree(fetched.temp_dir, ignore_errors=True)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(markdown, encoding="utf-8")
        self.record_delivery_ready(order_id, _ready_evidence(report_path))
        return _public(self._require(order_id))

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

    def orders(self) -> list[dict[str, Any]]:
        return [_public(self._orders[order_id]) for order_id in sorted(self._orders)]

    def revenue_summary(self) -> dict[str, Any]:
        """Verified revenue is delivered work that has not been refunded.

        Pending is payment that is confirmed and not yet delivered, refunded,
        or failed. An unpaid order is neither. Test orders are never revenue;
        they are only counted in ``test_count``.
        """
        real = [order for order in self._orders.values() if not order.get("test")]
        verified = [order for order in real if order["status"] == DELIVERED]
        pending = [order for order in real if order["status"] in _PENDING]
        return {
            "test_count": len(self._orders) - len(real),
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

    def _commit(
        self,
        order: dict[str, Any],
        transition: str,
        evidence_ref: str | None,
        *,
        from_status: str | None,
        to_status: str | None = None,
    ) -> None:
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
            "to_status": transition if to_status is None else to_status,
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
    if receipt.get("transition") == "DELIVERY_READY":
        if current is None or current["status"] != RUNNING or status != RUNNING:
            raise OrderError("receipt log contains a transition the order cannot take")
        orders[order_id] = dict(snapshot)
        return
    if current is None or status not in _NEXT[current["status"]]:
        raise OrderError("receipt log contains a transition the order cannot take")
    orders[order_id] = dict(snapshot)


def _public(order: Mapping[str, Any]) -> dict[str, Any]:
    public = {
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
        "ready_evidence": order.get("ready_evidence"),
    }
    # Only present on test orders, so real order snapshots and their
    # receipt hashes stay exactly as before.
    if order.get("test"):
        public["test"] = True
    return public


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
    if (
        not cleaned
        or len(cleaned) > _MAX_EVIDENCE
        or "@" in cleaned
        or any(ch.isspace() and ch != " " for ch in cleaned)
    ):
        raise OrderError("evidence ref is required")
    return cleaned


def _payment_evidence(value: Any) -> str:
    """A provider transaction id: non-empty, no whitespace, short. No provider lookup."""
    if (
        not isinstance(value, str)
        or not value.strip()
        or len(value.strip()) > _MAX_PAYMENT_EVIDENCE
        or any(ch.isspace() for ch in value.strip())
        or "@" in value
    ):
        raise OrderError(PAYMENT_EVIDENCE_MESSAGE)
    return value.strip()


def github_repo_url(value: str) -> str:
    """Accept only https://github.com/owner/repo. Anything else is refused."""
    if not isinstance(value, str):
        raise OrderError(REPO_INPUT_MESSAGE)
    parsed = urllib.parse.urlsplit(value.strip())
    if (
        parsed.scheme != "https"
        or parsed.hostname != _GITHUB_HOST
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
    ):
        raise OrderError(REPO_INPUT_MESSAGE)
    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) != 2:
        raise OrderError(REPO_INPUT_MESSAGE)
    owner, repo = parts
    if repo.endswith(".git"):
        repo = repo[:-4]
    if not _github_segment(owner) or not _github_segment(repo):
        raise OrderError(REPO_INPUT_MESSAGE)
    return f"https://github.com/{owner}/{repo}"


def _github_spec(repo_url: str) -> str:
    parsed = urllib.parse.urlsplit(repo_url)
    owner, repo = [part for part in parsed.path.split("/") if part]
    return f"{owner}/{repo}"


def _ready_evidence(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    commit = _labeled(text, "Commit: ")
    # Current German label first; older reports on disk still carry the English one.
    tarball = _labeled(text, "Tarball-Prüfsumme (sha256): ") or _labeled(text, "Tarball sha256: ")
    if _SHA40.fullmatch(commit) is None or _SHA256.fullmatch(tarball) is None:
        raise OrderError("report is missing fetch evidence")
    return f"{report_evidence(path)};commit:{commit};tarball:{tarball}"


def _labeled(text: str, label: str) -> str:
    prefix = "- " + label
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith(prefix):
            return stripped[len(prefix):].strip()
    return ""


def _github_segment(value: str) -> bool:
    if not value or value in {".", ".."} or value.startswith(".") or value.endswith("."):
        return False
    return all(ch.isalnum() or ch in "._-" for ch in value)


def report_evidence(path: str | os.PathLike) -> str:
    """sha256 and byte size of a report file. The file contents are not returned."""
    file_path = Path(path)
    if not file_path.is_file():
        raise OrderError("report must be a file")
    digest = hashlib.sha256()
    size = 0
    with file_path.open("rb") as handle:
        while True:
            block = handle.read(1024 * 1024)
            if not block:
                break
            size += len(block)
            digest.update(block)
    if size == 0:
        raise OrderError("report is empty")
    return f"sha256:{digest.hexdigest()};bytes:{size}"


def courier_state_dir() -> Path:
    """Local Courier state directory. Orders live under it, not in a checkout."""
    configured = os.environ.get("COURIER_HOME")
    if configured:
        return Path(configured).expanduser()
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA")
        root = Path(base) if base else Path.home() / "AppData" / "Local"
        return root / "Courier"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "Courier"
    return Path.home() / ".courier"


def resolve_orders_dir(explicit: str | None = None) -> Path:
    """--data-dir, else COURIER_ORDERS_DIR, else <courier state>/reality-orders."""
    if explicit:
        chosen = Path(explicit).expanduser()
    elif os.environ.get("COURIER_ORDERS_DIR"):
        chosen = Path(os.environ["COURIER_ORDERS_DIR"]).expanduser()
    else:
        chosen = courier_state_dir() / "reality-orders"
    chosen = Path(os.path.abspath(chosen))
    if _inside_git_checkout(chosen):
        raise OrderError("data dir must not sit inside a git checkout")
    return chosen


def _inside_git_checkout(path: Path) -> bool:
    current = path
    while True:
        if (current / ".git").exists():
            return True
        parent = current.parent
        if parent == current:
            return False
        current = parent


def _eur(cents: int) -> str:
    sign = "-" if cents < 0 else ""
    amount = abs(int(cents))
    return f"{sign}{amount // 100}.{amount % 100:02d} EUR"


def _new_order_id() -> str:
    return "ord-" + uuid.uuid4().hex[:16]


def main(argv: list[str] | None = None) -> int:
    """Founder CLI. Payment is recorded only by confirm-payment."""
    parser = argparse.ArgumentParser(prog="python -m courier_core.reality_orders")
    parser.add_argument("--data-dir", default=None)
    commands = parser.add_subparsers(dest="cmd", required=True)

    create = commands.add_parser("new")
    create.add_argument("--repo", required=True)
    create.add_argument("--contact", required=True)
    create.add_argument(
        "--test", action="store_true",
        help="probe order; never counted as revenue",
    )

    confirm = commands.add_parser("confirm-payment")
    confirm.add_argument("order_id")
    confirm.add_argument("--evidence", required=True)

    start = commands.add_parser("start")
    start.add_argument("order_id")

    fulfill = commands.add_parser("fulfill")
    fulfill.add_argument("order_id")
    fulfill.add_argument("--out-dir", required=True)

    deliver = commands.add_parser("deliver")
    deliver.add_argument("order_id")
    deliver.add_argument("--report", default=None)
    deliver.add_argument("--confirm-sent", action="store_true")

    refund = commands.add_parser("refund")
    refund.add_argument("order_id")
    refund.add_argument("--reason", required=True)

    fail = commands.add_parser("fail")
    fail.add_argument("order_id")
    fail.add_argument("--reason", required=True)

    commands.add_parser("list")
    commands.add_parser("revenue")

    args = parser.parse_args(argv)
    try:
        directory = resolve_orders_dir(args.data_dir)
        book = OrderBook(directory)
        if args.cmd == "new":
            order = book.create_order(
                _new_order_id(), github_repo_url(args.repo), args.contact, test=args.test,
            )
            print(order["order_id"])
        elif args.cmd == "confirm-payment":
            order = book.confirm_payment(args.order_id, args.evidence)
            print(f"{order['order_id']} {order['status']}")
        elif args.cmd == "start":
            order = book.mark_running(args.order_id)
            print(f"{order['order_id']} {order['status']}")
        elif args.cmd == "fulfill":
            order = book.fulfill(args.order_id, args.out_dir)
            print(f"{order['order_id']} {order['status']}")
            print(Path(args.out_dir) / f"{order['order_id']}-report.md")
        elif args.cmd == "deliver":
            if args.confirm_sent == bool(args.report):
                raise OrderError("deliver needs --report or --confirm-sent")
            if args.confirm_sent:
                current = book.get(args.order_id)
                if not current.get("ready_evidence"):
                    raise OrderError("report has not been prepared")
                order = book.mark_delivered(args.order_id, current["ready_evidence"])
            else:
                order = book.mark_delivered(args.order_id, report_evidence(args.report))
            print(f"{order['order_id']} {order['status']}")
        elif args.cmd == "refund":
            order = book.mark_refunded(args.order_id, args.reason)
            print(f"{order['order_id']} {order['status']}")
        elif args.cmd == "fail":
            order = book.mark_failed(args.order_id, args.reason)
            print(f"{order['order_id']} {order['status']}")
        elif args.cmd == "list":
            for order in book.orders():
                marker = " TEST" if order.get("test") else ""
                print(f"{order['order_id']} {order['status']} {order['repo_ref']} {_eur(order['price_cents'])}{marker}")
        elif args.cmd == "revenue":
            summary = book.revenue_summary()
            print(f"verified {_eur(summary['verified_cents'])} ({summary['verified_count']})")
            print(f"pending {_eur(summary['pending_cents'])} ({summary['pending_count']})")
            if summary["test_count"]:
                print(f"test orders, not revenue ({summary['test_count']})")
        else:
            parser.error(f"unknown command {args.cmd}")
    except FulfillmentError as exc:
        print(exc.template)
        print(str(exc), file=sys.stderr)
        return 2
    except OrderError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
