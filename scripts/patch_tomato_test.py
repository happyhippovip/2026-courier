import re

with open("tests/test_tomato_two_torture.py", "r") as f:
    code = f.read()

# 1. Change SERVER_URL to 8081
code = re.sub(r'SERVER_URL = "http://127.0.0.1:808[05]"', 'SERVER_URL = "http://127.0.0.1:8081"', code)

# 2. Change env["PORT"] to 8081
code = re.sub(r'env\["PORT"\] = "808[05]"', 'env["PORT"] = "8081"', code)

# 3. Add config update to fixture
setup_code = """    import json
    config_path = REPO_ROOT / "scripts/mac_worker/config.json"
    if config_path.exists():
        with open(config_path, "r") as cf:
            orig_config = json.load(cf)
        new_config = orig_config.copy()
        new_config["COURIER_SERVER"] = "http://127.0.0.1:8081/"
        with open(config_path, "w") as cf:
            json.dump(new_config, cf)
        try:
            subprocess.check_call(["launchctl", "stop", "com.courier.mac_worker"])
        except Exception:
            pass
"""
# Insert before starting the server
code = code.replace('    server_proc = subprocess.Popen([python_exe, "-m", "server.app"], env=env, cwd=str(REPO_ROOT))', 
                    setup_code + '\n    server_proc = subprocess.Popen([python_exe, "-m", "server.app"], env=env, cwd=str(REPO_ROOT))')

# 4. Add teardown to fixture
teardown_code = """
    if config_path.exists() and 'orig_config' in locals():
        with open(config_path, "w") as cf:
            json.dump(orig_config, cf)
        try:
            subprocess.check_call(["launchctl", "stop", "com.courier.mac_worker"])
        except Exception:
            pass
"""
# Insert after verifier_proc.wait()
code = code.replace('        verifier_proc.wait()\n', '        verifier_proc.wait()\n' + teardown_code)

with open("tests/test_tomato_two_torture.py", "w") as f:
    f.write(code)
print("Patched.")
