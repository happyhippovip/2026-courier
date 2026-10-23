"""Negative guards for reality orders. No network and no payment capture."""

import pytest

from courier_core.reality_orders import NEW, OrderBook, OrderError, resolve_orders_dir

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


def test_fulfill_refuses_a_symlinked_report_file(tmp_path, monkeypatch):
    calls = _spy(monkeypatch)
    book = OrderBook(tmp_path / "book")
    book.create_order(ORDER, REPO, _contact())
    stored = dict(book._orders[ORDER])
    stored["status"] = "PAYMENT_CONFIRMED"
    book._orders[ORDER] = stored
    outside = tmp_path / "secret.md"
    outside.write_text("keep", encoding="utf-8")
    out = tmp_path / "out"
    out.mkdir()
    report = out / f"{ORDER}-report.md"
    report.symlink_to(outside)
    with pytest.raises(OrderError, match="symlink"):
        book.fulfill(ORDER, out)
    assert calls == []
    assert outside.read_text(encoding="utf-8") == "keep"
    assert book.get(ORDER).get("ready_evidence") is None
    assert book.get(ORDER)["status"] == "PAYMENT_CONFIRMED"


def test_fulfill_refuses_a_symlinked_out_dir(tmp_path, monkeypatch):
    calls = _spy(monkeypatch)
    book = OrderBook(tmp_path / "book")
    book.create_order(ORDER, REPO, _contact())
    stored = dict(book._orders[ORDER])
    stored["status"] = "PAYMENT_CONFIRMED"
    book._orders[ORDER] = stored
    outside = tmp_path / "outside"
    outside.mkdir()
    link = tmp_path / "out"
    link.symlink_to(outside, target_is_directory=True)
    with pytest.raises(OrderError, match="symlink"):
        book.fulfill(ORDER, link)
    assert calls == []
    assert list(outside.iterdir()) == []
    assert book.get(ORDER)["status"] == "PAYMENT_CONFIRMED"


def test_resolve_orders_dir_refuses_a_symlinked_home(tmp_path, monkeypatch):
    outside = tmp_path / "outside"
    outside.mkdir()
    link = tmp_path / "home"
    link.symlink_to(outside, target_is_directory=True)
    monkeypatch.setenv("COURIER_HOME", str(link))
    monkeypatch.delenv("COURIER_ORDERS_DIR", raising=False)
    try:
        OrderBook(resolve_orders_dir()).create_order(ORDER, REPO, _contact())
    except OrderError as exc:
        assert "symlink" in str(exc)
    else:
        raise AssertionError(sorted(path.relative_to(outside).as_posix() for path in outside.rglob("*")))
    assert list(outside.iterdir()) == []


def test_order_book_refuses_a_symlinked_directory(tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    link = tmp_path / "orders"
    link.symlink_to(outside, target_is_directory=True)
    try:
        book = OrderBook(link)
        book.create_order(ORDER, REPO, _contact())
    except OrderError as exc:
        assert "symlink" in str(exc)
    else:
        raise AssertionError(f"wrote through a symlink: {sorted(p.name for p in outside.iterdir())}")
    assert list(outside.iterdir()) == []
    with pytest.raises(OrderError, match="symlink"):
        resolve_orders_dir(str(link))


def test_order_book_does_not_read_a_symlinked_receipt_log(tmp_path):
    outside = tmp_path / "foreign.jsonl"
    outside.write_text('{"adopted": true}\n', encoding="utf-8")
    root = tmp_path / "book"
    root.mkdir()
    (root / "receipts.jsonl").symlink_to(outside)
    try:
        OrderBook(root)
    except OrderError as exc:
        assert "symlink" in str(exc).lower(), str(exc)
    else:
        raise AssertionError("loaded a symlinked receipt log")
    assert outside.read_text(encoding="utf-8") == '{"adopted": true}\n'


def test_order_book_does_not_replace_a_symlinked_projection(tmp_path):
    outside = tmp_path / "foreign-orders.json"
    body = '{"head_seq": 99, "head_hash": "abc", "orders": {"foreign": {}}}\n'
    outside.write_text(body, encoding="utf-8")
    root = tmp_path / "book"
    root.mkdir()
    link = root / "orders.json"
    link.symlink_to(outside)
    try:
        OrderBook(root)
    except OrderError as exc:
        assert "symlink" in str(exc).lower(), str(exc)
    else:
        raise AssertionError(
            f"symlink={link.is_symlink()} local={link.read_text(encoding='utf-8')[:80]!r}"
        )
    assert link.is_symlink()
    assert outside.read_text(encoding="utf-8") == body
