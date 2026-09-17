import os
import re

for root, dirs, files in os.walk('.'):
    if '.git' in root or '.venv' in root or 'node_modules' in root:
        continue
    for name in files:
        if name.endswith('.py') and name != 'app.py' and name != 'fix_all.py':
            path = os.path.join(root, name)
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    content = f.read()
            except UnicodeDecodeError:
                with open(path, 'r', encoding='utf-16') as f:
                    content = f.read()
            
            new_content = content.replace(
                "'server/state/central_state.json'", 
                "os.environ.get('COURIER_STATE_FILE', r'C:\ProgramData\Courier\central_state.json')"
            )
            new_content = new_content.replace(
                '"server/state/central_state.json"', 
                "os.environ.get('COURIER_STATE_FILE', r'C:\ProgramData\Courier\central_state.json')"
            )
            
            if new_content != content:
                if 'os.environ' in new_content and not re.search(r'^import os$', new_content, re.MULTILINE):
                    new_content = "import os\n" + new_content
                try:
                    with open(path, 'w', encoding='utf-8') as f:
                        f.write(new_content)
                except Exception:
                    with open(path, 'w', encoding='utf-16') as f:
                        f.write(new_content)
