import re

with open("scripts/courier_safety_dispatcher.py", "r") as f:
    text = f.read()

# I want to replace the `raw_text = ...` line with stripping file extensions and paths
old_raw_text = 'raw_text = " ".join(str(x) for x in (mission.get("goal", ""), mission.get("normalized_task", ""), " ".join(task_parts)))'
new_raw_text = '''raw_text = " ".join(str(x) for x in (mission.get("goal", ""), mission.get("normalized_task", ""), " ".join(task_parts)))
        
        # Strip all file paths / identifiers ending in extensions or containing slashes to avoid false positives
        import re
        raw_text = re.sub(r'\\b[\\w\\.-]+/[\\w\\.-]+\\b', '', raw_text) # strip things like tests/test_deploy.py
        raw_text = re.sub(r'\\b[\\w\\.-]+\\.(?:py|json|md|txt|mjs|js|ts|sh|yaml|yml)\\b', '', raw_text) # strip things like test_deploy.py'''

text = text.replace(old_raw_text, new_raw_text)

with open("scripts/courier_safety_dispatcher.py", "w") as f:
    f.write(text)
