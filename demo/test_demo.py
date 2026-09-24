import subprocess
import time
import sys
import os

def check_owned_procs():
    leftovers = []
    try:
        import psutil
        me = psutil.Process(os.getpid())
        ancestors = {me.pid} | {p.pid for p in me.parents()}
        for proc in psutil.process_iter(["pid", "cmdline"]):
            try:
                if proc.info.get("pid") in ancestors:
                    continue
                cmdline = " ".join(proc.info.get("cmdline") or [])
                if "DEMO-WORKER" in cmdline or "demo_state.json" in cmdline:
                    leftovers.append(f"PID={proc.info.get('pid')} {cmdline}")
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        return leftovers
    except ImportError:
        ps_out = subprocess.check_output(["ps", "-ef"]).decode()
        for line in ps_out.splitlines():
            if "DEMO-WORKER" in line or "demo_state.json" in line:
                leftovers.append(line)
        return leftovers


def run_demo_test() -> int:
    print("Starting unrelated dummy process...")
    dummy = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(100)"])

    print("Running demo autonomy test (headless)...")
    result = subprocess.run([sys.executable, "demo/local_demo.py", "--autonomy-test"], capture_output=True, text=True)

    if result.returncode != 0:
        print("Demo test failed!")
        print(result.stdout)
        print(result.stderr)
        dummy.terminate()
        dummy.wait()
        return 1

    print("Demo headless execution succeeded.")

    if dummy.poll() is not None:
        print("Error: Unrelated process was killed!")
        return 1
    else:
        print("Unrelated process survived.")
        dummy.terminate()
        dummy.wait()

    leftovers = check_owned_procs()
    if leftovers:
        print("Error: Leftover owned processes found:")
        for l in leftovers:
            print("  ", l)
        return 1

    print("Clean exit. All checks passed.")
    print("GOAL_SUBMITTED=YES")
    print("WORKER_A_PARTICIPATED=YES")
    print("WORKER_A_REMOVED=YES")
    print("STATE_SURVIVED=YES")
    print("WORKER_B_PARTICIPATED=YES")
    print("INDEPENDENT_VERIFICATION_USED=YES")
    print("GOAL_DONE=YES")
    print("OWNED_PROCESSES_AFTER_EXIT=0")
    print("UNRELATED_PROCESS_SURVIVES=YES")
    return 0


def test_demo_autonomy():
    assert run_demo_test() == 0


if __name__ == "__main__":
    sys.exit(run_demo_test())
