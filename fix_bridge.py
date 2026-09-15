from pathlib import Path

p = Path("scripts/run_codex_bridge.py")
code = p.read_text()

# Remove the rigid checks that prevent Codex from running locally
code = code.replace("""    if job.get("target_host") != "DESKTOP-JDPRUGR":
        errors.append("TARGET_HOST_INVALID")
    if job.get("project_path") != r"C:\\Dev\\Windows-AI-OS":
        errors.append("PROJECT_PATH_INVALID")""", """    # Relaxed validation to allow Mac-local execution
    pass""")

p.write_text(code)
print("Bridge patched.")
