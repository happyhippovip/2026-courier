import glob
with open('memory/WINDOWS_VERIFICATION_LEDGER.md', encoding='utf-8') as f:
    ledger = f.read()
    
unverified = []
for p in glob.glob('scripts/*.py'):
    normalized = p.replace('\\', '/')
    if normalized not in ledger:
        unverified.append(normalized)

print("UNVERIFIED FILES:")
for u in unverified:
    print(u)
