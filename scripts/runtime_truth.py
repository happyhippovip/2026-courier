import subprocess
import os
import json
import sys

def get_sha(cwd):
    try:
        if os.path.exists(os.path.join(cwd, '.git')):
            return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=cwd, stderr=subprocess.DEVNULL, timeout=15).decode().strip()
        elif os.path.exists(os.path.join(cwd, '.deployed_sha')):
            with open(os.path.join(cwd, '.deployed_sha')) as f:
                return f.read().strip()
        else:
            # DO NOT INFER
            return "UNKNOWN_NO_GIT_NO_SHA_FILE"
    except Exception:
        return "ERROR"

def get_remote_sha(cwd):
    try:
        # The checked-out branch's upstream is the relevant release truth.
        # origin/HEAD may point at main while a release branch is deployed.
        return subprocess.check_output(
            ["git", "rev-parse", "--verify", "@{upstream}"],
            cwd=cwd,
            stderr=subprocess.DEVNULL,
            timeout=15,
        ).decode().strip()
    except Exception:
        return "UNKNOWN"


def select_server_process(ps_output):
    """Return the actual Courier Central process, never a worker process."""
    for line in ps_output.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        parts = stripped.split(maxsplit=1)
        if len(parts) != 2 or not parts[0].isdigit():
            continue
        command = parts[1].replace("\\", "/")
        if (
            " -m server.app" in command
            or "/server/run_waitress.py" in command
        ):
            return parts[0], parts[1]
    return None

def get_runtime_info():
    info = {
        "CANONICAL_HEAD_SHA": "UNKNOWN",
        "REMOTE_HEAD_SHA": "UNKNOWN",
        "TESTED_SHA": "UNKNOWN",
        "DEPLOYED_SHA": "UNKNOWN",
        "ACTUAL_SERVING_RUNTIME_SHA": "UNKNOWN",
        "ACCEPTANCE_BOUND_SHA": "UNKNOWN",
        "RUNTIME_PROCESS_IDENTITY": "UNKNOWN",
        "RUNTIME_LISTENER": "NONE",
        "RUNTIME_HEALTH": "UNKNOWN"
    }
    
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    info["CANONICAL_HEAD_SHA"] = get_sha(repo_root)
    info["REMOTE_HEAD_SHA"] = get_remote_sha(repo_root)
    
    ledger_path = os.path.join(repo_root, "agent_handoff_ledger.json")
    if os.path.exists(ledger_path):
        try:
            with open(ledger_path) as f:
                ledger = json.load(f)
            info["TESTED_SHA"] = ledger.get("record", {}).get("CURRENT_SHA", "UNKNOWN")
            guard = ledger.get("acceptance_guard", {})
            if "evidence" in guard and len(guard["evidence"]) > 0:
                info["ACCEPTANCE_BOUND_SHA"] = guard["evidence"][0].get("evidence_sha", "UNKNOWN")
            else:
                info["ACCEPTANCE_BOUND_SHA"] = guard.get("binding", {}).get("current_sha", "UNKNOWN")
        except Exception:
            pass
            
    # Process queries using ps (bounded: one blocked query must not stall truth)
    try:
        out = subprocess.check_output(["ps", "-eo", "pid,command"], stderr=subprocess.DEVNULL, timeout=10).decode()
        selected = select_server_process(out)
        if selected:
                pid, cmd = selected
                
                info["RUNTIME_PROCESS_IDENTITY"] = f"PID:{pid} EXE:{cmd.split()[0]}"
                
                try:
                    lsof_out = subprocess.check_output(["lsof", "-p", pid, "-a", "-d", "cwd", "-F", "n"], stderr=subprocess.DEVNULL, timeout=10).decode()
                    cwd = ""
                    for lline in lsof_out.splitlines():
                        if lline.startswith('n'):
                            cwd = lline[1:]
                except Exception:
                    cwd = ""
                
                info["DEPLOYED_SHA"] = get_sha(cwd)
                info["ACTUAL_SERVING_RUNTIME_SHA"] = info["DEPLOYED_SHA"]
                
                # Check listener
                listener = "NONE"
                try:
                    lsof_i = subprocess.check_output(["lsof", "-p", pid, "-a", "-i", "-P", "-n"], stderr=subprocess.DEVNULL, timeout=10).decode()
                    if lsof_i:
                        lines = lsof_i.splitlines()
                        if len(lines) > 1:
                            listener = lines[-1].split()[-2]
                except Exception:
                    pass
                info["RUNTIME_LISTENER"] = listener
                
                # Check health
                health_status = "UNKNOWN"
                health_script = os.path.join(cwd, "scripts", "product_health_check.py")
                if not os.path.exists(health_script):
                    health_script = os.path.join(repo_root, "scripts", "product_health_check.py")
                if os.path.exists(health_script):
                    try:
                        res = subprocess.run([sys.executable, health_script], stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=os.environ.copy(), timeout=30)
                        if res.returncode == 0 and b"HEALTHY" in res.stdout:
                            health_status = "HEALTHY"
                        else:
                            health_status = "DEGRADED"
                    except Exception:
                        pass
                info["RUNTIME_HEALTH"] = health_status
                
    except Exception as e:
        pass
            
    return info

if __name__ == "__main__":
    print(json.dumps(get_runtime_info(), indent=2))
