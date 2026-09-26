import os
import sys
import shutil
import subprocess
import time
import zipfile
import json
from pathlib import Path

def run_proof():
    print("[Proof W36] Starting W36 INSTALL / UPDATE / RESTART SAFETY Proof...")
    
    workspace = Path(os.getcwd())
    server_app = workspace / "server" / "app.py"
    
    # Create isolated app dir for update test to avoid blowing up the real repo
    test_app_dir = workspace / "w36_test_app"
    if test_app_dir.exists():
        shutil.rmtree(test_app_dir)
    test_app_dir.mkdir()
    
    scripts_dir = test_app_dir / "scripts"
    scripts_dir.mkdir()
    
    # Copy necessary scripts
    shutil.copy2(workspace / "scripts" / "update_courier.py", scripts_dir / "update_courier.py")
    shutil.copy2(workspace / "scripts" / "product_health_check.py", scripts_dir / "product_health_check.py")
    
    # Create mock version
    (test_app_dir / "version.txt").write_text("1.0.0")
    
    # Create mock credentials/state
    state_dir = test_app_dir / "state"
    state_dir.mkdir()
    now = time.time()
    mock_state = {"goals":{}, "tasks":{}, "workers": {"mock_verifier": {"last_heartbeat": now}}}
    (state_dir / "central_state.json").write_text(json.dumps(mock_state))
    
    print("[Proof W36] Setting up mock server for health check...")
    server_env = os.environ.copy()
    server_env["COURIER_STATE_FILE"] = str(state_dir / "central_state.json")
    server_env["COURIER_API_KEY"] = "test-key"
    server_env["FLASK_APP"] = str(server_app)
    
    server_proc = subprocess.Popen(
        [sys.executable, "-m", "flask", "run", "--port", "8080"],
        env=server_env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT
    )
    time.sleep(3) # Wait for server
    
    print("[Proof W36] Creating malicious/failing update package...")
    fail_zip = workspace / "w36_fail.zip"
    with zipfile.ZipFile(fail_zip, "w") as z:
        z.writestr("version.txt", "2.0.0")
        z.writestr("scripts/product_health_check.py", "import sys\nsys.exit(1) # force failure")
        
    print("[Proof W36] Running update that should rollback...")
    res_fail = subprocess.run(
        [sys.executable, str(scripts_dir / "update_courier.py"), str(fail_zip)],
        cwd=str(test_app_dir),
        capture_output=True, text=True,
        env=server_env
    )
    print(res_fail.stdout)
    
    print("[Proof W36] Verifying rollback...")
    ver = (test_app_dir / "version.txt").read_text()
    if ver != "1.0.0":
        print("[Proof W36] Rollback failed, version is", ver)
        server_proc.terminate()
        sys.exit(1)
        
    print("[Proof W36] Creating successful update package...")
    succ_zip = workspace / "w36_succ.zip"
    with zipfile.ZipFile(succ_zip, "w") as z:
        z.writestr("version.txt", "2.0.0")
        
    print("[Proof W36] Running successful update...")
    res_succ = subprocess.run(
        [sys.executable, str(scripts_dir / "update_courier.py"), str(succ_zip)],
        cwd=str(test_app_dir),
        capture_output=True, text=True,
        env=server_env
    )
    print(res_succ.stdout)
    
    ver2 = (test_app_dir / "version.txt").read_text()
    if ver2 != "2.0.0":
        print("[Proof W36] Update failed, version is", ver2)
        print("\n--- Health check output ---")
        hc_res = subprocess.run([sys.executable, str(scripts_dir / "product_health_check.py")], cwd=str(test_app_dir), capture_output=True, text=True, env=server_env)
        print(hc_res.stdout, hc_res.stderr)
        server_proc.terminate()
        sys.exit(1)
        
    state_content = (test_app_dir / "state" / "central_state.json").read_text()
    if "goals" not in state_content:
        print("[Proof W36] State did not survive update!")
        server_proc.terminate()
        sys.exit(1)
        
    print("[Proof W36] PASS.")
    server_proc.terminate()

if __name__ == "__main__":
    run_proof()
