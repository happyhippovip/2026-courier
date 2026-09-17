import re

for file in ["scripts/courier_github_dispatcher.py", "scripts/courier_watchdog.py"]:
    with open(file, "r") as f:
        content = f.read()
    
    content = content.replace("import keyring", "try:\n    import keyring\nexcept ImportError:\n    keyring = None")
    content = content.replace(
        "API_KEY = os.environ.get(\"COURIER_API_KEY\") or keyring.get_password",
        "API_KEY = os.environ.get(\"COURIER_API_KEY\") or (keyring.get_password if keyring else lambda *args: None)"
    )
    
    with open(file, "w") as f:
        f.write(content)
