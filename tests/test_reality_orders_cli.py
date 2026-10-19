"""Founder CLI for Repo Reality Check orders. The book stays outside any checkout."""

import hashlib
import json
from pathlib import Path

from courier_core.reality_orders import main

REPO = Path(__file__).resolve().parents[1]
URL = "https://github.com/example/repo"


def _contact():
    return "buyer" + chr(64) + "example.invalid"


def _run(tmp_path, *args):
    return main(["--data-dir", str(tmp_path), *args])


def _text(tmp_path):
    parts = []
    for path in sorted(tmp_path.rglob("*")):
        if path.is_file():
            parts.append(path.read_text(encoding="utf-8"))
    return "\n".join(parts)


def test_new_prints_order_id_and_rejects_non_github_urls(tmp_path, capsys):
    assert _run(tmp_path, "new", "--repo", URL, "--contact", _contact()) == 0
    order_id = capsys.readouterr().out.strip()
    assert order_id.startswith("ord-")
    assert _contact() not in _text(tmp_path)
    assert "@" not in _text(tmp_path)

    before = _text(tmp_path)
    for repo in (
        "https://gitlab.com/example/repo",
        "https://github.com/example/repo/tree/main",
        "http://github.com/example/repo",
        "https://www.github.com/example/repo",
        "zip-upload",
        "https://github.com/example/repo?ref=1",
    ):
        assert _run(tmp_path, "new", "--repo", repo, "--contact", _contact()) == 2
        capsys.readouterr()
    assert _text(tmp_path) == before

    assert _run(tmp_path, "new", "--repo", "https://github.com/example/repo.git", "--contact", _contact()) == 0
    second = capsys.readouterr().out.strip()
    listed = _run(tmp_path, "list")
    assert listed == 0
    listing = capsys.readouterr().out
    assert f"{order_id} NEW https://github.com/example/repo 5.00 EUR" in listing
    assert f"{second} NEW https://github.com/example/repo 5.00 EUR" in listing


def test_refuses_a_data_dir_inside_a_git_checkout(tmp_path, capsys):
    inside_repo = REPO / "reality-orders-data"
    assert _run(inside_repo, "list") == 2
    assert "git checkout" in capsys.readouterr().err
    assert not inside_repo.exists()

    checkout = tmp_path / "checkout"
    (checkout / ".git").mkdir(parents=True)
    nested = checkout / "orders"
    assert main(["--data-dir", str(nested), "list"]) == 2
    assert not nested.exists()
    capsys.readouterr()


def test_env_dirs_and_revenue_output(tmp_path, capsys, monkeypatch):
    state = tmp_path / "state"
    monkeypatch.setenv("COURIER_HOME", str(state))
    monkeypatch.delenv("COURIER_ORDERS_DIR", raising=False)
    assert main(["new", "--repo", URL, "--contact", _contact()]) == 0
    order_id = capsys.readouterr().out.strip()
    orders = state / "reality-orders"
    assert (orders / "receipts.jsonl").is_file()
    assert not _inside(orders, REPO)

    custom = tmp_path / "custom"
    monkeypatch.setenv("COURIER_ORDERS_DIR", str(custom))
    assert main(["new", "--repo", URL, "--contact", _contact()]) == 0
    capsys.readouterr()
    assert (custom / "receipts.jsonl").is_file()
    assert (orders / "receipts.jsonl").read_text(encoding="utf-8").count("\n") >= 1

    explicit = tmp_path / "explicit"
    report = tmp_path / "report.md"
    marker = "REPORT-BODY-MARKER"
    report.write_text("# Bericht\n" + marker + "\n", encoding="utf-8")
    assert main(["--data-dir", str(explicit), "new", "--repo", URL, "--contact", _contact()]) == 0
    explicit_id = capsys.readouterr().out.strip()
    evidence = "paypal-TXN-100"
    assert main(["--data-dir", str(explicit), "confirm-payment", explicit_id, "--evidence", evidence]) == 0
    capsys.readouterr()
    assert main(["--data-dir", str(explicit), "revenue"]) == 0
    pending = capsys.readouterr().out
    assert "verified 0.00 EUR (0)" in pending
    assert "pending 5.00 EUR (1)" in pending
    assert main(["--data-dir", str(explicit), "start", explicit_id]) == 0
    capsys.readouterr()
    assert main(["--data-dir", str(explicit), "deliver", explicit_id, "--report", str(report)]) == 0
    capsys.readouterr()
    assert main(["--data-dir", str(explicit), "revenue"]) == 0
    verified = capsys.readouterr().out
    assert "verified 5.00 EUR (1)" in verified
    assert "pending 0.00 EUR (0)" in verified
    stored = _text(explicit)
    digest = hashlib.sha256(report.read_bytes()).hexdigest()
    assert f"sha256:{digest}" in stored
    assert f"bytes:{report.stat().st_size}" in stored
    assert marker not in stored
    assert evidence in stored
    assert _contact() not in stored
    record = json.loads((explicit / "orders.json").read_text(encoding="utf-8"))
    assert record["orders"][explicit_id]["delivery_evidence"].startswith("sha256:")
    assert order_id not in stored


def test_refund_and_fail_store_the_reason(tmp_path, capsys):
    assert _run(tmp_path, "new", "--repo", URL, "--contact", _contact()) == 0
    order_id = capsys.readouterr().out.strip()
    assert _run(tmp_path, "confirm-payment", order_id, "--evidence", "stripe-ch-1") == 0
    capsys.readouterr()
    assert _run(tmp_path, "refund", order_id, "--reason", "storniert vor Lieferung") == 0
    assert "REFUNDED" in capsys.readouterr().out
    assert "storniert vor Lieferung" in _text(tmp_path)
    assert _run(tmp_path, "revenue") == 0
    assert "verified 0.00 EUR (0)" in capsys.readouterr().out

    assert _run(tmp_path, "new", "--repo", URL, "--contact", _contact()) == 0
    other = capsys.readouterr().out.strip()
    assert _run(tmp_path, "start", other) == 2
    capsys.readouterr()
    assert _run(tmp_path, "confirm-payment", other, "--evidence", "stripe-ch-2") == 0
    capsys.readouterr()
    assert _run(tmp_path, "fail", other, "--reason", "Repository nicht erreichbar") == 0
    assert "FAILED" in capsys.readouterr().out
    assert "@" not in _text(tmp_path)


def _inside(path, root):
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError:
        return False
    return True


def test_new_test_order_is_listed_and_kept_out_of_revenue(tmp_path, capsys):
    assert _run(tmp_path, "new", "--repo", URL, "--contact", _contact(), "--test") == 0
    probe = capsys.readouterr().out.strip()
    assert _run(tmp_path, "new", "--repo", URL, "--contact", _contact()) == 0
    real = capsys.readouterr().out.strip()
    assert _run(tmp_path, "confirm-payment", probe, "--evidence", "TEST-TXN-0000") == 0
    assert _run(tmp_path, "confirm-payment", real, "--evidence", "pay-1") == 0
    capsys.readouterr()

    assert _run(tmp_path, "list") == 0
    lines = capsys.readouterr().out.splitlines()
    assert any(line.startswith(probe + " ") and line.endswith(" TEST") for line in lines)
    assert any(line.startswith(real + " ") and not line.endswith(" TEST") for line in lines)

    assert _run(tmp_path, "revenue") == 0
    assert capsys.readouterr().out.splitlines() == [
        "verified 0.00 EUR (0)",
        "pending 5.00 EUR (1)",
        "test orders, not revenue (1)",
    ]


def test_new_rejects_zip_and_non_github_with_bilingual_message(tmp_path, capsys):
    for repo in ("zip-upload", "repo.zip", "https://example.com/repo.zip",
                 "https://gitlab.com/example/repo", "git@github.com:example/repo.git"):
        assert _run(tmp_path, "new", "--repo", repo, "--contact", _contact()) == 2
        err = capsys.readouterr().err
        assert "Beta nimmt nur öffentliche GitHub-Links an" in err
        assert "public GitHub links only" in err
    assert not (tmp_path / "receipts.jsonl").exists()


def test_confirm_payment_evidence_must_be_a_short_txn_id(tmp_path, capsys):
    assert _run(tmp_path, "new", "--repo", URL, "--contact", _contact()) == 0
    order_id = capsys.readouterr().out.strip()
    for bad in ("", "   ", "paid by paypal", "txn\t1", "x" * 101):
        assert _run(tmp_path, "confirm-payment", order_id, "--evidence", bad) == 2
        assert "Zahlungsbeleg" in capsys.readouterr().err
    assert _run(tmp_path, "list") == 0
    assert " NEW " in capsys.readouterr().out
    assert _run(tmp_path, "confirm-payment", order_id, "--evidence", "x" * 100) == 0
    assert capsys.readouterr().out.strip() == order_id + " PAYMENT_CONFIRMED"
