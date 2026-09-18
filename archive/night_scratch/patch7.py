import sys

content = open("tests/test_tomato_two_torture.py").read()

content = content.replace(
    'assert (REPO_ROOT / canary_seq2).exists()',
    'assert (Path.home() / ".courier_runtime" / canary_seq2).exists()'
).replace(
    'assert (REPO_ROOT / canary_seq1).exists()',
    'assert (Path.home() / ".courier_runtime" / canary_seq1).exists()'
).replace(
    'assert not (REPO_ROOT / canary_seq1).exists()',
    'assert not (Path.home() / ".courier_runtime" / canary_seq1).exists()'
).replace(
    'assert not (REPO_ROOT / canary_seq2).exists()',
    'assert not (Path.home() / ".courier_runtime" / canary_seq2).exists()'
)

# wait, are there other canary files in the rest of the test?
# let's replace all `REPO_ROOT / canary` with `Path.home() / ".courier_runtime" / canary`
import re
content = re.sub(r'REPO_ROOT \/ (canary_[a-z0-9_]+)', r'Path.home() / ".courier_runtime" / \1', content)

open("tests/test_tomato_two_torture.py", "w").write(content)
