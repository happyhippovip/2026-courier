from pathlib import Path
p = Path("tests/test_windows_runtime_torture.py")
content = p.read_text()
content = content.replace('"capabilities": ["windows_native"]', '"capabilities": ["windows", "windows_native"]')
p.write_text(content)
