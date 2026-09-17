import sys
import re

content = open("tests/test_tomato_two_torture.py").read()

content = content.replace(
    'canary_seq1 = f"courier_canary_torture_seq1_{run_uid}.txt"',
    'canary_seq1 = str(REPO_ROOT / f"courier_canary_torture_seq1_{run_uid}.txt")'
).replace(
    'canary_seq2 = f"courier_canary_torture_seq2_{run_uid}.txt"',
    'canary_seq2 = str(REPO_ROOT / f"courier_canary_torture_seq2_{run_uid}.txt")'
)

open("tests/test_tomato_two_torture.py", "w").write(content)
