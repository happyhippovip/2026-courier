import os
import sys
import time
import subprocess
import signal

# Add scripts directory to path to import agent_session_manager
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "scripts"))
import agent_session_manager

def main():
    print("Running Agent Background Task Cleanup Regression Test...")
    
    agent_session_manager.audit_orphans()
    
    print("Starting unrelated control process...")
    control_proc = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(100)"])
    
    print("Starting disposable background monitor processes...")
    monitors = []
    for i in range(3):
        p = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(100)"])
        monitors.append(p)
        
    session_id = "TEST-SESSION-123"
    
    print(f"Registering monitors to session {session_id}...")
    for i, p in enumerate(monitors):
        success = agent_session_manager.register_task(p.pid, session_id, f"test-monitor-{i}")
        if not success:
            print(f"FAIL: Failed to register PID {p.pid}")
            return 1
            
    data = agent_session_manager._load()
    assert len(data.get(session_id, [])) == 3, "Tasks not properly registered"
    
    print("Performing terminal handoff cleanup...")
    killed = agent_session_manager.cleanup_session(session_id)
    print(f"Killed {killed} processes.")
    assert killed == 3, f"Expected to kill 3 processes, killed {killed}"
    
    time.sleep(0.5)
    for p in monitors:
        # Reap the process so it stops being a zombie
        p.poll()
        if p.returncode is None:
            # Let's try waiting
            try:
                p.wait(timeout=1)
            except subprocess.TimeoutExpired:
                p.kill()
                p.wait()
                print(f"FAIL: Owned process {p.pid} is still alive (and leaked)!")
                return 1
            
    try:
        os.kill(control_proc.pid, 0)
        print("PASS: Unrelated control process remains alive.")
    except OSError:
        print("FAIL: Unrelated control process was killed!")
        return 1
        
    control_proc.terminate()
    print("Regression test completed successfully.")
    return 0

def test_agent_background_cleanup():
    assert main() == 0

if __name__ == "__main__":
    sys.exit(main())
