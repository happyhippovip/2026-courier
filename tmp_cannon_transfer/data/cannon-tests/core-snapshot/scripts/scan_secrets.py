import os
import re
import sys

# We will scan for typical secret formats but ignore our redactor itself and testing mocks.
# Let's search for "dev-secret-key" (unless it's in redaction files/tests where we explicitly mock it).

FORBIDDEN = [
    r'([A-Za-z0-9_]*SECRET[A-Za-z0-9_]*\s*=\s*[\'"][A-Za-z0-9]{16,}[\'"])',
    r'(api_key\s*=\s*[\'"][A-Za-z0-9]{16,}[\'"])',
    # We will block plaintext "dev-secret-key" in files other than docs or test files
]

def scan_file(filepath):
    # skip this file and the redactor/tests
    if 'scan_secrets.py' in filepath: return []
    if 'test_' in filepath: return []
    if 'redaction.py' in filepath: return []
    if '.git' in filepath or '__pycache__' in filepath or 'egg-info' in filepath or '.archive' in filepath: return []
    if not filepath.endswith('.py') and not filepath.endswith('.json') and not filepath.endswith('.bat') and not filepath.endswith('.ps1'):
        return []

    violations = []
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
            if 'dev-secret-key' in content or 'test-api-key' in content:
                violations.append(f"Found placeholder default secret string in {filepath}")
            
            for pat in FORBIDDEN:
                if re.search(pat, content):
                    violations.append(f"Found hardcoded credential pattern in {filepath}")
    except Exception:
        pass
    return violations

def run_scan(root_dir='.'):
    all_violations = []
    for dirpath, _, filenames in os.walk(root_dir):
        for f in filenames:
            v = scan_file(os.path.join(dirpath, f))
            all_violations.extend(v)
    return all_violations

if __name__ == '__main__':
    v = run_scan()
    if v:
        for val in v:
            print(val)
        sys.exit(1)
    print("No hardcoded secrets found.")
