with open("tests/conftest.py", "r") as f:
    lines = f.readlines()

out = []
for line in lines:
    if "os.environ[\"MOCK_LEDGER\"]" in line:
        continue
    out.append(line)

out.append("""
@pytest.fixture(autouse=True)
def _mock_ledger_env(monkeypatch):
    monkeypatch.setenv("MOCK_LEDGER", "1")
""")

with open("tests/conftest.py", "w") as f:
    f.write("".join(out))
