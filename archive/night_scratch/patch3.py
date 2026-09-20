import sys

content = open("tests/test_tomato_two_torture.py").read()

content = content.replace(
    'canary_seq1_abs = str(Path.home() / ".courier_runtime" / canary_seq1)',
    ''
).replace(
    'canary_seq2_abs = str(Path.home() / ".courier_runtime" / canary_seq2)',
    ''
).replace(
    '"artifacts": [canary_seq2_abs]',
    '"artifacts": [canary_seq2]'
).replace(
    'cleanup_file(canary_seq1_abs)',
    'cleanup_file(canary_seq1)'
).replace(
    'cleanup_file(canary_seq2_abs)',
    'cleanup_file(canary_seq2)'
).replace(
    'cwd=str(REPO_ROOT),',
    'cwd=str(Path.home() / ".courier_runtime"),'
)

# And update cleanup_file to check Path.home() / ".courier_runtime"
content = content.replace(
    'def cleanup_file(filename):',
    'def cleanup_file(filename):\n    p = Path.home() / ".courier_runtime" / filename\n    if p.exists(): p.unlink()\n    return'
)

open("tests/test_tomato_two_torture.py", "w").write(content)
