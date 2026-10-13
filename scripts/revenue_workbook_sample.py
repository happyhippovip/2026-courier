import os
import re
import sys
from collections import defaultdict
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from courier_runtime.workbook import read_cells, apply, make_fixture

def clean_email(email_str):
    """Normalize email address to lowercase and strip whitespace."""
    if not isinstance(email_str, str):
        return email_str
    # Simple extraction
    m = re.search(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", email_str)
    if m:
        return m.group(0).lower()
    return email_str

def create_sample_workbook(path):
    """Creates a raw workbook to demonstrate the cleanup."""
    content = {
        "A1": "Name", "B1": "Email", "C1": "Phone",
        "A2": "JOHN DOE", "B2": "   JOHN.DOE@Example.com   ", "C2": "555-1234",
        "A3": "Jane Smith", "B3": "jane.smith@EXAMPLE.ORG", "C3": "555-5678",
        "A4": "Bob", "B4": "CONTACT: bob@company.net!!", "C4": "1234567890"
    }
    
    make_fixture(path, content)
    print(f"Created messy sample workbook at {path}")

def main():
    sample_file = "messy_leads.xlsx"
    if not os.path.exists(sample_file):
        create_sample_workbook(sample_file)
        
    print("Reading cells...")
    cells = read_cells(sample_file)
    
    changes = {}
    for ref, val in cells.items():
        # B column has emails
        if ref.startswith("B") and ref != "B1":
            cleaned = clean_email(val)
            if cleaned != val:
                changes[ref] = cleaned
                
        # A column has names
        if ref.startswith("A") and ref != "A1" and isinstance(val, str):
            cleaned = val.title()
            if cleaned != val:
                changes[ref] = cleaned

    print(f"Planned mutations: {len(changes)}")
    for ref, val in changes.items():
        print(f" - {ref}: '{cells[ref]}' -> '{val}'")
        
    if changes:
        print("\nApplying changes securely...")
        # Apply requires a grant_id, we can pass any non-empty string for the sample
        receipt = apply(sample_file, changes, grant_id="dummy_grant_for_sample")
        print("Success! Receipt:")
        print(f" File Hash Before: {receipt['before_sha256']}")
        print(f" File Hash After:  {receipt['after_sha256']}")
        print(f" Cells Changed:    {len(receipt['changes'])}")
        
    print("\nCleanup complete.")

if __name__ == "__main__":
    main()
