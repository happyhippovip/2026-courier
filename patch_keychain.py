with open("tests/test_tomato_two_torture.py", "r") as f:
    content = f.read()

bad = """        with open(config_path, "w") as f:
            json.dump(test_config, f)
            
        try:
            subprocess.check_call(["launchctl", "stop", "com.courier.mac_worker"])"""

good = """        with open(config_path, "w") as f:
            json.dump(test_config, f)
            
        try:
            subprocess.check_call(["security", "add-generic-password", "-a", "courier_worker", "-s", "courier_server_url", "-w", "http://127.0.0.1:8081", "-U"])
        except Exception as e:
            pass
            
        try:
            subprocess.check_call(["launchctl", "stop", "com.courier.mac_worker"])"""

content = content.replace(bad, good)

bad2 = """        with open(config_path, "w") as cf:
            json.dump(orig_config, cf)
                
        try:
            subprocess.check_call(["launchctl", "stop", "com.courier.mac_worker"])"""

good2 = """        with open(config_path, "w") as cf:
            json.dump(orig_config, cf)
            
        try:
            subprocess.check_call(["security", "add-generic-password", "-a", "courier_worker", "-s", "courier_server_url", "-w", "http://127.0.0.1:8080/", "-U"])
        except Exception:
            pass
                
        try:
            subprocess.check_call(["launchctl", "stop", "com.courier.mac_worker"])"""

content = content.replace(bad2, good2)

with open("tests/test_tomato_two_torture.py", "w") as f:
    f.write(content)
