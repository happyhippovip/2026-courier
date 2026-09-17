import re

with open("scripts/courier_github_dispatcher.py", "r") as f:
    code = f.read()

code = code.replace("subprocess.Popen([python_bin, \"scripts/github_worker_adapter.py\", tmp_file])", 
"""p = subprocess.Popen([python_bin, "scripts/github_worker_adapter.py", tmp_file])
                    active_procs.append(p)""")

code = code.replace("while True:",
"""active_procs = []
    while True:
        # Collect zombies
        active_procs = [p for p in active_procs if p.poll() is None]""")

with open("scripts/courier_github_dispatcher.py", "w") as f:
    f.write(code)
