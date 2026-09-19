import re

with open("/tmp/pytest_out_s.txt") as f:
    text = f.read()

m = re.search(r"where 'MOCK_LEDGER IN ENV.*? = CompletedProcess\(args=.*?stdout='(.*?)', stderr", text, re.DOTALL)
if m:
    s = m.group(1).replace("\\n", "\n")
    with open("/tmp/real_stdout.txt", "w") as f2:
        f2.write(s)
