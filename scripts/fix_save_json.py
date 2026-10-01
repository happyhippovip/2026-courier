import os
import re
from pathlib import Path

files = [
    'build_channel_workflow_tasks.py',
    'resource_policy.py',
    'run_demo_workflow.py',
    'run_content_production_pipeline.py',
    'run_codex_bridge.py',
    'run_bodyguards.py',
    'run_antigravity_bridge.py',
]

def replace_save_json(filepath):
    path = Path(filepath)
    content = path.read_text(encoding='utf-8')
    
    # regex to match save_json definition
    pattern = re.compile(r'def save_json\(path: Path, .*?\).*?temp\.replace\(path\)\n', re.DOTALL)
    
    def repl(m):
        orig = m.group(0)
        # extract the signature
        sig_match = re.match(r'(def save_json\(path: Path, [^:]+:\s*[^)]+\)\s*->\s*None:)', orig)
        if not sig_match:
            return orig
        sig = sig_match.group(1)
        
        # extract the dumps part
        dumps_match = re.search(r'temp\.write_text\((json\.dumps\([^)]+\)), encoding="utf-8"\)', orig)
        if not dumps_match:
            # Maybe data without dumps
            dumps_match = re.search(r'temp\.write_text\(([^,]+), encoding="utf-8"\)', orig)
            if not dumps_match:
                return orig
        dumps_expr = dumps_match.group(1)
        
        new_impl = f'''{sig}
    import os
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(f".tmp.{{os.getpid()}}")
    try:
        temp.write_text({dumps_expr}, encoding="utf-8")
        temp.replace(path)
    finally:
        try:
            if temp.exists():
                temp.unlink()
        except OSError:
            pass
'''
        return new_impl
    
    new_content = pattern.sub(repl, content)
    if new_content != content:
        path.write_text(new_content, encoding='utf-8')
        print(f'Updated {filepath}')
    else:
        print(f'No change in {filepath}')

for f in files:
    replace_save_json(f)
