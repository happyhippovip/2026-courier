"""Spreadsheet vertical slice on .xlsx with the standard library only.

WORKBOOK -> REQUESTED CHANGE -> PLANNED MUTATION (preview) -> MUTATION on a
copy -> VERIFY (intended cells changed, every other cell identical) ->
atomic replace -> RECEIPT. Values only (numbers and inline strings); formulas
and styles are carried through byte-for-byte on cells that are not edited.
"""
import hashlib
import os
import re
import shutil
import tempfile
import zipfile
import xml.etree.ElementTree as ET

NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
ET.register_namespace("", NS)
SHEET = "xl/worksheets/sheet1.xml"
CELL_REF = re.compile(r"^[A-Z]{1,3}[1-9][0-9]{0,6}$")


def _q(tag):
    return f"{{{NS}}}{tag}"


def _shared_strings(z):
    try:
        root = ET.fromstring(z.read("xl/sharedStrings.xml"))
    except KeyError:
        return []
    return ["".join(t.text or "" for t in si.iter(_q("t"))) for si in root.findall(_q("si"))]


def read_cells(path):
    """{ref: value} for sheet1; formulas are reported as '=<formula>'."""
    with zipfile.ZipFile(path) as z:
        shared = _shared_strings(z)
        root = ET.fromstring(z.read(SHEET))
    cells = {}
    for c in root.iter(_q("c")):
        ref, kind = c.get("r"), c.get("t")
        f, v, is_ = c.find(_q("f")), c.find(_q("v")), c.find(_q("is"))
        if f is not None:
            cells[ref] = "=" + (f.text or "")
        elif kind == "s" and v is not None:
            cells[ref] = shared[int(v.text)]
        elif kind == "inlineStr" and is_ is not None:
            cells[ref] = "".join(t.text or "" for t in is_.iter(_q("t")))
        elif v is not None:
            cells[ref] = float(v.text) if "." in v.text else int(v.text)
    return cells


def plan(path, changes):
    """Preview: [(ref, before, after)] for each requested cell; refuses formulas and bad refs."""
    current = read_cells(path)
    out = []
    for ref, value in changes.items():
        if not CELL_REF.match(ref):
            raise ValueError(f"bad cell reference {ref!r}")
        if isinstance(current.get(ref), str) and current[ref].startswith("="):
            raise ValueError(f"{ref} holds a formula; editing formulas is out of scope")
        if not isinstance(value, (int, float, str)) or (isinstance(value, str) and value.startswith("=")):
            raise ValueError(f"{ref}: only plain numbers and text can be written")
        out.append((ref, current.get(ref), value))
    return out


def _set_cell(root, ref, value):
    sheet_data = root.find(_q("sheetData"))
    row_no = int(re.sub(r"[A-Z]", "", ref))
    row = next((r for r in sheet_data.findall(_q("row")) if int(r.get("r")) == row_no), None)
    if row is None:
        row = ET.SubElement(sheet_data, _q("row"), r=str(row_no))
    cell = next((c for c in row.findall(_q("c")) if c.get("r") == ref), None)
    if cell is None:
        cell = ET.SubElement(row, _q("c"), r=ref)
    for child in list(cell):
        cell.remove(child)
    cell.attrib.pop("t", None)
    if isinstance(value, str):
        cell.set("t", "inlineStr")
        ET.SubElement(ET.SubElement(cell, _q("is")), _q("t")).text = value
    else:
        ET.SubElement(cell, _q("v")).text = repr(value)


def _sha256(path):
    with open(path, "rb") as handle:
        return hashlib.sha256(handle.read()).hexdigest()


def apply(path, changes, grant_id):
    """Mutate a copy, verify it, then atomically replace. Returns a receipt; the original
    file is untouched if verification fails."""
    if not grant_id:
        raise PermissionError("writing a workbook needs a grant (fs.write on this path)")
    preview = plan(path, changes)
    before = read_cells(path)
    before_hash = _sha256(path)
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(os.path.abspath(path)), suffix=".xlsx")
    os.close(fd)
    try:
        with zipfile.ZipFile(path) as src, zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as dst:
            for item in src.infolist():
                data = src.read(item.filename)
                if item.filename == SHEET:
                    root = ET.fromstring(data)
                    for ref, value in changes.items():
                        _set_cell(root, ref, value)
                    data = ET.tostring(root, xml_declaration=True, encoding="UTF-8")
                dst.writestr(item, data)
        after = read_cells(tmp)
        unexpected = sorted(r for r in set(before) | set(after) if r not in changes and before.get(r) != after.get(r))
        wrong = sorted(r for r, v in changes.items() if after.get(r) != v)
        if unexpected or wrong:
            raise AssertionError(f"verification failed: changed {unexpected}, not applied {wrong}")
        os.replace(tmp, path)
    except Exception:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise
    return {"path": os.path.basename(path), "grant_id": grant_id, "before_sha256": before_hash,
            "after_sha256": _sha256(path), "changes": [{"cell": r, "before": b, "after": a} for r, b, a in preview],
            "untouched_cells_verified": len(set(before) - set(changes))}


def make_fixture(path, cells):
    """Minimal valid .xlsx with one sheet; values or '=formula' strings."""
    rows = {}
    for ref, value in cells.items():
        rows.setdefault(int(re.sub(r"[A-Z]", "", ref)), []).append((ref, value))
    sheet = ET.Element(_q("worksheet"))
    data = ET.SubElement(sheet, _q("sheetData"))
    for r in sorted(rows):
        row = ET.SubElement(data, _q("row"), r=str(r))
        for ref, value in sorted(rows[r]):
            c = ET.SubElement(row, _q("c"), r=ref)
            if isinstance(value, str) and value.startswith("="):
                ET.SubElement(c, _q("f")).text = value[1:]
            elif isinstance(value, str):
                c.set("t", "inlineStr")
                ET.SubElement(ET.SubElement(c, _q("is")), _q("t")).text = value
            else:
                ET.SubElement(c, _q("v")).text = repr(value)
    files = {
        "[Content_Types].xml": '<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/></Types>',
        "_rels/.rels": '<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>',
        "xl/workbook.xml": f'<?xml version="1.0" encoding="UTF-8"?><workbook xmlns="{NS}" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Sheet1" sheetId="1" r:id="rId1"/></sheets></workbook>',
        "xl/_rels/workbook.xml.rels": '<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/></Relationships>',
    }
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        for name, text in files.items():
            z.writestr(name, text)
        z.writestr(SHEET, ET.tostring(sheet, xml_declaration=True, encoding="UTF-8"))
    return path
