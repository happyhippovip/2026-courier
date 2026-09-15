from pathlib import Path
import re

p = Path("scripts/router_dispatch_codex.py")
code = p.read_text()

# Fix indentation for lines starting with queue = and opp = etc
lines = code.split('\n')
for i in range(len(lines)):
    if lines[i].startswith("queue = OpportunityQueue(repo_dir=COURIER_DIR)"):
        # We know it starts at 65
        for j in range(i, i+30):
            if lines[j].startswith("    # ── 3."):
                break
            if len(lines[j].strip()) > 0:
                lines[j] = "    " + lines[j]

code = "\n".join(lines)
p.write_text(code)
