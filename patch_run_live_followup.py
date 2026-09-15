from pathlib import Path
import re

p = Path("scripts/run_live_production_goal.py")
code = p.read_text()

pattern = r"                        # Generate next task from result.*?queue\.add_opportunity\(new_opp\)\n.*?print\(f\"Planner derived next mission: \{new_opp\.opportunity_id\}\"\)"
code = re.sub(pattern, "", code, flags=re.DOTALL)
p.write_text(code)
print("Removed unconditional follow-up.")
