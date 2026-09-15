from pathlib import Path

p = Path("scripts/courier_real_worker_adapters.py")
code = p.read_text()

old = '''            dispatcher_path = Path(root or __file__).resolve().parent.parent / "scripts" / "mac_windows_dispatcher.py"'''
new = '''            dispatcher_path = Path(root or Path(__file__).resolve().parent.parent).resolve() / "scripts" / "mac_windows_dispatcher.py"'''

code = code.replace(old, new)
p.write_text(code)
print("Patched dispatcher path.")
