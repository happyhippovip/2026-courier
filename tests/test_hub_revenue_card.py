"""Hub revenue card: read-only order/revenue state, no payments, no network."""

import json

import pytest

from courier_core.reality_orders import (
    CURRENCY,
    DELIVERED,
    FAILED,
    NEW,
    PAYMENT_CONFIRMED,
    PRICE_CENTS,
    PRODUCT,
    REFUNDED,
    RUNNING,
    OrderBook,
    OrderError,
)
from courier_hub.revenue_card import revenue_card, revenue_card_from_book

REPO = "https://github.com/example/repo"


def _contact(tag="buyer"):
    # Built at runtime so this file does not carry a raw address.
    return tag + chr(64) + "example.invalid"


def _seed(root, paid=0, delivered=0):
    """Seed a book: `paid` orders stop at PAYMENT_CONFIRMED, `delivered` run to DELIVERED."""
    book = OrderBook(root)
    for index in range(paid + delivered):
        order_id = f"ord-{index}"
        book.create_order(order_id, REPO, _contact(f"buyer{index}"))
        if index >= paid:
            book.confirm_payment(order_id, f"pay-{index}")
            book.mark_running(order_id)
            book.mark_delivered(order_id, f"dlv-{index}")
        else:
            book.confirm_payment(order_id, f"pay-{index}")
    return book


def _receipt_lines(root):
    path = root / "receipts.jsonl"
    if not path.exists():
        return []
    return [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_empty_directory_is_zero_state(tmp_path):
    card = revenue_card(tmp_path / "orders")
    assert card["product"] == PRODUCT
    assert card["currency"] == CURRENCY
    assert card["price_cents"] == PRICE_CENTS
    assert card["order_count"] == 0
    assert card["orders"] == []
    assert card["revenue"] == {
        "currency": CURRENCY,
        "verified_count": 0,
        "verified_cents": 0,
        "pending_count": 0,
        "pending_cents": 0,
    }
    assert sum(card["counts"].values()) == 0


def test_counts_and_revenue_follow_statuses(tmp_path):
    root = tmp_path / "orders"
    book = OrderBook(root)
    book.create_order("ord-new", REPO, _contact())
    book.create_order("ord-run", REPO, _contact("other"))
    book.confirm_payment("ord-run", "pay-1")
    book.mark_running("ord-run")
    _seed(root, paid=1, delivered=2)
    card = revenue_card(root)
    assert card["counts"][NEW] == 1
    assert card["counts"][RUNNING] == 1
    assert card["counts"][PAYMENT_CONFIRMED] == 1
    assert card["counts"][DELIVERED] == 2
    assert card["order_count"] == 5
    assert card["revenue"]["verified_count"] == 2
    assert card["revenue"]["verified_cents"] == 2 * PRICE_CENTS
    assert card["revenue"]["pending_count"] == 2
    assert card["revenue"]["pending_cents"] == 2 * PRICE_CENTS


def test_card_carries_no_contact_and_appends_no_receipt(tmp_path):
    root = tmp_path / "orders"
    _seed(root, paid=1, delivered=1)
    before = _receipt_lines(root)
    card = revenue_card(root)
    assert _receipt_lines(root) == before
    blob = json.dumps(card)
    assert _contact() not in blob
    assert chr(64) + "example.invalid" not in blob
    assert "contact" not in blob
    for row in card["orders"]:
        assert set(row) == {
            "order_id", "product", "price_cents", "currency", "repo_ref",
            "status", "payment_evidence", "delivery_evidence",
            "refund_evidence", "failure_evidence", "ready_evidence",
        }


def test_refund_leaves_verified_and_pending(tmp_path):
    root = tmp_path / "orders"
    book = OrderBook(root)
    book.create_order("ord-1", REPO, _contact())
    book.confirm_payment("ord-1", "pay-1")
    book.mark_running("ord-1")
    book.mark_delivered("ord-1", "dlv-1")
    book.mark_refunded("ord-1", "ref-1")
    card = revenue_card_from_book(OrderBook(root))
    assert card["counts"][REFUNDED] == 1
    assert card["counts"][DELIVERED] == 0
    assert card["revenue"]["verified_cents"] == 0
    assert card["revenue"]["pending_cents"] == 0


def test_failed_order_is_neither_verified_nor_pending(tmp_path):
    root = tmp_path / "orders"
    book = OrderBook(root)
    book.create_order("ord-1", REPO, _contact())
    book.mark_failed("ord-1", "fail-1")
    card = revenue_card(root)
    assert card["counts"][NEW] == 0
    assert card["counts"][FAILED] == 1
    assert card["revenue"]["verified_cents"] == 0
    assert card["revenue"]["pending_cents"] == 0


def test_corrupt_log_fails_closed(tmp_path):
    root = tmp_path / "orders"
    _seed(root, paid=1, delivered=0)
    with (root / "receipts.jsonl").open("a", encoding="utf-8") as handle:
        handle.write("not json\n")
    with pytest.raises(OrderError):
        revenue_card(root)
