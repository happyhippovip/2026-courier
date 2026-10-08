"""Repo Reality Check orders: payment is explicit, receipts survive a crash."""

import json

import pytest

from courier_core.reality_orders import (
    DELIVERED, NEW, PAYMENT_CONFIRMED, RUNNING, OrderBook, OrderError,
)

REPO = "https://github.com/example/repo"
ORDER = "ord-1"


def _contact():
    # Built at runtime so this file does not carry a raw address.
    return "buyer" + chr(64) + "example.invalid"


def _persisted(root):
    chunks = []
    for path in sorted(root.rglob("*")):
        if path.is_file():
            chunks.append(path.read_text(encoding="utf-8"))
    return "\n".join(chunks)


def _runner(order):
    assert order["status"] == RUNNING
    assert "contact" not in order
    return "report-" + order["order_id"]


def test_happy_path_counts_only_delivered_revenue(tmp_path):
    book = OrderBook(tmp_path)
    created = book.create_order(ORDER, REPO, _contact())
    assert created["status"] == NEW
    assert created["product"] == "Repo Reality Check beta"
    assert created["price_cents"] == 500
    assert created["currency"] == "EUR"
    assert created["contact_hash"] != _contact()
    assert _contact() not in created["contact_hash"]
    assert book.revenue_summary() == {
        "currency": "EUR", "verified_count": 0, "verified_cents": 0,
        "pending_count": 0, "pending_cents": 0, "test_count": 0,
    }

    book.confirm_payment(ORDER, "pay-1")
    assert book.revenue_summary()["pending_cents"] == 500
    assert book.revenue_summary()["verified_cents"] == 0

    delivered = book.run_report(ORDER, _runner)
    assert delivered["status"] == DELIVERED
    assert delivered["payment_evidence"] == "pay-1"
    assert delivered["delivery_evidence"] == "report-ord-1"
    summary = book.revenue_summary()
    assert summary["verified_count"] == 1 and summary["verified_cents"] == 500
    assert summary["pending_count"] == 0 and summary["pending_cents"] == 0
    assert _contact() not in _persisted(tmp_path)
    assert "@" not in _persisted(tmp_path)


def test_replays_are_noops(tmp_path):
    book = OrderBook(tmp_path)
    book.create_order(ORDER, "zip-upload", _contact())
    book.confirm_payment(ORDER, "pay-1")
    book.mark_running(ORDER)
    book.mark_delivered(ORDER, "report-ord-1")
    frozen = (tmp_path / "receipts.jsonl").read_bytes()
    state = (tmp_path / "orders.json").read_bytes()

    again = book.create_order(ORDER, "zip-upload", _contact())
    assert again["status"] == DELIVERED
    assert book.confirm_payment(ORDER, "pay-1")["status"] == DELIVERED
    assert book.mark_running(ORDER)["status"] == DELIVERED
    assert book.mark_delivered(ORDER, "report-ord-1")["status"] == DELIVERED
    assert book.run_report(ORDER, _runner)["status"] == DELIVERED
    assert (tmp_path / "receipts.jsonl").read_bytes() == frozen
    assert (tmp_path / "orders.json").read_bytes() == state
    assert book.revenue_summary()["verified_cents"] == 500


def test_crash_between_receipt_and_state_recovers(tmp_path):
    seen = {"n": 0}

    def crash_on_payment():
        seen["n"] += 1
        if seen["n"] == 2:
            raise RuntimeError("crash after receipt")

    book = OrderBook(tmp_path, on_receipt_durable=crash_on_payment)
    book.create_order(ORDER, REPO, _contact())
    with pytest.raises(RuntimeError, match="crash after receipt"):
        book.confirm_payment(ORDER, "pay-1")
    assert json.loads((tmp_path / "orders.json").read_text(encoding="utf-8"))["orders"][ORDER]["status"] == NEW
    lines = (tmp_path / "receipts.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    assert json.loads(lines[1])["transition"] == PAYMENT_CONFIRMED

    recovered = OrderBook(tmp_path)
    assert recovered.get(ORDER)["status"] == PAYMENT_CONFIRMED
    assert recovered.get(ORDER)["payment_evidence"] == "pay-1"
    assert recovered.revenue_summary()["pending_cents"] == 500
    opened = OrderBook(tmp_path)
    assert opened.get(ORDER)["status"] == PAYMENT_CONFIRMED
    assert opened.revenue_summary() == recovered.revenue_summary()


def test_illegal_transitions_write_nothing(tmp_path):
    book = OrderBook(tmp_path)
    book.create_order(ORDER, REPO, _contact())
    frozen = (tmp_path / "receipts.jsonl").read_bytes()
    for call in (
        lambda: book.mark_running(ORDER),
        lambda: book.mark_delivered(ORDER, "report-1"),
        lambda: book.mark_refunded(ORDER, "refund-1"),
        lambda: book.run_report(ORDER, _runner),
        lambda: book.confirm_payment(ORDER, ""),
        lambda: book.confirm_payment("missing", "pay-1"),
    ):
        with pytest.raises(OrderError):
            call()
    assert (tmp_path / "receipts.jsonl").read_bytes() == frozen
    assert book.get(ORDER)["status"] == NEW

    book.confirm_payment(ORDER, "pay-1")
    with pytest.raises(OrderError):
        book.mark_delivered(ORDER, "report-1")
    assert book.get(ORDER)["status"] == PAYMENT_CONFIRMED


def test_refund_leaves_verified_revenue(tmp_path):
    book = OrderBook(tmp_path)
    book.create_order(ORDER, REPO, _contact())
    book.create_order("ord-2", "zip-upload", _contact())
    book.confirm_payment(ORDER, "pay-1")
    book.confirm_payment("ord-2", "pay-2")
    book.run_report(ORDER, _runner)
    book.mark_running("ord-2")
    assert book.revenue_summary() == {
        "currency": "EUR", "verified_count": 1, "verified_cents": 500,
        "pending_count": 1, "pending_cents": 500, "test_count": 0,
    }
    refunded = book.mark_refunded(ORDER, "refund-1")
    assert refunded["status"] == "REFUNDED"
    assert book.revenue_summary() == {
        "currency": "EUR", "verified_count": 0, "verified_cents": 0,
        "pending_count": 1, "pending_cents": 500, "test_count": 0,
    }
    assert book.mark_refunded(ORDER, "refund-1")["status"] == "REFUNDED"
    assert _contact() not in _persisted(tmp_path)
    assert "@" not in _persisted(tmp_path)


def test_payment_is_not_inferred_and_identity_conflicts_fail(tmp_path):
    book = OrderBook(tmp_path)
    book.create_order(ORDER, REPO, _contact())
    with pytest.raises(OrderError):
        book.create_order(ORDER, "zip-upload", _contact())
    with pytest.raises(OrderError):
        book.create_order(ORDER, REPO, "other" + chr(64) + "example.invalid")
    assert book.get(ORDER)["status"] == NEW
    assert book.get(ORDER)["repo_ref"] == REPO


def test_test_orders_are_never_revenue_and_survive_reopen(tmp_path):
    book = OrderBook(tmp_path)
    real = book.create_order(ORDER, REPO, _contact())
    assert "test" not in real
    probe = book.create_order("ord-probe", REPO, _contact(), test=True)
    assert probe["test"] is True
    book.confirm_payment(ORDER, "pay-1")
    book.confirm_payment("ord-probe", "TEST-TXN-0000")
    assert book.revenue_summary()["pending_cents"] == 500
    book.run_report(ORDER, _runner)
    book.run_report("ord-probe", _runner)
    expected = {
        "currency": "EUR", "verified_count": 1, "verified_cents": 500,
        "pending_count": 0, "pending_cents": 0, "test_count": 1,
    }
    assert book.revenue_summary() == expected

    reopened = OrderBook(tmp_path)
    assert reopened.get("ord-probe")["test"] is True
    assert "test" not in reopened.get(ORDER)
    assert reopened.revenue_summary() == expected
    with pytest.raises(OrderError):
        reopened.create_order("ord-probe", REPO, _contact())
    with pytest.raises(OrderError):
        reopened.create_order(ORDER, REPO, _contact(), test=True)
    assert reopened.create_order("ord-probe", REPO, _contact(), test=True)["test"] is True
    assert "@" not in _persisted(tmp_path)
