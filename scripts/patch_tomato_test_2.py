import re

with open("tests/test_tomato_two_torture.py", "r") as f:
    code = f.read()

# Replace the previous setup with a new one that also patches COURIER_API_KEY
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
            subprocess.check_call(["launchctl", "stop", "com.courier.mac_worker"])
        except Exception:
            pass
"""
# We'll just replace the lines we injected earlier:
code = re.sub(r'    import json\n    config_path = REPO_ROOT / "scripts/mac_worker/config.json"\n.*?            pass\n', new_setup_code, code, flags=re.DOTALL)

with open("tests/test_tomato_two_torture.py", "w") as f:
    f.write(code)
print("Patched again.")
