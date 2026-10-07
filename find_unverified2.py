import glob

with open('memory/WINDOWS_VERIFICATION_LEDGER.md', encoding='utf-8') as f:
    ledger = f.read()

unverified = []
for p in glob.glob('*/**/*.py', recursive=True):
    if "tests" in p or ".venv" in p or "muse" in p or p.endswith("__init__.py"):
        continue
    normalized = p.replace('\\', '/')
    if normalized not in ledger:
        unverified.append(normalized)

print("UNVERIFIED:")
for u in unverified:
    print(u)
