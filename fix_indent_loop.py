from pathlib import Path
import re

p = Path("scripts/mac_result_consumer.py")
code = p.read_text()

pattern = r"                        pass.*?break\n\n                    try:"
replacement = "                        pass\n\n                    try:"
code = re.sub(pattern, replacement, code, flags=re.DOTALL)
p.write_text(code)
print("Fixed!")
