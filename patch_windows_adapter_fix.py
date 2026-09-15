from pathlib import Path

adapters_path = Path("scripts/courier_real_worker_adapters.py")
code = adapters_path.read_text()

code = code.replace('dispatcher_path = Path(root).resolve() / "scripts" / "mac_windows_dispatcher.py"', 'dispatcher_path = Path(root or "/Users/user/Downloads/2026-courier").resolve() / "scripts" / "mac_windows_dispatcher.py"')

adapters_path.write_text(code)
print("Windows adapter fixed.")
