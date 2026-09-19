with open("tests/test_ledger_authenticated_receipts.py", "r") as f:
    lines = f.readlines()

out = []
for line in lines:
    if "os.environ.pop('MOCK_LEDGER', None)" in line:
        continue
    out.append(line)

out.append("""
@pytest.fixture(autouse=True)
def _disable_mock_ledger(monkeypatch):
    monkeypatch.delenv("MOCK_LEDGER", raising=False)
""")

with open("tests/test_ledger_authenticated_receipts.py", "w") as f:
    f.write("".join(out))
