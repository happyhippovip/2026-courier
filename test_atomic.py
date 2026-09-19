from pathlib import Path
import json
import sys
sys.path.insert(0, str(Path("scripts").resolve()))
from agent_handoff_ledger import atomic_write, load_bundle

p = Path("test_ledger.json")
p.write_text('{"revision": 0}')

print("Before:", load_bundle(p))
atomic_write(p, {"revision": 1})
print("After:", load_bundle(p))
