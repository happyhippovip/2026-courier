from pathlib import Path
adapters_path = Path("scripts/courier_real_worker_adapters.py")
code = adapters_path.read_text()
code = code.replace('"PROJECT_PATH": "C:\\\\\\\\Dev\\\\\\\\Windows-AI-OS",', '"PROJECT_PATH": r"C:\\Dev\\Windows-AI-OS",')
adapters_path.write_text(code)
print("Fixed project path")
