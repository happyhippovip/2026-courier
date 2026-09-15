import os
def process_file(filepath, replacements):
    if not os.path.exists(filepath):
        return
    with open(filepath, 'r') as f:
        content = f.read()
    
    for old, new in replacements.items():
        content = content.replace(old, new)
        
    with open(filepath, 'w') as f:
        f.write(content)

codex_replacements = {
    "if auth:\n        success, gen, err = auth.acquire_scopes(": "if auth:\n        success, gen, err = auth.acquire_scopes(",
    "else:\n        success, gen, err = True, 1, ''\n    if False: # dummy to balance syntax": "else:\n        success, gen, err = False, 0, 'CanonicalAuthority is missing; failing closed as required.'\n    if False: # dummy"
}
process_file("scripts/run_codex_bridge.py", codex_replacements)
process_file("scripts/render_godot_movie.py", codex_replacements)
