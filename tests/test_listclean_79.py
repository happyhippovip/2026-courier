"""Synthetic checks for the 39 EUR list cleaner. No customer data."""

from __future__ import annotations

import ast
import csv
import io
import json
import socket
from pathlib import Path

import pytest

from courier_listclean.clean import MAX_ROWS, ListCleanError, clean_table
from courier_listclean.cli import clean_file, main
from courier_listclean.io_tables import read_table, write_table

EXAMPLE_1 = (
    "Name,Telefon,E-Mail\n"
    '" mÜLLER, hans ",0171/123 45 67, Hans.Mueller@Beispiel.DE\n'
    "Hans Müller,+49171 1234567,hans.mueller@beispiel.de\n"
    "ERIKA MUSTERFRAU,(030) 1234-567,erika@example.com\n"
)

EXAMPLE_2 = (
    "Name,Straße,PLZ,Ort\n"
    "peter beispiel,Musterstr.12,1234,musterstadt\n"
    "Anna Probe,Hauptstraße  5a,D-12345,Musterstadt\n"
    "Lena Test,Bahnhofsstrasse 7,12345,MUSTERSTADT\n"
)

EXAMPLE_3 = (
    "Name,E-Mail\n"
    'Tom Demo,"tom.demo@beispiel,de"\n'
    "Sara Muster,sara.muster@@example.com\n"
    "Jan Probe,JAN.PROBE@EXAMPLE.COM  \n"
    "Mia Test,mia.test(at)beispiel.de\n"
)


def _clean_csv(tmp_path: Path, text: str, name: str = "liste.csv") -> tuple[list[list[str]], dict]:
    source = tmp_path / name
    source.write_bytes(text.encode("utf-8"))
    raw = source.read_bytes()
    written = clean_file(source)
    assert source.read_bytes() == raw
    table = read_table(Path(written["output"]), max_rows=MAX_ROWS)
    report = json.loads(Path(written["report_json"]).read_text(encoding="utf-8"))
    return table.rows, report


def _has(report: dict, row: int, column: str, reason: str, before: str | None = None, after: str | None = None) -> bool:
    for item in report["findings"]:
        if item["row"] == row and item["column"] == column and item["reason"] == reason:
            if before is not None and item["before"] != before:
                continue
            if after is not None and item["after"] != after:
                continue
            return True
    return False


def test_report_does_not_include_a_price(tmp_path: Path):
    source = tmp_path / "liste.csv"
    source.write_bytes(EXAMPLE_1.encode("utf-8"))
    written = clean_file(source)
    report = json.loads(Path(written["report_json"]).read_text(encoding="utf-8"))
    report_csv = Path(written["report_csv"]).read_text(encoding="utf-8-sig")
    assert "offer" not in report
    blob = json.dumps(report, ensure_ascii=False)
    assert "EUR" not in blob and "€" not in blob
    assert "offer" not in report_csv and "EUR" not in report_csv and "€" not in report_csv


def test_cells_past_the_header_are_kept_and_reported(tmp_path: Path):
    rows, report = _clean_csv(
        tmp_path,
        "Name,Straße,PLZ,Ort,Telefon,E-Mail\n"
        "Zu Viele,Weg 10,12345,Ort,0170 10,v@b.de,EXTRA,EXTRA2\n",
        "zu-viele.csv",
    )
    assert rows[0][0] == "Zu Viele"
    assert "EXTRA | EXTRA2" in rows[0]
    assert _has(report, 2, "Zusatzspalten", "extra_columns", "EXTRA | EXTRA2", "EXTRA | EXTRA2")
    finding = next(item for item in report["findings"] if item["reason"] == "extra_columns")
    assert "EXTRA" in finding["message"] and "EXTRA2" in finding["message"]
    assert finding["original_row_id"] == 2


def test_example_1_normalizes_and_flags_exact_duplicate(tmp_path: Path):
    rows, report = _clean_csv(tmp_path, EXAMPLE_1, "kunden.csv")
    assert rows[0][:3] == ["Hans Müller", "+49 171 1234567", "hans.mueller@beispiel.de"]
    assert rows[0][3] == "Zeile 3 = mögliche Dublette von Zeile 2"
    assert rows[1][:3] == ["Hans Müller", "+49 171 1234567", "hans.mueller@beispiel.de"]
    assert rows[1][3] == "⚠ Dublette, du entscheidest"
    assert rows[2] == ["Erika Musterfrau", "+49 30 1234567", "erika@example.com", "", "4"]
    assert len(rows) == 3
    assert _has(report, 2, "Name", "name_comma_order", " mÜLLER, hans ", "Hans Müller")
    assert _has(report, 2, "Name", "inconsistent_case", " mÜLLER, hans ", "Hans Müller")
    assert _has(report, 2, "Telefon", "phone_normalized", "0171/123 45 67", "+49 171 1234567")
    assert _has(report, 2, "E-Mail", "email_normalized", " Hans.Mueller@Beispiel.DE", "hans.mueller@beispiel.de")
    assert _has(report, 2, "Name", "exact_duplicate")
    assert _has(report, 3, "Name", "exact_duplicate")
    assert _has(report, 4, "Name", "inconsistent_case", "ERIKA MUSTERFRAU", "Erika Musterfrau")
    assert not any(item["reason"] == "fuzzy_duplicate" for item in report["findings"])


def test_example_2_flags_plz_and_street_without_guessing(tmp_path: Path):
    rows, report = _clean_csv(tmp_path, EXAMPLE_2, "mitglieder.csv")
    assert rows[0][:4] == ["Peter Beispiel", "Musterstraße 12", "1234", "Musterstadt"]
    assert rows[0][4] == "⚠ PLZ hat nur 4 Stellen (fehlt eine führende 0?). Bitte prüfen, wird nicht geraten"
    assert rows[1] == ["Anna Probe", "Hauptstraße 5a", "12345", "Musterstadt", "", "3"]
    assert rows[2][:4] == ["Lena Test", "Bahnhofstraße 7", "12345", "Musterstadt"]
    assert rows[2][4] == "⚠ Schreibweise „Bahnhofsstrasse“ angepasst, bitte bestätigen"
    assert _has(report, 2, "PLZ", "plz_not_5_digits", "1234", "1234")
    assert _has(report, 2, "Straße", "street_abbreviation", "Musterstr.12", "Musterstraße 12")
    assert _has(report, 3, "PLZ", "plz_country_prefix", "D-12345", "12345")
    assert _has(report, 3, "Straße", "whitespace", "Hauptstraße  5a", "Hauptstraße 5a")
    assert _has(report, 4, "Straße", "street_spelling", "Bahnhofsstrasse 7", "Bahnhofstraße 7")
    assert _has(report, 2, "Name", "inconsistent_case", "peter beispiel", "Peter Beispiel")
    assert _has(report, 2, "Ort", "inconsistent_case", "musterstadt", "Musterstadt")
    assert _has(report, 4, "Ort", "inconsistent_case", "MUSTERSTADT", "Musterstadt")
    assert not any(item["after"] == "01234" for item in report["findings"])


def test_example_3_flags_invalid_emails_and_does_not_rewrite_them(tmp_path: Path):
    rows, report = _clean_csv(tmp_path, EXAMPLE_3, "newsletter.csv")
    assert rows[0][1] == "tom.demo@beispiel,de"
    assert "Komma statt Punkt" in rows[0][2]
    assert rows[1][1] == "sara.muster@@example.com"
    assert "doppeltes @" in rows[1][2]
    assert rows[2] == ["Jan Probe", "jan.probe@example.com", "", "4"]
    assert rows[3][1] == "mia.test(at)beispiel.de"
    assert "(at)" in rows[3][2]
    assert _has(report, 2, "E-Mail", "email_comma", "tom.demo@beispiel,de", "tom.demo@beispiel,de")
    assert _has(report, 3, "E-Mail", "email_double_at", "sara.muster@@example.com", "sara.muster@@example.com")
    assert _has(report, 4, "E-Mail", "email_normalized", "JAN.PROBE@EXAMPLE.COM  ", "jan.probe@example.com")
    assert _has(report, 4, "E-Mail", "inconsistent_case", "JAN.PROBE@EXAMPLE.COM  ", "jan.probe@example.com")
    assert any("klein geschrieben" in item["message"] for item in report["findings"] if item["row"] == 4)
    assert _has(report, 5, "E-Mail", "email_at_word", "mia.test(at)beispiel.de", "mia.test(at)beispiel.de")


def test_fuzzy_duplicate_is_name_plus_plz_only(tmp_path: Path):
    text = (
        "Name,Straße,PLZ,Ort\n"
        "Anna Probe,Hauptstraße 1,12345,Musterstadt\n"
        "Anna Probe,Nebenweg 2,12345,Musterstadt\n"
        "Anna Probe,Nebenweg 2,12346,Musterstadt\n"
        '"Müller, Hans",Hauptstraße 9,10115,Berlin\n'
        "Hans Müller,Andere Straße 2,10115,Berlin\n"
    )
    rows, report = _clean_csv(tmp_path, text, "fuzzy.csv")
    assert "Name + PLZ" in rows[0][4]
    assert rows[1][4] == "⚠ mögliche Dublette (Name + PLZ), du entscheidest"
    assert rows[2][4] == ""
    assert "Name + PLZ" in rows[3][4]
    assert rows[4][4] == "⚠ mögliche Dublette (Name + PLZ), du entscheidest"
    assert _has(report, 2, "Name", "fuzzy_duplicate")
    assert _has(report, 3, "Name", "fuzzy_duplicate")
    assert not _has(report, 4, "Name", "fuzzy_duplicate")
    assert not any(item["reason"] == "exact_duplicate" for item in report["findings"])


def test_empty_required_fields_are_flagged_and_left_empty(tmp_path: Path):
    text = (
        "Name,Straße,PLZ,Ort\n"
        ",Hauptstraße 1,12345,Berlin\n"
        "Mia Test,Hauptstraße 1,,Berlin\n"
        "Mia Test,Hauptstraße 1,123456,Berlin\n"
    )
    rows, report = _clean_csv(tmp_path, text, "leer.csv")
    assert rows[0][0] == ""
    assert "Pflichtfeld Name ist leer" in rows[0][4]
    assert rows[1][2] == ""
    assert "Pflichtfeld PLZ ist leer" in rows[1][4]
    assert rows[2][2] == "123456"
    assert "nicht genau 5 Stellen" in rows[2][4]
    assert _has(report, 2, "Name", "empty_required", "", "")
    assert _has(report, 3, "PLZ", "empty_required", "", "")
    assert _has(report, 4, "PLZ", "plz_not_5_digits", "123456", "123456")


def test_newsletter_requires_email_customer_list_does_not(tmp_path: Path):
    newsletter, report = _clean_csv(tmp_path, "Name,E-Mail\nTom Demo,\n", "news.csv")
    assert "Pflichtfeld E-Mail ist leer" in newsletter[0][2]
    assert _has(report, 2, "E-Mail", "empty_required")
    customer, customer_report = _clean_csv(
        tmp_path,
        "Name,Telefon,E-Mail\nTom Demo,0171 1234567,\n",
        "kunde-leer.csv",
    )
    assert customer[0][2] == ""
    assert customer[0][3] == ""
    assert not _has(customer_report, 2, "E-Mail", "empty_required")


def test_formula_cells_stay_untouched(tmp_path: Path):
    rows, report = _clean_csv(
        tmp_path,
        "Name,Telefon\n=SUMME(A2),01711234567\n",
        "formel.csv",
    )
    assert rows[0][0] == "=SUMME(A2)"
    assert rows[0][1] == "+49 171 1234567"
    assert _has(report, 2, "Name", "formula_preserved", "=SUMME(A2)", "=SUMME(A2)")


def test_street_abbreviation_keeps_a_trailing_s(tmp_path: Path):
    rows, _report = _clean_csv(
        tmp_path,
        "Name,Straße,PLZ,Ort\nThomas Beispiel,Thomasstr. 1,12345,Berlin\n",
        "thomas.csv",
    )
    assert rows[0][1] == "Thomasstraße 1"


def test_row_limit_rejects_2001_and_accepts_2000(tmp_path: Path):
    header = "Name,E-Mail\n"
    ok = header + "".join(f"Person {i},person{i}@example.com\n" for i in range(MAX_ROWS))
    rows, _report = _clean_csv(tmp_path, ok, "voll.csv")
    assert len(rows) == MAX_ROWS
    too_many = tmp_path / "zu-gross.csv"
    too_many.write_text(header + "".join(f"Person {i},person{i}@example.com\n" for i in range(MAX_ROWS + 1)), encoding="utf-8")
    with pytest.raises(ListCleanError, match="2000"):
        clean_file(too_many)
    assert not (tmp_path / "zu-gross.cleaned.csv").exists()


def test_semicolon_csv_and_report_roundtrip(tmp_path: Path):
    source = tmp_path / "verein.csv"
    source.write_bytes(
        "Name;Straße;PLZ;Ort\n"
        "peter beispiel;Musterstr.12;1234;musterstadt\n".encode("utf-8")
    )
    written = clean_file(source)
    text = Path(written["output"]).read_text(encoding="utf-8-sig")
    assert text.splitlines()[0] == "Name;Straße;PLZ;Ort;Hinweis;original_row_id"
    report_csv = Path(written["report_csv"]).read_text(encoding="utf-8-sig")
    parsed = list(csv.reader(io.StringIO(report_csv), delimiter=";"))
    assert parsed[0] == ["original_row_id", "row", "column", "reason", "before", "after", "message"]
    assert any(row[3] == "plz_not_5_digits" for row in parsed[1:])
    assert all(row[0] == row[1] and row[0] != "" for row in parsed[1:])


def test_xlsx_roundtrip_and_numeric_plz(tmp_path: Path):
    source_csv = tmp_path / "roh.csv"
    source_csv.write_bytes(EXAMPLE_1.encode("utf-8"))
    raw_table = read_table(source_csv, max_rows=MAX_ROWS)
    xlsx = tmp_path / "roh.xlsx"
    write_table(xlsx, raw_table.headers, raw_table.rows, delimiter=";", kind="xlsx")
    written = clean_file(xlsx)
    cleaned = read_table(Path(written["output"]), max_rows=MAX_ROWS)
    assert cleaned.rows[0][0] == "Hans Müller"
    assert cleaned.rows[0][1] == "+49 171 1234567"
    assert cleaned.rows[1][3] == "⚠ Dublette, du entscheidest"
    assert Path(written["output"]).suffix == ".xlsx"
    assert xlsx.read_bytes()  # source still present

    numeric = tmp_path / "zahl.xlsx"
    _write_numeric_plz(numeric)
    number_rows, number_report = _clean_existing(numeric)
    assert number_rows[0][0] == "Mia Test"
    assert number_rows[0][2] == "1234"
    assert "4 Stellen" in number_rows[0][4]
    assert _has(number_report, 2, "PLZ", "plz_not_5_digits", "1234", "1234")


def test_two_runs_are_identical(tmp_path: Path):
    source = tmp_path / "gleich.csv"
    source.write_bytes(EXAMPLE_2.encode("utf-8"))
    first = clean_file(source, output=tmp_path / "a.csv", report=tmp_path / "a.csv.report.csv")
    second = clean_file(source, output=tmp_path / "b.csv", report=tmp_path / "b.csv.report.csv")
    assert Path(first["output"]).read_bytes() == Path(second["output"]).read_bytes()
    assert json.loads(Path(first["report_json"]).read_text(encoding="utf-8"))["findings"] == json.loads(
        Path(second["report_json"]).read_text(encoding="utf-8")
    )["findings"]


def test_refuses_to_overwrite_the_source(tmp_path: Path):
    source = tmp_path / "quelle.csv"
    source.write_text("Name,E-Mail\nMia Test,mia@example.com\n", encoding="utf-8")
    code = main([str(source), "-o", str(source)])
    assert code == 2
    assert source.read_text(encoding="utf-8").startswith("Name,E-Mail")


def test_de_prefix_plz_and_unrecognized_phone():
    result = clean_table(
        ["Name", "Telefon", "PLZ"],
        [["Mia Test", "abc", "DE-12345"], ["Mia Test", "+43 1 234567", "12345"]],
    )
    assert result.rows[0][1] == "abc"
    assert result.rows[0][2] == "12345"
    assert "nicht erkannt" in result.rows[0][3]
    assert result.rows[1][1] == "+43 1 234567"
    assert any(item.reason == "plz_country_prefix" and item.after == "12345" for item in result.findings)
    assert any(item.reason == "phone_unrecognized" for item in result.findings)


def test_module_does_not_import_network_or_model_clients():
    root = Path(__file__).resolve().parents[1] / "courier_listclean"
    banned = {"socket", "urllib", "requests", "httpx", "openai", "http.client", "ftplib", "smtplib"}
    for path in root.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [alias.name.split(".")[0] for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [(node.module or "").split(".")[0]]
            else:
                continue
            assert banned.isdisjoint(names), path.name


def test_clean_table_does_not_open_a_socket(monkeypatch: pytest.MonkeyPatch):
    def boom(*_args, **_kwargs):
        raise AssertionError("network")

    monkeypatch.setattr(socket, "socket", boom)
    result = clean_table(["Name", "E-Mail"], [["Mia Test", "Mia.Test@Example.com"]])
    assert result.rows[0][1] == "mia.test@example.com"


def _clean_existing(path: Path) -> tuple[list[list[str]], dict]:
    written = clean_file(path)
    table = read_table(Path(written["output"]), max_rows=MAX_ROWS)
    report = json.loads(Path(written["report_json"]).read_text(encoding="utf-8"))
    return table.rows, report


def _write_numeric_plz(path: Path) -> None:
    import zipfile

    sheet = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <sheetData>
    <row r="1">
      <c r="A1" t="inlineStr"><is><t>Name</t></is></c>
      <c r="B1" t="inlineStr"><is><t>Straße</t></is></c>
      <c r="C1" t="inlineStr"><is><t>PLZ</t></is></c>
      <c r="D1" t="inlineStr"><is><t>Ort</t></is></c>
    </row>
    <row r="2">
      <c r="A2" t="inlineStr"><is><t>Mia Test</t></is></c>
      <c r="B2" t="inlineStr"><is><t>Hauptstraße 1</t></is></c>
      <c r="C2"><v>1234</v></c>
      <c r="D2" t="inlineStr"><is><t>Berlin</t></is></c>
    </row>
  </sheetData>
</worksheet>
"""
    workbook = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <sheets><sheet name="Liste" sheetId="1" r:id="rId1"/></sheets>
</workbook>
"""
    rels = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
</Relationships>
"""
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("xl/workbook.xml", workbook)
        zf.writestr("xl/_rels/workbook.xml.rels", rels)
        zf.writestr("xl/worksheets/sheet1.xml", sheet)
