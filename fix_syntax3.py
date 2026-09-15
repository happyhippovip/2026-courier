import re
with open("scripts/render_godot_movie.py", "r") as f:
    content = f.read()

content = re.sub(r'except ImportError:\n\s*\n', 'except ImportError:\n    pass\n\n', content)
block_to_replace = """    if False: # dummy
        owner_id=owner_id,
        task_id=task_id,
        scopes=target_scopes,
    )"""
content = content.replace(block_to_replace, "")

with open("scripts/render_godot_movie.py", "w") as f:
    f.write(content)
