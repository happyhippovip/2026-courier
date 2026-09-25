import re
with open("tests/test_tomato_two_torture.py", "r") as f:
    c = f.read()

replacement = """    config_path = REPO_ROOT / "scripts/mac_worker/config.json"
    orig_config = None
    if config_path.exists():
        with open(config_path, "r") as f:
            orig_config = f.read()
            
    with open(config_path, "w") as f:
        json.dump({"COURIER_SERVER": "http://127.0.0.1:8081"}, f)
        
    try:
        subprocess.check_call(["launchctl", "stop", "com.courier.mac_worker"])
        time.sleep(1)
        subprocess.check_call(["launchctl", "start", "com.courier.mac_worker"])
    except Exception as e:
        print("Failed to restart launchd worker:", e)
        
    server_proc = subprocess.Popen([python_exe, "-m", "server.app"], env=env, cwd=str(REPO_ROOT))
    
    verifier_proc = subprocess.Popen([python_exe, str(REPO_ROOT / "scripts/courier_verifier.py")], env=env, cwd=str(REPO_ROOT))
    time.sleep(3)
    yield
    
    if orig_config is not None:
        with open(config_path, "w") as f:
            f.write(orig_config)
    else:
        if config_path.exists():
            config_path.unlink()
            
    try:
        subprocess.check_call(["launchctl", "stop", "com.courier.mac_worker"])
        time.sleep(1)
        subprocess.check_call(["launchctl", "start", "com.courier.mac_worker"])
    except Exception:
        pass
"""

# We need to replace the body of start_server safely.
# Let's find the start of the fixture body.
c = re.sub(
    r"    # waitress is missing, so let's start the server and verifier manually here\n.*?yield\n",
    replacement,
    c,
    flags=re.DOTALL
)

with open("tests/test_tomato_two_torture.py", "w") as f:
    f.write(c)

