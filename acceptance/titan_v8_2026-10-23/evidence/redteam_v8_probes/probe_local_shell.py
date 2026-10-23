"""Probe: does anything stop a self-declared 0.0 local_shell task from launching a provider CLI?
Provider binaries are STUBS in ./fakebin (PATH is restricted so real CLIs cannot resolve)."""
import os, sys, tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
assert os.environ["PATH"].split(os.pathsep)[0] == str(HERE / "fakebin"), "PATH must start with fakebin"
import shutil
for b in ("codex", "claude", "gemini", "agy"):
    assert shutil.which(b).startswith(str(HERE / "fakebin")), b

from courier_core.controller import cost_admission
from courier_core.verification import adapter_cost_class
from courier_worker import adapter_bridge
from adapters import local_shell

cases = {
    "codex_exec": ["codex", "exec", "hi"],
    "env_claude": ["/usr/bin/env", "claude", "-p", "hi"],
    "python_c": [sys.executable, "-c", "import subprocess; subprocess.run(['gemini','-p','x'])"],
    "sh_c_agy": ["sh", "-c", "agy -p hi"],
}
for name, argv in cases.items():
    params = {"command": argv, "write": "out.txt", "timeout_s": 10, "estimated_cost_eur": 0.0}
    adm = cost_admission(adapter_cost_class("local_shell"), params)
    try:
        adapter_bridge.ADAPTERS["local_shell"](params)
        bridge = "accepted"
    except Exception as exc:
        bridge = f"rejected {exc}"
    wd = tempfile.mkdtemp()
    res = local_shell.run(params, wd)
    ran = (Path(wd) / "out.txt").exists() and "STUB" in (Path(wd) / "out.txt").read_text()
    print(f"{name}: controller_admission={'ADMIT' if adm is None else adm!r} bridge={bridge} "
          f"run={res.outcome} provider_stub_started={ran}")

# HOME inheritance: CLI logins (~/.codex, ~/.claude, ~/.gemini) live under HOME, which the env allowlist passes.
print("HOME_in_INHERITED_ENV:", "HOME" in local_shell.INHERITED_ENV, "USERPROFILE:", "USERPROFILE" in local_shell.INHERITED_ENV)
# missing / bad estimates
for v in (None, float("nan"), float("inf"), True, "0", -1, 10**400, -0.0):
    p = {"command": ["true"]} if v is None else {"command": ["true"], "estimated_cost_eur": v}
    print("estimate", repr(v) if v != 10**400 else "10**400", "->", cost_admission("metered", p) or "ADMIT")
