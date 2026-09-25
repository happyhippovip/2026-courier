import os
import sys
import subprocess
import time
import psutil

def get_changed_files():
    try:
        diff = subprocess.check_output(["git", "diff", "--name-only", "HEAD"], text=True)
        untracked = subprocess.check_output(["git", "ls-files", "--others", "--exclude-standard"], text=True)
        files = diff.strip().split("\n") + untracked.strip().split("\n")
        return [f for f in files if f and f.endswith(".py")]
    except Exception as e:
        print(f"Failed to get changed files: {e}")
        return []

def map_changes_to_tests(changed_files):
    test_files_to_run = set()
    for f in changed_files:
        if f.startswith("tests/") and "test_" in f:
            test_files_to_run.add(f)
        elif f.startswith("server/"):
            test_files_to_run.update(["tests/test_server_integration_contract.py", "tests/test_event_driven.py"])
        elif f.startswith("scripts/windows_worker"):
            test_files_to_run.update(["tests/test_windows_worker_reliability.py", "tests/test_windows_background.py"])
    return list(test_files_to_run)

def terminate_process_tree(pid):
    try:
        parent = psutil.Process(pid)
        for child in parent.children(recursive=True):
            child.kill()
        parent.kill()
    except psutil.NoSuchProcess:
        pass
    except Exception as e:
        print(f"Error terminating process tree: {e}")

def run_fast_tests(test_files):
    if not test_files:
        print("FAST: No specific test files matched, running core fast tests.")
        test_files = ["tests/test_event_driven.py"]
    
    print(f"FAST: Running relevant tests: {', '.join(test_files)}")
    cmd = [sys.executable, "-m", "pytest", "-m", "fast", "--timeout=20"] + test_files
    
    start = time.time()
    try:
        process = subprocess.Popen(cmd)
        while process.poll() is None:
            if time.time() - start > 25:
                print("FAST: TIMEOUT detected. Terminating process tree.", flush=True)
                terminate_process_tree(process.pid)
                return 1
            time.sleep(0.5)
            
        print(f"FAST: Completed in {time.time() - start:.2f}s")
        return process.returncode
    except Exception as e:
        print(f"FAST: Exception {e}")
        return 1

def launch_background_tests(tier, marker, test_files, timeout):
    print(f"{tier}: Launching background job...")
    log_file = f"logs\\{tier.lower()}_test.log"
    # Use PowerShell Start-Process to completely detach and redirect output
    # without inheriting Python's/Antigravity's file handles
    cmd = [
        "powershell", "-NoProfile", "-Command",
        f"Start-Process -FilePath '{sys.executable}' -ArgumentList '-m pytest -m \"{marker}\" --timeout={timeout}' -RedirectStandardOutput '{log_file}' -RedirectStandardError '{log_file}' -WindowStyle Hidden"
    ]
    subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print(f"{tier}: Background job started.")

def main():
    changed = get_changed_files()
    test_files = map_changes_to_tests(changed)

    print("=== FAST TIER ===")
    rc = run_fast_tests(test_files)
    if rc != 0:
        print("FAST tests failed or timed out. Stopping pipeline.")
        sys.exit(rc)
        
    print("\n=== INTEGRATION TIER ===")
    launch_background_tests("INTEGRATION", "integration", test_files, 60)
    
    print("\n=== DEEP TIER ===")
    launch_background_tests("DEEP", "not fast and not integration", test_files, 300)
    
    print("\nTest pipeline triggered successfully. Courier work can continue.")

if __name__ == "__main__":
    if not os.path.exists("logs"):
        os.makedirs("logs")
    main()
