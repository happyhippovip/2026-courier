"""Tests for adapters/spreadsheet.py and scripts/spreadsheet_cleanup_sample.py.

Synthetic fixtures only (example.com addresses), no real customer data.
"""
import contextlib
import io
import json
import re
import sys
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from adapters.spreadsheet import SpreadsheetAdapter  # noqa: E402
from courier_runtime.workbook import SHEET, apply, make_fixture, read_cells  # noqa: E402
import spreadsheet_cleanup_sample as sample  # noqa: E402


# ---------------------------------------------------------------- helpers
def _sheet_xml(path):
    with zipfile.ZipFile(path) as z:
        return z.read(SHEET).decode("utf-8")


def _cell_xml(xml, ref):
    m = re.search(r'<c r="%s"[^>]*?(?:/>|>.*?</c>)' % ref, xml)
    assert m, f"cell {ref} not found"
    return m.group(0)


def _run_sample(tmp_path, monkeypatch, capture_before=None):
    """Run the cleanup script in tmp_path; returns (receipt, workbook copy before cleanup removal)."""
    monkeypatch.chdir(tmp_path)
    snapshots = {}
    real_apply = sample.apply

    def spy_apply(path, changes, grant_id):
        snapshots["before_xml"] = _sheet_xml(path)
        snapshots["before_cells"] = read_cells(path)
        snapshots["changes"] = dict(changes)
        receipt = real_apply(path, changes, grant_id)
        snapshots["after_xml"] = _sheet_xml(path)
        snapshots["after_cells"] = read_cells(path)
        return receipt

    monkeypatch.setattr(sample, "apply", spy_apply)
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        sample.main()
    text = out.getvalue()
    start = text.index("Receipt:\n") + len("Receipt:\n")
    end = text.index("\nDone!")
    receipt = json.loads(text[start:end])
    return receipt, snapshots


@pytest.fixture
def run(tmp_path, monkeypatch):
    return _run_sample(tmp_path, monkeypatch)


# ---------------------------------------------------------------- cleanup script
def test_trim_whitespace(run):
    _, s = run
    assert s["after_cells"]["C2"] == "john@example.com"
    assert s["after_cells"]["C3"] == "jane.smith@example.com"
    assert s["after_cells"]["A2"] == "John Doe"


def test_names_title_case(run):
    _, s = run
    assert s["after_cells"]["A2"] == "John Doe"
    assert s["after_cells"]["A3"] == "Jane Smith"
    assert s["after_cells"]["A4"] == "Alice"


def test_phone_normalized_to_plus49(run):
    _, s = run
    assert s["after_cells"]["B2"] == "+491511234567"
    assert s["after_cells"]["B3"] == "+491517654321"
    assert s["after_cells"]["B4"] == "+49151000000"


def test_email_lowercase(tmp_path, monkeypatch):
    # The shipped sample has no uppercase e-mail; feed one in via make_fixture.
    real_make = sample.make_fixture

    def make_upper(path, data):
        data = dict(data)
        data["C4"] = "  Alice.UPPER@Example.COM "
        return real_make(path, data)

    monkeypatch.setattr(sample, "make_fixture", make_upper)
    _, s = _run_sample(tmp_path, monkeypatch)
    assert s["after_cells"]["C4"] == "alice.upper@example.com"


def test_formulas_unchanged_byte_exact(run):
    _, s = run
    for ref in ("D2", "D3"):
        assert ref not in s["changes"]
        assert _cell_xml(s["after_xml"], ref) == _cell_xml(s["before_xml"], ref)
    assert s["after_cells"]["D2"] == "=SUM(1, 2)"
    assert s["after_cells"]["D3"] == "=A3"


def test_untouched_cells_unchanged(run):
    receipt, s = run
    untouched = set(s["before_cells"]) - set(s["changes"])
    assert {"A1", "B1", "C1", "D1", "D4", "C4", "D2", "D3"} <= untouched
    for ref in untouched:
        assert s["after_cells"][ref] == s["before_cells"][ref]
        assert _cell_xml(s["after_xml"], ref) == _cell_xml(s["before_xml"], ref)
    assert receipt["untouched_cells_verified"] == len(untouched)


def test_receipt_per_cell(run):
    receipt, s = run
    cells = {c["cell"]: c for c in receipt["changes"]}
    assert set(cells) == set(s["changes"])
    for ref, entry in cells.items():
        assert entry["before"] == s["before_cells"][ref]
        assert entry["after"] == s["after_cells"][ref]
    assert receipt["grant_id"] == "grant_demo_123"
    assert re.fullmatch(r"[0-9a-f]{64}", receipt["before_sha256"])
    assert receipt["before_sha256"] != receipt["after_sha256"]


def test_sample_removes_its_fixture(run, tmp_path):
    assert not (tmp_path / "messy_sample.xlsx").exists()


def test_workbook_apply_refuses_formula_edit(tmp_path):
    p = make_fixture(str(tmp_path / "f.xlsx"), {"A1": "=1+1"})
    before = (tmp_path / "f.xlsx").read_bytes()
    with pytest.raises(ValueError):
        apply(p, {"A1": "x"}, grant_id="g")
    assert (tmp_path / "f.xlsx").read_bytes() == before


# ---------------------------------------------------------------- adapter
def _adapter(tmp_path, cells):
    return SpreadsheetAdapter(make_fixture(str(tmp_path / "leads.xlsx"), cells))


def test_adapter_parses_and_trims(tmp_path):
    a = _adapter(tmp_path, {"A1": "Name", "B1": "Email",
                            "A2": "  Acme GmbH ", "B2": " info@example.com ",
                            "A3": "Beta AG", "B3": "beta@example.com"})
    leads = a.parse_leads()
    assert [l.organisation for l in leads] == ["Acme GmbH", "Beta AG"]
    assert [l.lead_id for l in leads] == ["L-2", "L-3"]
    assert all(l.source == "spreadsheet_import" for l in leads)


def test_adapter_skips_header_empty_and_invalid_email(tmp_path):
    a = _adapter(tmp_path, {"A1": "Name", "B1": "Email",
                            "A2": "NoAt", "B2": "not-an-email",
                            "A3": "", "B3": "",
                            "A4": "Gamma", "B4": "g@example.com"})
    leads = a.parse_leads(source_name="test")
    assert [l.lead_id for l in leads] == ["L-4"]
    assert leads[0].source == "test"


def test_adapter_does_not_modify_workbook(tmp_path):
    a = _adapter(tmp_path, {"A1": "Name", "B1": "Email", "A2": "X", "B2": "x@example.com", "C2": "=A2"})
    before = Path(a.workbook_path).read_bytes()
    a.parse_leads()
    assert Path(a.workbook_path).read_bytes() == before
