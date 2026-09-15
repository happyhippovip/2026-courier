with open("scripts/run_codex_bridge.py", "r") as f:
    content = f.read()

content = content.replace("except ImportError:\n    \n\nEVENTS_DIR", "except ImportError:\n    pass\n\nEVENTS_DIR")
content = content.replace("except ImportError:\n    \nEVENTS_DIR", "except ImportError:\n    pass\n\nEVENTS_DIR")

with open("scripts/run_codex_bridge.py", "w") as f:
    f.write(content)
