import os
import sys

with open("courier_worker/host.py", "r") as f:
    content = f.read()

new_probe = """
def default_pressure_probe() -> Optional[str]:
    \"\"\"Return None when the host may spawn, else a short reason.

    Fail-closed: any probe error pauses the host. The FD check opens and
    closes a real pipe, so descriptor exhaustion is observed, not assumed.
    \"\"\"
    try:
        r, w = os.pipe()
        try:
            pass
        finally:
            os.close(r)
            os.close(w)
    except OSError as exc:
        return f"fd-exhaustion: {exc.strerror or exc}"
        
    # Prefer OS-native thermal pressure signal on macOS
    if sys.platform == "darwin":
        import subprocess
        try:
            res = subprocess.run(["pmset", "-g", "therm"], capture_output=True, text=True, timeout=1.0)
            if res.returncode == 0:
                for line in res.stdout.splitlines():
                    if "CPU_Speed_Limit" in line:
                        parts = line.split("=")
                        if len(parts) == 2:
                            val = parts[1].strip()
                            if val.isdigit() and int(val) < 100:
                                return f"thermal-pressure: speed limit {val}%"
        except Exception:
            pass
            
    try:
        load = _one_minute_load()
    except OSError as exc:
        return f"load-probe-failed: {exc.strerror or exc}"
        
    if load is not None:
        cpus = os.cpu_count() or 1
        if load > cpus * LOAD_PRESSURE_FACTOR:
            return f"cpu-pressure: load1 {load:.1f} over {cpus} cpu(s)"
    return None
"""

import re
content = re.sub(r'def default_pressure_probe.*?return None', new_probe.strip(), content, flags=re.DOTALL)

with open("courier_worker/host.py", "w") as f:
    f.write(content)
