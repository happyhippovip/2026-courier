from pathlib import Path
import re

p = Path("scripts/run_live_production_goal.py")
code = p.read_text()

code = code.replace("output_lower = output.lower()", "                        output_lower = output.lower()")
p.write_text(code)
print("Indentation fixed.")
