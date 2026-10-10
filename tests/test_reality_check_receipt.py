import json
import os
from pathlib import Path
import pytest
from scripts.reality_check_receipt import (
    ReceiptError,
    compute_proof_signature,
    compute_reality_score,
    create_proof_card,
    main,
    render_markdown_card,
    verify_proof_card,
)


@pytest.fixture
def sample_report_data():
    findings = [
        {"area": "secrets", "severity": "high", "rule": "credential_in_code", "where": "app.py:12", "detail": "API key"},
        {"area": "hygiene", "severity": "medium", "rule": "missing_docstring", "where": "core.py:4", "detail": "No docs"},
        {"area": "hygiene", "severity": "medium", "rule": "trailing_whitespace", "where": "util.py:8", "detail": "Whitespace"},
        {"area": "supply", "severity": "low", "rule": "unpinned_dep", "where": "req.txt:1", "detail": "Unpinned"},
    ]
    return {
        "repository": "courier-test-repo",
        "sha": "a1b2c3d4e5f67890123456789abcdef012345678",
        "tool": "0.1.0",
        "files_scanned": 42,
        "findings": findings,
        "summary": {"high": 1, "medium": 2, "low": 1},
        "digest": "d41d8cd98f00b204e9800998ecf8427e00000000000000000000000000000000",
    }


@pytest.fixture
def report_dir(tmp_path, sample_report_data):
    report_file = tmp_path / "report.json"
    report_file.write_text(json.dumps(sample_report_data, indent=2), encoding="utf-8")
    return tmp_path


def test_score_calculation():
    # 1 high (15), 2 medium (10), 1 low (1) -> 100 - 26 = 74
    assert compute_reality_score(1, 2, 1) == 74
    # All clean -> 100
    assert compute_reality_score(0, 0, 0) == 100
    # Overwhelming penalties floor at 0
    assert compute_reality_score(10, 10, 10) == 0


def test_make_proof_card_from_valid_report(report_dir, sample_report_data):
    card = create_proof_card(report_dir, order_id="ord-test-123")
    assert card["goal"] == "repo-reality-check"
    assert card["order_id"] == "ord-test-123"
    assert card["repository"] == "courier-test-repo"
    assert card["commit_sha"] == sample_report_data["sha"]
    assert card["files_scanned"] == 42
    assert card["score"] == 74
    assert card["clean_verdict"] is False  # has 1 high risk
    assert len(card["proof_signature"]) == 64
    assert len(card["report_sha256"]) == 64
    assert card["report_bytes"] > 0
    # Signature matches payload
    assert compute_proof_signature(card) == card["proof_signature"]


def test_make_clean_verdict_when_no_high_findings(tmp_path):
    clean_data = {
        "repository": "safe-repo",
        "sha": "1234567890abcdef1234567890abcdef12345678",
        "tool": "0.1.0",
        "files_scanned": 10,
        "findings": [],
        "summary": {"high": 0, "medium": 1, "low": 2},
        "digest": "abcde12345",
    }
    report_file = tmp_path / "report.json"
    report_file.write_text(json.dumps(clean_data), encoding="utf-8")

    card = create_proof_card(report_file)
    assert card["clean_verdict"] is True
    assert card["score"] == 93  # 100 - 5 - 2


def test_verify_success_unaltered(report_dir, tmp_path):
    card = create_proof_card(report_dir)
    receipt_file = tmp_path / "receipt.json"
    receipt_file.write_text(json.dumps(card, indent=2), encoding="utf-8")

    res = verify_proof_card(receipt_file, report_dir)
    assert res["ok"] is True
    assert res["receipt_id"] == card["receipt_id"]
    assert res["score"] == 74
    assert res["commit_sha"] == card["commit_sha"]


def test_verify_tamper_receipt_signature_fails(report_dir, tmp_path):
    card = create_proof_card(report_dir)
    # Tamper with score inside receipt
    card["score"] = 99
    receipt_file = tmp_path / "tampered_receipt.json"
    receipt_file.write_text(json.dumps(card), encoding="utf-8")

    with pytest.raises(ReceiptError, match="proof_signature mismatch"):
        verify_proof_card(receipt_file, report_dir)


def test_verify_tamper_report_file_fails(report_dir, tmp_path):
    card = create_proof_card(report_dir)
    receipt_file = tmp_path / "receipt.json"
    receipt_file.write_text(json.dumps(card), encoding="utf-8")

    # Alter report.json on disk
    report_file = report_dir / "report.json"
    altered = json.loads(report_file.read_text(encoding="utf-8"))
    altered["files_scanned"] = 999
    report_file.write_text(json.dumps(altered), encoding="utf-8")

    with pytest.raises(ReceiptError, match="report_sha256 mismatch"):
        verify_proof_card(receipt_file, report_dir)


def test_verify_tamper_commit_sha_fails(report_dir, tmp_path):
    card = create_proof_card(report_dir)
    # Alter commit SHA in receipt and recompute signature
    card["commit_sha"] = "0000000000000000000000000000000000000000"
    card["proof_signature"] = compute_proof_signature(card)

    receipt_file = tmp_path / "receipt.json"
    receipt_file.write_text(json.dumps(card), encoding="utf-8")

    with pytest.raises(ReceiptError, match="commit_sha mismatch"):
        verify_proof_card(receipt_file, report_dir)


def test_missing_report_fails(tmp_path):
    with pytest.raises(ReceiptError, match="report file not found"):
        create_proof_card(tmp_path / "nonexistent_dir")

    # Directory exists but lacks report.json
    empty_dir = tmp_path / "empty_dir"
    empty_dir.mkdir()
    with pytest.raises(ReceiptError, match="report.json not found in directory"):
        create_proof_card(empty_dir)


def test_render_markdown_card(report_dir):
    card = create_proof_card(report_dir)
    rendered = render_markdown_card(card)
    assert "REPO REALITY CHECK PROOF CARD" in rendered
    assert card["receipt_id"] in rendered
    assert "Reality Score: 74/100" in rendered


def test_cli_roundtrip(report_dir, tmp_path, capsys):
    report_file = report_dir / "report.json"
    receipt_file = tmp_path / "cli_receipt.json"

    # 1. make
    ret = main(["make", str(report_file), "--out", str(receipt_file), "--order-id", "ord-99"])
    assert ret == 0
    assert receipt_file.is_file()

    # 2. verify
    ret = main(["verify", str(receipt_file), str(report_file)])
    assert ret == 0
    captured = capsys.readouterr()
    assert "VERIFIED: Proof Card matches report" in captured.out

    # 3. card
    ret = main(["card", str(receipt_file)])
    assert ret == 0

    # 4. tamper report -> verify exits 2
    report_file.write_text('{"tampered": true}', encoding="utf-8")
    ret = main(["verify", str(receipt_file), str(report_file)])
    assert ret == 2
