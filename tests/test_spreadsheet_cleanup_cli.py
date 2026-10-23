"""Targeted unit and CLI tests for scripts/spreadsheet_cleanup.py.

Verifies:
1. CSV cleaning: whitespace trimming, phone normalization, email lowercasing, name title casing.
2. Cryptographic SHA-256 before/after verification receipt.
3. Fail-closed strict mode on corrupted CSV schema (exit code 1).
4. XLSX cleaning with formula preservation.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from courier_runtime.workbook import make_fixture, read_cells


def run_cli(*args):
    cmd = [sys.executable, str(ROOT / "scripts" / "spreadsheet_cleanup.py")] + list(args)
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    return res


def test_csv_cleanup_cli_success(tmp_path):
    messy_csv = tmp_path / "messy.csv"
    clean_csv = tmp_path / "clean.csv"
    receipt_file = tmp_path / "receipt.json"

    content = (
        "Name,Telefon,Email,Status\n"
        " john doe ,0151-1234567, John.Doe@Example.com , aktiv \n"
        "JANE SMITH,004915199999,JANE@COMPANY.DE,inaktiv\n"
        "max mustermann,+49 151 888 777,Max@Work.com,aktiv\n"
    )
    messy_csv.write_text(content, encoding="utf-8")

    res = run_cli(
        "--input", str(messy_csv),
        "--output", str(clean_csv),
        "--receipt", str(receipt_file)
    )

    assert res.returncode == 0, f"CLI failed: {res.stderr}"
    assert clean_csv.exists()
    assert receipt_file.exists()

    # Verify cleaned content
    cleaned_text = clean_csv.read_text(encoding="utf-8")
    lines = cleaned_text.strip().split("\n")
    assert lines[0] == "Name,Telefon,Email,Status"
    assert lines[1] == "John Doe,+491511234567,john.doe@example.com,aktiv"
    assert lines[2] == "Jane Smith,+4915199999,jane@company.de,inaktiv"
    assert lines[3] == "Max Mustermann,+49151888777,max@work.com,aktiv"

    # Verify receipt
    receipt = json.loads(receipt_file.read_text(encoding="utf-8"))
    assert receipt["status"] == "PASS"
    assert receipt["format"] == "csv"
    assert receipt["rows_processed"] == 3
    assert receipt["mutated_cells"] > 0
    assert len(receipt["before_sha256"]) == 64
    assert len(receipt["after_sha256"]) == 64
    assert receipt["before_sha256"] != receipt["after_sha256"]
    assert receipt["verification_verified"] is True


def test_csv_strict_fail_closed_on_schema_mismatch(tmp_path):
    corrupt_csv = tmp_path / "corrupt.csv"
    receipt_file = tmp_path / "receipt.json"

    # Row 2 has 2 columns instead of 3
    content = (
        "Name,Telefon,Email\n"
        "Alice,+49151000\n"
        "Bob,0151111,bob@example.com\n"
    )
    corrupt_csv.write_text(content, encoding="utf-8")

    res = run_cli(
        "--input", str(corrupt_csv),
        "--output", str(tmp_path / "out.csv"),
        "--receipt", str(receipt_file),
        "--strict"
    )

    assert res.returncode == 1
    assert "length mismatch" in res.stderr

    receipt = json.loads(receipt_file.read_text(encoding="utf-8"))
    assert receipt["status"] == "FAIL"
    assert receipt["verification_verified"] is False


def test_xlsx_cleanup_cli_success(tmp_path):
    messy_xlsx = tmp_path / "messy.xlsx"
    clean_xlsx = tmp_path / "clean.xlsx"
    receipt_file = tmp_path / "receipt.json"

    data = {
        "A1": "Name", "B1": "Phone", "C1": "Email", "D1": "Formula",
        "A2": " john doe ", "B2": "0151-1234567", "C2": " JOHN@EXAMPLE.COM ", "D2": "=SUM(1, 2)",
        "A3": "JANE SMITH", "B3": "+49 151 7654321", "C3": "jane@example.com", "D3": "=A3"
    }
    make_fixture(str(messy_xlsx), data)

    res = run_cli(
        "--input", str(messy_xlsx),
        "--output", str(clean_xlsx),
        "--receipt", str(receipt_file)
    )

    assert res.returncode == 0, f"CLI failed: {res.stderr}"
    assert clean_xlsx.exists()

    cells = read_cells(str(clean_xlsx))
    assert cells["A2"] == "John Doe"
    assert cells["B2"] == "+491511234567"
    assert cells["C2"] == "john@example.com"
    # Formula carried over byte-exact
    assert cells["D2"] == "=SUM(1, 2)"
    assert cells["D3"] == "=A3"

    receipt = json.loads(receipt_file.read_text(encoding="utf-8"))
    assert receipt["status"] == "PASS"
    assert receipt["format"] == "xlsx"
    assert receipt["mutated_cells"] > 0
    assert receipt["untouched_cells_verified"] >= 2
