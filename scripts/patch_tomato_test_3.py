import re

with open("tests/test_tomato_two_torture.py", "r") as f:
    code = f.read()

new_setup_code = """    import json
    config_path = REPO_ROOT / "scripts/mac_worker/config.json"
    if config_path.exists():
        with open(config_path, "r") as cf:
            orig_config = json.load(cf)
        new_config = orig_config.copy()
        new_config["COURIER_SERVER"] = "http://127.0.0.1:8081/"
        new_config["COURIER_API_KEY"] = "local-dev-key-123"
        with open(config_path, "w") as cf:
            json.dump(new_config, cf)
            
        try:
            # Backup keychain server URL if it exists
            orig_keychain_srv = subprocess.check_output(["security", "find-generic-password", "-a", "courier_worker", "-s", "courier_server_url", "-w"]).decode().strip()
        except Exception:
            orig_keychain_srv = None
            
        try:
            subprocess.check_call(["security", "delete-generic-password", "-a", "courier_worker", "-s", "courier_server_url"])
        except Exception:
            pass

        try:
            subprocess.check_call(["launchctl", "stop", "com.courier.mac_worker"])
        except Exception:
            pass
"""

new_teardown_code = """
    if config_path.exists() and 'orig_config' in locals():
        with open(config_path, "w") as cf:
            json.dump(orig_config, cf)
            
        if orig_keychain_srv:
            try:
                subprocess.check_call(["security", "add-generic-password", "-a", "courier_worker", "-s", "courier_server_url", "-w", orig_keychain_srv, "-U"])
            except Exception:
                pass
                
        try:
            subprocess.check_call(["launchctl", "stop", "com.courier.mac_worker"])
        except Exception:
            pass
"""

# We'll just replace the lines we injected earlier in patch 2
code = re.sub(r'    import json\n    config_path = REPO_ROOT / "scripts/mac_worker/config.json"\n.*?            pass\n', new_setup_code, code, flags=re.DOTALL)
code = re.sub(r'\n    if config_path\.exists.*?            pass\n', new_teardown_code, code, flags=re.DOTALL)

with open("tests/test_tomato_two_torture.py", "w") as f:
    f.write(code)
print("Patched 3.")
