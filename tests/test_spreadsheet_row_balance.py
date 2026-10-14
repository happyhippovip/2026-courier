"""Row balance for adapters/spreadsheet.py (AUF-20261014-04). Synthetic data only."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from adapters.spreadsheet import (  # noqa: E402
    DUPLICATE_EMAIL, EMPTY_ROW, INVALID_EMAIL, SpreadsheetAdapter, split_ref)
from courier_runtime.workbook import make_fixture  # noqa: E402

UMLAUT_NAMES = ["Müller GmbH", "Bäckerei Größe", "Öko Löwe AG", "Straße & Söhne", "Jürgen Ü."]


def synthetic_cells():
    """Deterministic 50 data rows (rows 2..51): 39 valid, 5 duplicates, 4 broken e-mails,
    2 empty rows. Column AB carries a note on every non-empty row."""
    cells = {"A1": "Name", "B1": "Email", "AB1": "Notiz"}
    plan = (["ok"] * 39) + ["dup"] * 5 + ["bad"] * 4 + ["empty"] * 2
    # deterministic interleave
    order = sorted(range(50), key=lambda i: (i * 37) % 50)
    kinds = [plan[i] for i in order]
    ok_n = 0
    for i, kind in enumerate(kinds):
        r = i + 2
        if kind == "empty":
            cells[f"A{r}"], cells[f"B{r}"] = "  ", ""
            continue
        if kind == "ok":
            ok_n += 1
            name = UMLAUT_NAMES[ok_n % 5] + f" {ok_n}"
            email = f"kontakt{ok_n}@example.com"
        elif kind == "dup":
            name, email = "Duplikat Ä", f"KONTAKT{1 + (i % 3)}@Example.com"
        else:
            name, email = "Kaputt Ö", f"kaputt{i}.example.com"
        cells[f"A{r}"], cells[f"B{r}"], cells[f"AB{r}"] = name, email, f"Notiz ü {r}"
    return cells, kinds


def _adapter(tmp_path, name="leads.xlsx"):
    cells, kinds = synthetic_cells()
    return SpreadsheetAdapter(make_fixture(str(tmp_path / name), cells)), kinds


def test_split_ref_handles_multi_letter_columns():
    assert split_ref("A5") == ("A", 5)
    assert split_ref("AA5") == ("AA", 5)
    assert split_ref("AB123") == ("AB", 123)
    assert split_ref("a5") is None and split_ref("5A") is None and split_ref("AA0") is None


def test_dup_rows_point_to_earlier_rows(tmp_path):
    # duplicates must refer to an e-mail that appeared earlier, so check the plan is sound
    adapter, kinds = _adapter(tmp_path)
    _, balance = adapter.parse_leads_with_balance()
    for entry in balance["rejected"]:
        if entry["reason"] == DUPLICATE_EMAIL:
            assert int(entry["duplicate_of"][2:]) < entry["row"]


def test_balance_explains_every_row(tmp_path):
    adapter, kinds = _adapter(tmp_path)
    leads, balance = adapter.parse_leads_with_balance()
    assert balance["rows_in"] == 50
    assert balance["unexplained"] == 0
    assert len(balance["accepted"]) + len(balance["rejected"]) == 50
    reasons = [e["reason"] for e in balance["rejected"]]
    assert reasons.count(EMPTY_ROW) == 2
    assert reasons.count(INVALID_EMAIL) == 4
    assert reasons.count(DUPLICATE_EMAIL) == 5
    assert len(leads) == len(balance["accepted"]) == 39
    assert balance["unparsed_refs"] == []
    rows = sorted([e["row"] for e in balance["accepted"]] + [e["row"] for e in balance["rejected"]])
    assert rows == list(range(2, 52))


def test_original_content_kept_including_ab_and_umlauts(tmp_path):
    adapter, _ = _adapter(tmp_path)
    _, balance = adapter.parse_leads_with_balance()
    every = balance["accepted"] + balance["rejected"]
    non_empty = [e for e in every if e.get("reason") != EMPTY_ROW]
    assert all(e["original"]["AB"] == f"Notiz ü {e['row']}" for e in non_empty)
    names = {e["original"]["A"] for e in balance["accepted"]}
    assert any("Müller" in n for n in names) and any("Größe" in n for n in names)
    bad = [e for e in balance["rejected"] if e["reason"] == INVALID_EMAIL]
    assert all("@" not in e["original"]["B"] for e in bad)


def test_identical_hash_on_repeat(tmp_path):
    a1, _ = _adapter(tmp_path, "one.xlsx")
    a2, _ = _adapter(tmp_path, "two.xlsx")
    _, b1 = a1.parse_leads_with_balance()
    _, b1_again = a1.parse_leads_with_balance()
    _, b2 = a2.parse_leads_with_balance()
    assert b1["sha256"] == b1_again["sha256"] == b2["sha256"]
    assert len(b1["sha256"]) == 64


def test_parse_leads_shape_unchanged(tmp_path):
    adapter, _ = _adapter(tmp_path)
    leads = adapter.parse_leads()
    # legacy behaviour: drops empty and invalid rows, keeps duplicates
    assert len(leads) == 39 + 5
    assert all(l.lead_id.startswith("L-") and l.source == "spreadsheet_import" for l in leads)


def test_row_with_only_column_ab_is_explained(tmp_path):
    p = make_fixture(str(tmp_path / "ab.xlsx"), {"A1": "Name", "B1": "Email", "AB2": "nur Notiz"})
    leads, balance = SpreadsheetAdapter(p).parse_leads_with_balance()
    assert leads == [] and balance["unexplained"] == 0
    assert balance["rejected"] == [{"row": 2, "reason": "no_name_or_email", "original": {"AB": "nur Notiz"}}]
