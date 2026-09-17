files = [
    'scripts/intake_dispatcher.py',
    'scripts/queue_processor.py',
    'scripts/run_autonomous_loop.py',
    'scripts/run_autonomous_supervisor.py'
]

import os
for f in files:
    with open(f, 'r', encoding='utf-8') as file:
        content = file.read()
    
    content = content.replace("import sys\nprint(\"Disabled in favor of OS-owned Courier Motor.\")\nsys.exit(1)\n", "")
    content = content.replace("import sys\nprint('Disabled in favor of OS-owned Courier Motor.')\nsys.exit(1)\n", "")
    
    if 'from __future__ import annotations' in content:
        parts = content.split('from __future__ import annotations\n', 1)
        new_content = parts[0] + 'from __future__ import annotations\n\nif __name__ == "__main__":\n    import sys\n    print("Disabled in favor of OS-owned Courier Motor.")\n    sys.exit(1)\n' + parts[1]
    else:
        new_content = 'if __name__ == "__main__":\n    import sys\n    print("Disabled in favor of OS-owned Courier Motor.")\n    sys.exit(1)\n' + content
        
    with open(f, 'w', encoding='utf-8') as file:
        file.write(new_content)
