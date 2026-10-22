import math
import os
import json
import runpy
from pathlib import Path
from scripts.invoice_generator import InvoiceGenerator

def test_invoice_generator_setup(tmp_path, monkeypatch):
    monkeypatch.setattr(InvoiceGenerator, "INVOICE_DIR", tmp_path / "invoices")
    InvoiceGenerator.setup()
    assert (tmp_path / "invoices").exists()
    assert (tmp_path / "invoices").is_dir()

def test_generate_invoice_defaults(tmp_path, monkeypatch):
    monkeypatch.setattr(InvoiceGenerator, "INVOICE_DIR", tmp_path / "invoices")
    
    doc = InvoiceGenerator.generate_invoice({}, "test@example.com", "John Doe")
    
    assert doc["customer_email"] == "test@example.com"
    assert doc["customer_name"] == "John Doe"
    assert doc["prospect_id"] == "UNKNOWN-PROSPECT"
    assert doc["amount_eur"] == 0.0
    assert doc["opportunity_id"] == "UNKNOWN-OFFERING"
    assert "INV-UNKNOWN-PROSPECT-" in doc["invoice_id"]
    
    out_file = tmp_path / "invoices" / f"{doc['invoice_id']}.json"
    assert out_file.exists()
    with open(out_file, "r") as f:
        saved_doc = json.load(f)
    assert saved_doc == doc

def test_generate_invoice_sequence(tmp_path, monkeypatch):
    monkeypatch.setattr(InvoiceGenerator, "INVOICE_DIR", tmp_path / "invoices")
    
    exp_data = {
        "prospect_alias": "P-TEST-01",
        "price_eur": 500.0,
        "target_offering": "REV-TEST-OFFERING"
    }
    
    doc1 = InvoiceGenerator.generate_invoice(exp_data, "1@example.com", "Test1")
    doc2 = InvoiceGenerator.generate_invoice(exp_data, "2@example.com", "Test2")
    
    assert doc1["invoice_id"].endswith("-01")
    assert doc2["invoice_id"].endswith("-02")
    assert doc1["amount_eur"] == 500.0
    assert doc1["opportunity_id"] == "REV-TEST-OFFERING"

import subprocess
import sys

def test_main_execution(tmp_path):
    # Run the module to cover the __main__ block
    # INVOICE_DIR is CWD-relative: run from tmp_path so no invoice lands in the repo.
    repo_root = str(Path(__file__).resolve().parent.parent)
    env = dict(os.environ, PYTHONPATH=os.pathsep.join([repo_root, os.environ.get("PYTHONPATH", "")]))
    result = subprocess.run([sys.executable, "-m", "scripts.invoice_generator"], capture_output=True, text=True,
                            cwd=str(tmp_path), env=env)
    assert list((tmp_path / "events" / "invoices").glob("*.json")), "invoice should be written under tmp_path"
    assert result.returncode == 0
    assert "Generated Invoice: " in result.stdout


def test_invoice_dir_does_not_follow_a_symlink(tmp_path, monkeypatch):
    outside = tmp_path / "outside-invoices"
    outside.mkdir()
    (outside / "keep.txt").write_text("keep", encoding="utf-8")
    linked = tmp_path / "linked-invoices"
    linked.symlink_to(outside)
    monkeypatch.setattr(InvoiceGenerator, "INVOICE_DIR", linked)
    try:
        InvoiceGenerator.generate_invoice(
            {"prospect_alias": "P-SAFE", "price_eur": 1.0},
            "a@b.c",
            "SECRET-INVOICE",
        )
        err = None
    except ValueError as exc:
        err = str(exc)
    names = sorted(path.name for path in outside.iterdir())
    bodies = [path.read_text(encoding="utf-8") for path in outside.glob("*.json")]
    assert (err, any("SECRET-INVOICE" in body for body in bodies), names) == (
        "refusing to follow a symlink",
        False,
        ["keep.txt"],
    )


def test_text_false_price_is_not_an_amount(tmp_path, monkeypatch):
    monkeypatch.setattr(InvoiceGenerator, "INVOICE_DIR", tmp_path / "invoices")

    def run(price):
        try:
            doc = InvoiceGenerator.generate_invoice(
                {"prospect_alias": "P-PRICE", "price_eur": price},
                "a@b.c",
                "Name",
            )
        except ValueError as exc:
            return ("raised", str(exc), None)
        saved = json.loads((tmp_path / "invoices" / f"{doc['invoice_id']}.json").read_text(encoding="utf-8"))
        return ("wrote", doc["amount_eur"], saved["amount_eur"])

    text_false = run("false")
    text_zero = run("0")
    bool_true = run(True)
    bool_false = run(False)
    nan = run(float("nan"))
    finite = run(500.0)
    assert (
        text_false[0],
        text_false[1],
        text_false[2],
        text_zero[0],
        text_zero[1],
        text_zero[2],
        bool_true[0],
        bool_true[1],
        bool_true[2],
        bool_false[0],
        bool_false[1],
        bool_false[2],
        nan[0],
        nan[1],
        isinstance(nan[2], float) and math.isnan(nan[2]),
        finite[0],
        finite[1],
        finite[2],
    ) == (
        "raised",
        "price is not a number.",
        None,
        "raised",
        "price is not a number.",
        None,
        "raised",
        "price is not a number.",
        None,
        "raised",
        "price is not a number.",
        None,
        "raised",
        "price is not a number.",
        False,
        "wrote",
        500.0,
        500.0,
    )
