for fn in ["tests/test_DLQ01_trust_boundary.py", "tests/test_DLQ02_freshness_bound.py"]:
    with open(fn, "r") as f:
        c = f.read()
    # Find the bad line and replace it
    lines = c.split("\n")
    for i, line in enumerate(lines):
        if 'hashlib.sha256(b"a' in line:
            lines[i] = '        "artifacts": [{"path": "a.txt", "sha256": hashlib.sha256(b"a\\n").hexdigest()}]'
            if lines[i+1] == '").hexdigest()}]':
                lines[i+1] = ""
    
    with open(fn, "w") as f:
        f.write("\n".join(lines))
