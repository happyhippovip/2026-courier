from pathlib import Path

p = Path("scripts/run_codex_bridge.py")
code = p.read_text()

old_prompt = """        "Perform only read-only repository inspection. Return ONLY a valid JSON object with exact keys: "\n"""
new_prompt = """        "Execute the requested instruction. You may modify the repository. When finished, you MUST return ONLY a valid JSON object with exact keys: "\n"""

code = code.replace(old_prompt, new_prompt)
p.write_text(code)
print("Patched.")
