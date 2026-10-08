#!/usr/bin/env python3
"""Spreadsheet Cleanup Sample (RV-09).

Demonstrates using courier_runtime.workbook to clean up a messy spreadsheet.
1. Creates a messy fixture.
2. Reads the cells.
3. Plans changes (trimming spaces, fixing name capitalization).
4. Applies changes and prints the receipt.
"""
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from courier_runtime.workbook import make_fixture, read_cells, apply

def main():
    sample_path = "messy_sample.xlsx"
    
    # 1. Create a messy fixture
    messy_data = {
        "A1": "Name", "B1": "Phone", "C1": "Email", "D1": "Formula",
        "A2": " john doe ", "B2": "0151-1234567", "C2": " john@example.com", "D2": "=SUM(1, 2)",
        "A3": "JANE SMITH", "B3": "+49 151 7654321", "C3": "jane.smith@example.com ", "D3": "=A3",
        "A4": "alice", "B4": "0049151000000", "C4": "alice@example.com", "D4": "Keep me untouched"
    }
    
    print(f"Creating messy fixture at {sample_path}...")
    make_fixture(sample_path, messy_data)
    
    # 2. Read the cells
    current = read_cells(sample_path)
    
    # 3. Plan the changes (Business Logic)
    changes = {}
    for ref, value in current.items():
        if isinstance(value, str) and not value.startswith("="):
            col = "".join([c for c in ref if c.isalpha()])
            row = "".join([c for c in ref if c.isdigit()])
            if row == "1":
                continue # Skip header
            
            clean_val = value.strip()
            
            # Fix Names (Column A)
            if col == "A":
                clean_val = clean_val.title()
                
            # Normalize Phone (Column B)
            elif col == "B":
                clean_val = clean_val.replace(" ", "").replace("-", "")
                if clean_val.startswith("0049"):
                    clean_val = "+49" + clean_val[4:]
                elif clean_val.startswith("0"):
                    clean_val = "+49" + clean_val[1:]
                    
            # Email (Column C)
            elif col == "C":
                clean_val = clean_val.lower()
                
            if clean_val != value:
                changes[ref] = clean_val
                
    print(f"\nPlanned changes: {len(changes)} cells need cleanup.")
    
    # 4. Apply changes
    print("\nApplying changes via courier_runtime.workbook...")
    receipt = apply(sample_path, changes, grant_id="grant_demo_123")
    
    print("\nReceipt:")
    print(json.dumps(receipt, indent=2))
    
    print("\nDone! The fixture is removed next; re-run to see the receipt again.")

    # Cleanup fixture
    os.remove(sample_path)

if __name__ == "__main__":
    main()
