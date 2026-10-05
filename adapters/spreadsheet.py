import re
from courier_runtime.revenue import Lead, PROSPECT
from courier_runtime.workbook import read_cells
from collections import defaultdict

class SpreadsheetAdapter:
    def __init__(self, workbook_path):
        self.workbook_path = workbook_path

    def parse_leads(self, source_name="spreadsheet_import"):
        cells = read_cells(self.workbook_path)
        rows = defaultdict(dict)
        for ref, val in cells.items():
            col = ref[0]
            try:
                row_idx = int(ref[1:])
            except ValueError:
                continue
            if row_idx == 1:
                continue
            rows[row_idx][col] = val

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
                
            lead = Lead(
                lead_id=f"L-{row_idx}",
                organisation=name,
                problem=f"Found in {self.workbook_path}",
                source=source_name,
                state=PROSPECT
            )
            leads.append(lead)
            
        return leads
