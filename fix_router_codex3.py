from pathlib import Path
import re

p = Path("scripts/router_dispatch_codex.py")
code = p.read_text()

# Strip lines and add exactly 4 spaces
lines = code.split('\n')
for i in range(len(lines)):
    if lines[i].strip().startswith("queue = OpportunityQueue(repo_dir=COURIER_DIR)"):
        # We know it starts here
        for j in range(i, i+30):
            if lines[j].strip().startswith("# ── 3."):
                break
            if len(lines[j].strip()) > 0:
                lines[j] = "    " + lines[j].strip()
                if lines[j].strip() == "else:":
                    pass # it should be 4 spaces
                elif lines[j].strip().startswith("dedupe_hash") or lines[j].strip().startswith("opp =") or lines[j].strip().startswith("queue.add_opportunity") or lines[j].strip().startswith("print("):
                    if lines[j].strip().startswith("print(f\"[STEP 2] Opportunity loaded"):
                        lines[j] = "        " + lines[j].strip()
                    elif lines[j].strip().startswith("queue.add_opportunity") or lines[j].strip().startswith("print(f\"[STEP 2] Opportunity injected"):
                        lines[j] = "        " + lines[j].strip()
                    elif lines[j].strip().startswith("opp = Opportunity("):
                        lines[j] = "        " + lines[j].strip()
                    elif lines[j].strip().startswith("dedupe_hash ="):
                        lines[j] = "        " + lines[j].strip()

code = "\n".join(lines)
p.write_text(code)
