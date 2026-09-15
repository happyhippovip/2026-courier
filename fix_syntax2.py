import re
with open("scripts/run_codex_bridge.py", "r") as f:
    content = f.read()

# Fix the IndentationError
content = re.sub(r'except ImportError:\n\s*\nEVENTS_DIR', 'except ImportError:\n    pass\n\nEVENTS_DIR', content)

# Fix the SyntaxError block
block_to_replace = """    if False: # dummy
        owner_id=owner_id,
        task_id=task_id,
        scopes=target_scopes,
    )"""
content = content.replace(block_to_replace, "")

with open("scripts/run_codex_bridge.py", "w") as f:
    f.write(content)

