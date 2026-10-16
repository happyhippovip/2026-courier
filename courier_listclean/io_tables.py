"""CSV and XLSX read/write. Standard library only."""

from __future__ import annotations

import csv
import io
import re
import zipfile
from dataclasses import dataclass
from pathlib import Path
from xml.etree import ElementTree as ET

from .clean import ListCleanError

NS_MAIN = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
NS_REL_OFFICE = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
NS_REL_PKG = "http://schemas.openxmlformats.org/package/2006/relationships"
MAX_UNCOMPRESSED_BYTES = 32 * 1024 * 1024
MAX_COLUMNS = 64

_INT_NUMBER = re.compile(r"-?\d+(?:\.0+)?")


@dataclass(frozen=True)
class Table:
    headers: list[str]
    rows: list[list[str]]
    row_numbers: list[int]
    delimiter: str
    kind: str


def read_table(path: Path, *, max_rows: int) -> Table:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return _read_csv(path, max_rows=max_rows)
    if suffix == ".xlsx":
        return _read_xlsx(path, max_rows=max_rows)
    raise ListCleanError("Bitte eine CSV- oder XLSX-Datei übergeben.")


def write_table(path: Path, headers: list[str], rows: list[list[str]], *, delimiter: str, kind: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if kind == "xlsx" or path.suffix.lower() == ".xlsx":
        _write_xlsx(path, headers, rows)
        return
    _write_csv(path, headers, rows, delimiter=delimiter or ",")


def _decode_csv(raw: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-8", "cp1252"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ListCleanError("Die CSV-Datei lässt sich nicht als UTF-8 oder Windows-1252 lesen.")


def _detect_delimiter(header_line: str) -> str:
    counts = {",": 0, ";": 0, "\t": 0}
    in_quotes = False
    for ch in header_line:
        if ch == '"':
            in_quotes = not in_quotes
            continue
        if not in_quotes and ch in counts:
            counts[ch] += 1
    best = max(counts, key=lambda key: counts[key])
    if counts[best] == 0:
        return ","
    return best


def _read_csv(path: Path, *, max_rows: int) -> Table:
    text = _decode_csv(path.read_bytes())
    if text == "":
        raise ListCleanError("Die Datei ist leer.")
    first_line = text.splitlines()[0] if text.splitlines() else ""
    delimiter = _detect_delimiter(first_line)
    reader = csv.reader(io.StringIO(text), delimiter=delimiter)
    parsed = list(reader)
    if not parsed or not any(cell.strip() for cell in parsed[0]):
        raise ListCleanError("Die Datei hat keine Kopfzeile.")
    headers = list(parsed[0])
    rows: list[list[str]] = []
    row_numbers: list[int] = []
    for offset, record in enumerate(parsed[1:], start=2):
        if not any(cell.strip() for cell in record):
            continue
        rows.append(record)
        row_numbers.append(offset)
        if len(rows) > max_rows:
            raise ListCleanError(
                f"Die Liste hat mehr als {max_rows} Datenzeilen. "
                f"Das 39-€-Angebot gilt bis {max_rows} Zeilen."
            )
    width = len(headers)
    rows = [_fit_width(row, width) for row in rows]
    return Table(headers=headers, rows=rows, row_numbers=row_numbers, delimiter=delimiter, kind="csv")


def _fit_width(row: list[str], width: int) -> list[str]:
    """Pad a short row. Cells past the header stay on the row and are not dropped."""
    if len(row) >= width:
        return list(row)
    return [*row, *[""] * (width - len(row))]


def _read_xlsx(path: Path, *, max_rows: int) -> Table:
    try:
        zf = zipfile.ZipFile(path)
    except zipfile.BadZipFile as exc:
        raise ListCleanError("Die XLSX-Datei lässt sich nicht öffnen.") from exc
    with zf:
        total = sum(info.file_size for info in zf.infolist())
        if total > MAX_UNCOMPRESSED_BYTES:
            raise ListCleanError("Die Datei ist zu groß für das 39-€-Angebot.")
        sheet_name = _first_sheet_name(zf)
        strings = _shared_strings(zf)
        try:
            root = ET.fromstring(zf.read(sheet_name))
        except KeyError as exc:
            raise ListCleanError("Die XLSX-Datei enthält kein Arbeitsblatt.") from exc
    rows_by_index: dict[int, dict[int, str]] = {}
    max_col = 0
    for row in root.iter(f"{{{NS_MAIN}}}row"):
        ref = row.attrib.get("r")
        row_index = int(ref) if ref and ref.isdigit() else None
        cells: dict[int, str] = {}
        for cell in row.findall(f"{{{NS_MAIN}}}c"):
            cref = cell.attrib.get("r", "")
            col = _col_index(cref) if cref else len(cells)
            if col >= MAX_COLUMNS:
                raise ListCleanError(f"Die Liste hat mehr als {MAX_COLUMNS} Spalten.")
            cells[col] = _cell_text(cell, strings)
            max_col = max(max_col, col + 1)
        if row_index is None:
            row_index = (max(rows_by_index) + 1) if rows_by_index else 1
        rows_by_index[row_index] = cells
    if 1 not in rows_by_index:
        raise ListCleanError("Die Datei hat keine Kopfzeile.")
    header_cells = rows_by_index[1]
    width = max([1, max_col, max(header_cells, default=0) + 1])
    headers = [header_cells.get(i, "") for i in range(width)]
    if not any(headers):
        raise ListCleanError("Die Datei hat keine Kopfzeile.")
    data_indexes = [index for index in sorted(rows_by_index) if index > 1]
    if not data_indexes:
        return Table(headers=headers, rows=[], row_numbers=[], delimiter=";", kind="xlsx")
    last = data_indexes[-1]
    rows = []
    row_numbers = []
    for index in range(2, last + 1):
        cells = rows_by_index.get(index, {})
        values = [cells.get(col, "") for col in range(width)]
        if not any(value.strip() for value in values):
            continue
        rows.append(values)
        row_numbers.append(index)
        if len(rows) > max_rows:
            raise ListCleanError(
                f"Die Liste hat mehr als {max_rows} Datenzeilen. "
                f"Das 39-€-Angebot gilt bis {max_rows} Zeilen."
            )
    return Table(headers=headers, rows=rows, row_numbers=row_numbers, delimiter=";", kind="xlsx")


def _first_sheet_name(zf: zipfile.ZipFile) -> str:
    try:
        workbook = ET.fromstring(zf.read("xl/workbook.xml"))
        rels = ET.fromstring(zf.read("xl/_rels/workbook.xml.rels"))
    except KeyError as exc:
        raise ListCleanError("Die XLSX-Datei enthält kein Arbeitsblatt.") from exc
    sheets = workbook.findall(f"{{{NS_MAIN}}}sheets/{{{NS_MAIN}}}sheet")
    if not sheets:
        raise ListCleanError("Die XLSX-Datei enthält kein Arbeitsblatt.")
    rel_id = sheets[0].attrib.get(f"{{{NS_REL_OFFICE}}}id")
    target = None
    for rel in rels:
        if rel.attrib.get("Id") == rel_id:
            target = rel.attrib.get("Target")
            break
    if not target:
        raise ListCleanError("Die XLSX-Datei enthält kein Arbeitsblatt.")
    target = target.lstrip("/")
    if not target.startswith("xl/"):
        target = "xl/" + target
    return target


def _shared_strings(zf: zipfile.ZipFile) -> list[str]:
    try:
        root = ET.fromstring(zf.read("xl/sharedStrings.xml"))
    except KeyError:
        return []
    values: list[str] = []
    for si in root.findall(f"{{{NS_MAIN}}}si"):
        parts = [node.text or "" for node in si.iter(f"{{{NS_MAIN}}}t")]
        values.append("".join(parts))
    return values


def _cell_text(cell: ET.Element, strings: list[str]) -> str:
    kind = cell.attrib.get("t")
    if kind == "inlineStr":
        parts = [node.text or "" for node in cell.iter(f"{{{NS_MAIN}}}t")]
        return "".join(parts)
    value = cell.find(f"{{{NS_MAIN}}}v")
    if kind == "s":
        if value is None or value.text is None:
            return ""
        index = int(value.text)
        if index < 0 or index >= len(strings):
            return ""
        return strings[index]
    if kind == "b":
        return "WAHR" if value is not None and value.text == "1" else "FALSCH"
    if value is None or value.text is None:
        return ""
    if kind in (None, "n"):
        return _number_to_text(value.text)
    return value.text


def _number_to_text(text: str) -> str:
    if _INT_NUMBER.fullmatch(text):
        return text.split(".", 1)[0]
    return text


def _col_index(cell_ref: str) -> int:
    letters = []
    for ch in cell_ref:
        if ch.isalpha():
            letters.append(ch.upper())
        else:
            break
    index = 0
    for ch in letters:
        index = index * 26 + (ord(ch) - 64)
    return max(0, index - 1)


def _write_csv(path: Path, headers: list[str], rows: list[list[str]], *, delimiter: str) -> None:
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer, delimiter=delimiter, lineterminator="\n", quoting=csv.QUOTE_MINIMAL)
    writer.writerow(headers)
    for row in rows:
        writer.writerow(row)
    path.write_bytes(buffer.getvalue().encode("utf-8-sig"))


def _write_xlsx(path: Path, headers: list[str], rows: list[list[str]]) -> None:
    matrix = [headers, *rows]
    strings: list[str] = []
    index_of: dict[str, int] = {}
    for row in matrix:
        for value in row:
            if value not in index_of:
                index_of[value] = len(strings)
                strings.append(value)
    sheet = _sheet_xml(matrix, index_of)
    payload = {
        "[Content_Types].xml": _content_types_xml(),
        "_rels/.rels": _root_rels_xml(),
        "xl/workbook.xml": _workbook_xml(),
        "xl/_rels/workbook.xml.rels": _workbook_rels_xml(),
        "xl/styles.xml": _styles_xml(),
        "xl/sharedStrings.xml": _shared_strings_xml(strings),
        "xl/worksheets/sheet1.xml": sheet,
    }
    with zipfile.ZipFile(path, "w") as zf:
        for name in sorted(payload):
            info = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            zf.writestr(info, payload[name].encode("utf-8"))


def _xml_text(text: str) -> str:
    escaped = (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
    if text[:1].isspace() or text[-1:].isspace() or "  " in text:
        return f'<t xml:space="preserve">{escaped}</t>'
    return f"<t>{escaped}</t>"


def _col_letter(index: int) -> str:
    number = index + 1
    letters = []
    while number:
        number, rem = divmod(number - 1, 26)
        letters.append(chr(65 + rem))
    return "".join(reversed(letters))


def _sheet_xml(matrix: list[list[str]], index_of: dict[str, int]) -> str:
    rows_xml = []
    for row_number, row in enumerate(matrix, start=1):
        cells = []
        for col, value in enumerate(row):
            ref = f"{_col_letter(col)}{row_number}"
            cells.append(f'<c r="{ref}" t="s"><v>{index_of[value]}</v></c>')
        rows_xml.append(f'<row r="{row_number}">{"".join(cells)}</row>')
    body = "".join(rows_xml)
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<worksheet xmlns="{NS_MAIN}"><sheetData>{body}</sheetData></worksheet>'
    )


def _shared_strings_xml(strings: list[str]) -> str:
    items = "".join(f"<si>{_xml_text(value)}</si>" for value in strings)
    count = len(strings)
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<sst xmlns="{NS_MAIN}" count="{count}" uniqueCount="{count}">{items}</sst>'
    )


def _content_types_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
  <Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
  <Override PartName="/xl/sharedStrings.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sharedStrings+xml"/>
  <Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>
</Types>
"""


def _root_rels_xml() -> str:
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="{NS_REL_PKG}">
  <Relationship Id="rId1" Type="{NS_REL_OFFICE}/officeDocument" Target="xl/workbook.xml"/>
</Relationships>
"""


def _workbook_xml() -> str:
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="{NS_MAIN}" xmlns:r="{NS_REL_OFFICE}">
  <sheets>
    <sheet name="Liste" sheetId="1" r:id="rId1"/>
  </sheets>
</workbook>
"""


def _workbook_rels_xml() -> str:
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="{NS_REL_PKG}">
  <Relationship Id="rId1" Type="{NS_REL_OFFICE}/worksheet" Target="worksheets/sheet1.xml"/>
  <Relationship Id="rId2" Type="{NS_REL_OFFICE}/sharedStrings" Target="sharedStrings.xml"/>
  <Relationship Id="rId3" Type="{NS_REL_OFFICE}/styles" Target="styles.xml"/>
</Relationships>
"""


def _styles_xml() -> str:
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<styleSheet xmlns="{NS_MAIN}">
  <fonts count="1"><font><sz val="11"/><name val="Calibri"/></font></fonts>
  <fills count="2"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill></fills>
  <borders count="1"><border/></borders>
  <cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>
  <cellXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/></cellXfs>
</styleSheet>
"""
