"""One-command fulfillment. The GitHub fetch is mocked so the tests stay offline."""

import hashlib
import json
from pathlib import Path

from courier_core.reality_orders import FETCH_FAIL_REASON, REFUND_TEMPLATE, main
from courier_core.repo_reality_fetch import FetchError, FetchedRepo

URL = "https://github.com/example/repo"
SHA = "a" * 40
TARBALL = "b" * 64
MARKER = "Nur lesende Prüfung eines öffentlichen GitHub-Tarballs"


def _contact():
    return "buyer" + chr(64) + "example.invalid"


def _run(data, *args):
    return main(["--data-dir", str(data), *args])


def _text(directory):
    parts = []
    for path in sorted(Path(directory).rglob("*")):
        if path.is_file():
            parts.append(path.read_text(encoding="utf-8"))
    return "\n".join(parts)


def _orders(data):
    return json.loads((Path(data) / "orders.json").read_text(encoding="utf-8"))["orders"]


def _receipt_count(data):
    return (Path(data) / "receipts.jsonl").read_text(encoding="utf-8").count("\n")


def _paid(data, capsys):
    assert _run(data, "new", "--repo", URL, "--contact", _contact()) == 0
    order_id = capsys.readouterr().out.strip()
    assert _run(data, "confirm-payment", order_id, "--evidence", "paypal-TXN-1") == 0
    capsys.readouterr()
    return order_id


def _install_fetch(monkeypatch, tmp_path, calls):
    source = tmp_path / "source"
    source.mkdir()
    (source / "README.md").write_text("hello\n", encoding="utf-8")
    scratch = tmp_path / "fetch-scratch"
    scratch.mkdir()

    def fake_fetch(spec):
        calls.append(spec)
        return FetchedRepo(
            root=source,
            temp_dir=scratch,
            owner="example",
            repo="repo",
            ref="heads/main",
            sha=SHA,
            tarball_sha256=TARBALL,
        )

    monkeypatch.setattr("courier_core.reality_orders.fetch_public", fake_fetch)
    return scratch


def test_fulfill_refuses_an_unpaid_order(tmp_path, capsys, monkeypatch):
    calls = []
    _install_fetch(monkeypatch, tmp_path, calls)
    data = tmp_path / "orders"
    out = tmp_path / "out"
    assert _run(data, "new", "--repo", URL, "--contact", _contact()) == 0
    order_id = capsys.readouterr().out.strip()
    before = _receipt_count(data)
    assert _run(data, "fulfill", order_id, "--out-dir", str(out)) == 2
    assert "not paid" in capsys.readouterr().err
    assert calls == []
    assert _receipt_count(data) == before
    assert _orders(data)[order_id]["status"] == "NEW"
    assert not (out / f"{order_id}-report.md").exists()
    assert "@" not in _text(data)


def test_fulfill_prepares_a_report_and_confirm_sent_delivers(tmp_path, capsys, monkeypatch):
    calls = []
    _install_fetch(monkeypatch, tmp_path, calls)
    data = tmp_path / "orders"
    out = tmp_path / "out"
    order_id = _paid(data, capsys)
    report = out / f"{order_id}-report.md"

    before_confirm = _receipt_count(data)
    assert _run(data, "deliver", order_id, "--confirm-sent") == 2
    assert "not been prepared" in capsys.readouterr().err
    assert _receipt_count(data) == before_confirm
    assert _orders(data)[order_id]["status"] == "PAYMENT_CONFIRMED"

    assert _run(data, "fulfill", order_id, "--out-dir", str(out)) == 0
    printed = capsys.readouterr().out
    assert f"{order_id} RUNNING" in printed
    assert str(report) in printed
    assert calls == ["example/repo"]
    assert report.is_file()
    assert MARKER in report.read_text(encoding="utf-8")
    body = report.read_bytes()
    digest = hashlib.sha256(body).hexdigest()
    record = _orders(data)[order_id]
    assert record["status"] == "RUNNING"
    assert record["delivery_evidence"] is None
    evidence = record["ready_evidence"]
    assert evidence == f"sha256:{digest};bytes:{len(body)};commit:{SHA};tarball:{TARBALL}"
    assert MARKER not in _text(data)
    assert _contact() not in _text(data)
    assert "@" not in _text(data)

    assert _run(data, "revenue") == 0
    pending = capsys.readouterr().out
    assert "verified 0.00 EUR (0)" in pending
    assert "pending 5.00 EUR (1)" in pending

    first = report.read_bytes()
    assert _run(data, "fulfill", order_id, "--out-dir", str(out)) == 0
    capsys.readouterr()
    assert calls == ["example/repo"]
    assert report.read_bytes() == first
    assert _orders(data)[order_id]["status"] == "RUNNING"
    assert _orders(data)[order_id]["ready_evidence"] == evidence

    assert _run(data, "deliver", order_id, "--confirm-sent") == 0
    assert "DELIVERED" in capsys.readouterr().out
    delivered = _orders(data)[order_id]
    assert delivered["status"] == "DELIVERED"
    assert delivered["delivery_evidence"] == evidence
    assert _run(data, "revenue") == 0
    verified = capsys.readouterr().out
    assert "verified 5.00 EUR (1)" in verified
    assert "pending 0.00 EUR (0)" in verified

    assert _run(data, "fulfill", order_id, "--out-dir", str(out)) == 2
    capsys.readouterr()
    assert calls == ["example/repo"]
    assert report.read_bytes() == first
    assert _orders(data)[order_id]["status"] == "DELIVERED"


def test_fulfill_marks_failed_when_the_repository_cannot_be_fetched(tmp_path, capsys, monkeypatch):
    def explode(spec):
        raise FetchError("missing")

    monkeypatch.setattr("courier_core.reality_orders.fetch_public", explode)
    data = tmp_path / "orders"
    out = tmp_path / "out"
    order_id = _paid(data, capsys)
    assert _run(data, "fulfill", order_id, "--out-dir", str(out)) == 2
    captured = capsys.readouterr()
    assert str(REFUND_TEMPLATE) in captured.out
    assert FETCH_FAIL_REASON in captured.err
    record = _orders(data)[order_id]
    assert record["status"] == "FAILED"
    assert record["failure_evidence"] == FETCH_FAIL_REASON
    assert not (out / f"{order_id}-report.md").exists()
    assert "@" not in _text(data)
    assert _run(data, "revenue") == 0
    summary = capsys.readouterr().out
    assert "verified 0.00 EUR (0)" in summary
    assert "pending 0.00 EUR (0)" in summary


def test_started_order_reuses_an_existing_report_without_fetching(tmp_path, capsys, monkeypatch):
    calls = []
    _install_fetch(monkeypatch, tmp_path, calls)
    data = tmp_path / "orders"
    out = tmp_path / "out"
    order_id = _paid(data, capsys)
    assert _run(data, "start", order_id) == 0
    capsys.readouterr()
    report = out / f"{order_id}-report.md"
    out.mkdir()
    report.write_text(
        "# Repo Reality Check\n\n- Commit: " + SHA + "\n- Tarball sha256: " + TARBALL + "\n",
        encoding="utf-8",
    )
    original = report.read_bytes()
    assert _run(data, "fulfill", order_id, "--out-dir", str(out)) == 0
    assert "RUNNING" in capsys.readouterr().out
    assert calls == []
    assert report.read_bytes() == original
    evidence = _orders(data)[order_id]["ready_evidence"]
    digest = hashlib.sha256(original).hexdigest()
    assert evidence == f"sha256:{digest};bytes:{len(original)};commit:{SHA};tarball:{TARBALL}"
