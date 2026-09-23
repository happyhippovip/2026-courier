import pytest
import os
import re
from pathlib import Path

def test_a5_no_sandbox_bypass_flags_in_source():
    root = Path(__file__).parent.parent
    
    # We scan all .py files in scripts, app, pre_courier_muse
    directories_to_scan = [root / "scripts", root / "app", root / "pre_courier_muse"]
    
    forbidden = [
        "--yolo",
        "--disable-sandbox",
        "--dangerously-skip-permissions",
        "--dangerously-disable-permissions"
    ]
    
    violations = []
    
    for d in directories_to_scan:
        if not d.exists():
            continue
        for p in d.rglob("*.py"):
            text = p.read_text(encoding="utf-8")
            # We skip comments!
            lines = text.split("\n")
            for i, line in enumerate(lines):
                # strip comments (naive but works for string literals)
                if "#" in line:
                    line = line.split("#")[0]
                
                for flag in forbidden:
                    if flag in line:
                        violations.append(f"{p.name}:{i+1} contains {flag}")
                        
    assert not violations, "Found sandbox bypass flags: " + ", ".join(violations)

