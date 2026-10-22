"""Negative guards for reality orders. No network and no payment capture."""

import pytest

from courier_core.reality_orders import NEW, OrderBook, OrderError

REPO = "zip-upload"
ORDER = "ord-guard"


def _contact():
    return "buyer" + chr(64) + "example.invalid"


def _spy(monkeypatch):
    calls = []

    def boom(spec):
        calls.append(spec)
        raise AssertionError("network fetch is not allowed in this test")

    monkeypatch.setattr("courier_core.reality_orders.fetch_public", boom)
    return calls


def test_unpaid_order_does_not_fetch(tmp_path, monkeypatch):
    calls = _spy(monkeypatch)
    book = OrderBook(tmp_path)
    book.create_order(ORDER, REPO, _contact())
    with pytest.raises(OrderError, match="not paid"):
        book.fulfill(ORDER, tmp_path / "out")
    assert calls == []
    assert book.get(ORDER)["status"] == NEW
    assert book.get(ORDER)["payment_evidence"] is None


def test_non_fulfill_paths_do_not_fetch(tmp_path, monkeypatch):
    calls = _spy(monkeypatch)
    book = OrderBook(tmp_path)
    book.create_order(ORDER, REPO, _contact())
    book.revenue_summary()
    book.orders()
    with pytest.raises(OrderError):
        book.mark_running(ORDER)
    with pytest.raises(OrderError):
        book.mark_delivered(ORDER, "report-1")
    assert calls == []
    assert book.get(ORDER)["status"] == NEW
    assert book.get(ORDER)["payment_evidence"] is None


def test_unknown_cost_blocks_before_network(tmp_path, monkeypatch):
    calls = _spy(monkeypatch)
    book = OrderBook(tmp_path)
    book.create_order(ORDER, REPO, _contact())
    stored = dict(book._orders[ORDER])
    stored["status"] = "PAYMENT_CONFIRMED"
    stored["price_cents"] = None
    book._orders[ORDER] = stored
    with pytest.raises(OrderError, match="UNKNOWN_COST"):
        book.fulfill(ORDER, tmp_path / "out")
    assert calls == []
    with pytest.raises(OrderError, match="UNKNOWN_COST"):
        book.revenue_summary()
    stored["price_cents"] = True
    book._orders[ORDER] = stored
    with pytest.raises(OrderError, match="UNKNOWN_COST"):
        book.revenue_summary()
