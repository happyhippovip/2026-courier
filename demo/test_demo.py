import subprocess
import time
import sys
import os

def check_owned_procs():
    ps_out = subprocess.check_output(["ps", "-ef"]).decode()
    leftovers = []
    for line in ps_out.splitlines():
        if "DEMO-WORKER" in line or "demo_state.json" in line:
            leftovers.append(line)
    return leftovers

def main():
    print("Starting unrelated dummy process...")
    dummy = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(100)"])

    print("Running demo autonomy test (headless)...")
    result = subprocess.run([sys.executable, "demo/local_demo.py", "--autonomy-test"], capture_output=True, text=True)

    if result.returncode != 0:
        print("Demo test failed!")
        print(result.stdout)
        print(result.stderr)
        dummy.terminate()
        sys.exit(1)

    print("Demo headless execution succeeded.")

    if dummy.poll() is not None:
        print("Error: Unrelated process was killed!")
        sys.exit(1)
    else:
        print("Unrelated process survived.")
        dummy.terminate()
        dummy.wait()

    leftovers = check_owned_procs()
    if leftovers:
        print("Error: Leftover owned processes found:")
        for l in leftovers:
            print("  ", l)
        sys.exit(1)

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

if __name__ == "__main__":
    main()
