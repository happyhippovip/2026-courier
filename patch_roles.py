import re
with open("scripts/run_bodyguards.py", "r") as f:
    content = f.read()

patch = """        # Check valid temporary role
        if temporary_role not in ALLOWED_TEMP_ROLES:
            raise ValueError(f"Invalid temporary role {temporary_role}")

        # Check required capabilities"""
        
content = content.replace("        # Check required capabilities", patch)
with open("scripts/run_bodyguards.py", "w") as f:
    f.write(content)
