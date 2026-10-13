#!/usr/bin/env python3
import os
import sys
from pathlib import Path
from collections import defaultdict

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from courier_runtime.revenue import Lead, PROSPECT
from courier_runtime.workbook import read_cells

def run_lead_helper(workbook_path: str):
    if not os.path.exists(workbook_path):
        print(f"Error: {workbook_path} not found.")
        sys.exit(1)
        
    print(f"Processing raw leads from {workbook_path}...")
    cells = read_cells(workbook_path)
    
    # Simple heuristic to extract rows (assuming headers in row 1)
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
            
        lead = Lead(
            lead_id=f"L-{row_idx}",
            organisation=name,
            problem=f"Found in {workbook_path}",
            source="spreadsheet_import",
            state=PROSPECT
        )
        leads.append(lead)
        
    print(f"Imported {len(leads)} leads into the Revenue engine as PROSPECTs.")
    for lead in leads:
        print(f" - [{lead.lead_id}] {lead.organisation} (State: {lead.state})")
        
    return leads

if __name__ == "__main__":
    target = "messy_leads.xlsx"
    if len(sys.argv) > 1:
        target = sys.argv[1]
    run_lead_helper(target)
