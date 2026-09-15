from pathlib import Path
import re

p = Path("scripts/router_dispatch_codex.py")
code = p.read_text()

# Remove the inner `import json`
code = code.replace("            import json\n", "")

p.write_text(code)
print("Fixed json import.")
