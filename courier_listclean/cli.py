"""Command line for the 39 EUR list cleaner."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import sys
from pathlib import Path

from .clean import MAX_ROWS, DECISION_REASONS, CleanResult, ListCleanError, clean_table
from .io_tables import read_table, write_table


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="courier-listclean",
        description=(
            "Bereinigt eine Kunden-, Mitglieder- oder Adressliste (CSV oder XLSX, "
            f"bis {MAX_ROWS} Zeilen). Schreibt eine Kopie und einen Änderungsbericht. "
            "Die Quelldatei bleibt unverändert. Kein Netz, keine KI."
        ),
    )
    parser.add_argument("input", type=Path, help="CSV- oder XLSX-Datei")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="Pfad der bereinigten Kopie (Standard: <name>.cleaned.csv bzw. .xlsx)",
    )
    parser.add_argument(
        "-r",
        "--report",
        type=Path,
        help="Pfad des Berichtes als CSV (JSON entsteht daneben)",
    )
    parser.add_argument(
        "--max-rows",
        type=int,
        default=MAX_ROWS,
        help=f"Obergrenze der Datenzeilen (Standard {MAX_ROWS})",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        written = clean_file(
            args.input,
            output=args.output,
            report=args.report,
            max_rows=args.max_rows,
        )
    except ListCleanError as exc:
        print(f"courier-listclean: {exc}", file=sys.stderr)
        return 2
    print(f"Bereinigt: {written['output']}")
    print(f"Bericht: {written['report_csv']}")
    print(f"Markierungen: {written['decision_flags']}")
    return 0


def clean_file(
    source: Path,
    *,
    output: Path | None = None,
    report: Path | None = None,
    max_rows: int = MAX_ROWS,
) -> dict[str, str | int]:
    source = source.expanduser().resolve()
    if not source.is_file():
        raise ListCleanError(f"Datei nicht gefunden: {source}")
    output_path = (output or _default_output(source)).expanduser().resolve()
    report_csv = (report or source.with_name(f"{source.stem}.report.csv")).expanduser().resolve()
    report_json = report_csv.with_suffix(".json")
    for target in (output_path, report_csv, report_json):
        if target == source:
            raise ListCleanError("Die Ausgabe darf die Quelldatei nicht überschreiben.")
    raw = source.read_bytes()
    table = read_table(source, max_rows=max_rows)
    result = clean_table(
        table.headers,
        table.rows,
        row_numbers=table.row_numbers,
        max_rows=max_rows,
    )
    kind = "xlsx" if output_path.suffix.lower() == ".xlsx" else table.kind
    delimiter = ";" if kind == "xlsx" else table.delimiter
    write_table(output_path, result.headers, result.rows, delimiter=delimiter, kind=kind)
    payload = _report_payload(
        source_name=source.name,
        source_sha256=hashlib.sha256(raw).hexdigest(),
        result=result,
        delimiter=delimiter,
    )
    report_csv.parent.mkdir(parents=True, exist_ok=True)
    _write_report_csv(report_csv, result, delimiter=delimiter)
    # write_bytes keeps LF on Windows. write_text would rewrite newlines and change the hash.
    report_json.write_bytes((json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    return {
        "output": str(output_path),
        "report_csv": str(report_csv),
        "report_json": str(report_json),
        "decision_flags": result.decision_count,
    }


def _default_output(source: Path) -> Path:
    if source.suffix.lower() == ".xlsx":
        return source.with_name(f"{source.stem}.cleaned.xlsx")
    return source.with_name(f"{source.stem}.cleaned.csv")


def _report_payload(
    *,
    source_name: str,
    source_sha256: str,
    result: CleanResult,
    delimiter: str,
) -> dict[str, object]:
    counts: dict[str, int] = {}
    for item in result.findings:
        counts[item.reason] = counts.get(item.reason, 0) + 1
    return {
        "tool": "courier-listclean",
        "offer": "39 EUR",
        "source": source_name,
        "source_sha256": source_sha256,
        "rows_in": len(result.rows),
        "rows_out": len(result.rows),
        "delimiter": delimiter,
        "decision_flags": result.decision_count,
        "counts": counts,
        "findings": [item.as_dict() for item in result.findings],
    }


def _write_report_csv(path: Path, result: CleanResult, *, delimiter: str) -> None:
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer, delimiter=delimiter, lineterminator="\n", quoting=csv.QUOTE_MINIMAL)
    writer.writerow(["original_row_id", "row", "column", "reason", "before", "after", "message"])
    for item in result.findings:
        writer.writerow(
            [item.row, item.row, item.column, item.reason, item.before, item.after, item.message]
        )
    path.write_bytes(buffer.getvalue().encode("utf-8-sig"))


if __name__ == "__main__":
    raise SystemExit(main())
