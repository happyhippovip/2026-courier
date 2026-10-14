"""Pilot of 50 fictional rows for the 39 EUR cleaner.

Every data row is counted once:

- rejected: empty required field, invalid email, or a PLZ that is not 5 digits
- duplicate: exact or fuzzy duplicate, and not rejected
- accepted: every remaining row

50 = accepted + duplicates + rejected.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
from pathlib import Path

from courier_listclean.clean import ORIGINAL_ROW_ID
from courier_listclean.cli import clean_file

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "listclean_79"

SOURCE = FIXTURE_DIR / "pilot_50.csv"
EXPECTED_CLEANED = FIXTURE_DIR / "pilot_50.cleaned.csv"
EXPECTED_REPORT_JSON = FIXTURE_DIR / "pilot_50.report.json"
EXPECTED_REPORT_CSV = FIXTURE_DIR / "pilot_50.report.csv"

REJECT_REASONS = frozenset(
    {
        "empty_required",
        "email_invalid",
        "email_comma",
        "email_double_at",
        "email_at_word",
        "plz_not_5_digits",
    }
)
DUPLICATE_REASONS = frozenset({"exact_duplicate", "fuzzy_duplicate"})


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _disposition(reasons: set[str]) -> str:
    if reasons & REJECT_REASONS:
        return "rejected"
    if reasons & DUPLICATE_REASONS:
        return "duplicate"
    return "accepted"


def test_pilot_50_rows_partition_and_hashes_are_stable(tmp_path: Path):
    source_bytes = SOURCE.read_bytes()
    first = clean_file(
        SOURCE,
        output=tmp_path / "run1.cleaned.csv",
        report=tmp_path / "run1.report.csv",
    )
    second = clean_file(
        SOURCE,
        output=tmp_path / "run2.cleaned.csv",
        report=tmp_path / "run2.report.csv",
    )
    cleaned_hash = _sha256(Path(first["output"]))
    report_hash = _sha256(Path(first["report_json"]))
    report_csv_hash = _sha256(Path(first["report_csv"]))
    assert cleaned_hash == _sha256(Path(second["output"]))
    assert report_hash == _sha256(Path(second["report_json"]))
    assert report_csv_hash == _sha256(Path(second["report_csv"]))
    assert cleaned_hash == _sha256(EXPECTED_CLEANED)
    assert report_hash == _sha256(EXPECTED_REPORT_JSON)
    assert report_csv_hash == _sha256(EXPECTED_REPORT_CSV)
    assert SOURCE.read_bytes() == source_bytes
    assert _sha256(SOURCE) == json.loads(EXPECTED_REPORT_JSON.read_text(encoding="utf-8"))["source_sha256"]

    report = json.loads(Path(first["report_json"]).read_text(encoding="utf-8"))
    reasons_by_id: dict[int, set[str]] = {}
    for item in report["findings"]:
        assert item["original_row_id"] == item["row"]
        assert item["original_row_id"] != ""
        reasons_by_id.setdefault(item["original_row_id"], set()).add(item["reason"])

    with Path(first["output"]).open(encoding="utf-8-sig", newline="") as handle:
        cleaned_rows = list(csv.reader(handle))
    header, data = cleaned_rows[0], cleaned_rows[1:]
    assert header[-1] == ORIGINAL_ROW_ID
    assert len(data) == 50
    output_ids = [int(row[-1]) for row in data]
    assert output_ids == list(range(2, 52))
    assert len(set(output_ids)) == 50

    counts = {"accepted": 0, "duplicate": 0, "rejected": 0}
    for row_id in output_ids:
        counts[_disposition(reasons_by_id.get(row_id, set()))] += 1
    assert counts == {"accepted": 30, "duplicate": 10, "rejected": 10}
    assert counts["accepted"] + counts["duplicate"] + counts["rejected"] == 50

    present = {reason for reasons in reasons_by_id.values() for reason in reasons}
    assert {"exact_duplicate", "fuzzy_duplicate"} <= present
    assert {"email_comma", "email_double_at", "email_at_word", "plz_not_5_digits", "empty_required"} <= present
    assert "inconsistent_case" in present

    report_csv = Path(first["report_csv"]).read_text(encoding="utf-8-sig")
    parsed = list(csv.reader(io.StringIO(report_csv)))
    assert parsed[0][0] == "original_row_id"
    assert len(parsed) == len(report["findings"]) + 1
    for row, item in zip(parsed[1:], report["findings"]):
        assert row[0] == str(item["original_row_id"])
        assert row[0] != ""
