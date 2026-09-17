import re
import time

SECRET_VALUE_RE = re.compile(
    r"(?i)(?:api[_ -]?key|password|passwd|authorization|bearer|"
    r"client[_ -]?secret|access[_ -]?token|refresh[_ -]?token|"
    r"private[_ -]?key)\s*[:=]\s*\S+|"
    r"\bbearer\s+\S+|-----BEGIN [A-Z ]*PRIVATE KEY-----|"
    r"\bAKIA[A-Z0-9]{16}\b|"
    r"\b(?:github_pat_|gh[pousr]_|sk-)[A-Za-z0-9_-]{16,}"
)

def test_string(s):
    t0 = time.time()
    SECRET_VALUE_RE.search(s)
    t1 = time.time()
    print(f"Length {len(s)} took {t1 - t0:.6f} seconds")

test_string("password" + " " * 100000 + "X")
test_string("password" + " " * 100000)
test_string("password=" + " " * 100000 + "X")
test_string("password=" + " " * 100000)
test_string("a" * 100000)
