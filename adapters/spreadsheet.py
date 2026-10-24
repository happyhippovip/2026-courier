import hashlib
import json
import re
from courier_runtime.revenue import Lead, PROSPECT
from courier_runtime.workbook import read_cells
from collections import defaultdict

# Cost class read by the controller before a task exists (pure local computation, no per-run charge).
COST_CLASS = "local"
_REF = re.compile(r"^([A-Z]+)([1-9][0-9]*)$")

# Row-balance rejection reasons (parse_leads_with_balance)
EMPTY_ROW = "empty_row"
NO_NAME_OR_EMAIL = "no_name_or_email"
INVALID_EMAIL = "invalid_email"
DUPLICATE_EMAIL = "duplicate_email"


def split_ref(ref):
    """'AB12' -> ('AB', 12). Proper letter-prefix split; None for anything else."""
    m = _REF.match(ref) if isinstance(ref, str) else None
    return (m.group(1), int(m.group(2))) if m else None


def _text(value):
    if value is None:
        return ""
    return value.strip() if isinstance(value, str) else str(value)


class SpreadsheetAdapter:
    def __init__(self, workbook_path):
        self.workbook_path = workbook_path

    def _rows(self):
        cells = read_cells(self.workbook_path)
        rows = defaultdict(dict)
        unparsed = []
        for ref, val in cells.items():
            parsed = split_ref(ref)
            if parsed is None:
                unparsed.append(ref)
                continue
            col, row_idx = parsed
            if row_idx == 1:
                continue
            rows[row_idx][col] = val
        return rows, sorted(unparsed)

    def _lead(self, row_idx, name, source_name):
        return Lead(
            lead_id=f"L-{row_idx}",
            organisation=name,
            problem=f"Found in {self.workbook_path}",
            source=source_name,
            state=PROSPECT
        )

    def parse_leads(self, source_name="spreadsheet_import"):
        """Unchanged contract: list of Lead for rows with a name or a plausible e-mail.
        Columns AA and beyond are now parsed instead of being dropped by accident; only
        columns A (name) and B (e-mail) feed a Lead."""
        rows, _ = self._rows()
        leads = []
        for row_idx in sorted(rows.keys()):
            row = rows[row_idx]
            name = row.get("A", "").strip() if isinstance(row.get("A"), str) else str(row.get("A", ""))
            email = row.get("B", "").strip() if isinstance(row.get("B"), str) else str(row.get("B", ""))
            
            if not name and not email:
                continue
            
            # Basic validation
            if email and "@" not in email:
                continue
                
            leads.append(self._lead(row_idx, name, source_name))
            
        return leads

    def parse_leads_with_balance(self, source_name="spreadsheet_import"):
        """(leads, balance). Every data row is either accepted or rejected with a reason
        and its original cells: rows_in == accepted + rejected, unexplained == 0.
        Unlike parse_leads, a repeated e-mail (case-insensitive) is rejected as duplicate."""
        rows, unparsed = self._rows()
        leads, accepted, rejected, seen = [], [], [], {}
        for row_idx in sorted(rows):
            row = rows[row_idx]
            original = {col: row[col] for col in sorted(row, key=lambda c: (len(c), c))}
            name, email = _text(row.get("A")), _text(row.get("B"))
            reason, detail = None, None
            if not any(_text(v) for v in row.values()):
                reason = EMPTY_ROW
            elif not name and not email:
                reason = NO_NAME_OR_EMAIL
            elif email and "@" not in email:
                reason = INVALID_EMAIL
            elif email and email.lower() in seen:
                reason, detail = DUPLICATE_EMAIL, f"L-{seen[email.lower()]}"
            if reason:
                entry = {"row": row_idx, "reason": reason, "original": original}
                if detail:
                    entry["duplicate_of"] = detail
                rejected.append(entry)
                continue
            if email:
                seen[email.lower()] = row_idx
            leads.append(self._lead(row_idx, name, source_name))
            accepted.append({"row": row_idx, "lead_id": f"L-{row_idx}", "original": original})
        balance = {
            "rows_in": len(rows),
            "accepted": accepted,
            "rejected": rejected,
            "unparsed_refs": unparsed,
        }
        balance["unexplained"] = balance["rows_in"] - len(accepted) - len(rejected)
        balance["sha256"] = hashlib.sha256(
            json.dumps(balance, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()
        return leads, balance
