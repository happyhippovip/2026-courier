"""Disposable owner for the Windows job crash test; no production imports."""
import json
import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cannon.adapters import FakeAdapter
from cannon.storage import atomic

request = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
adapter = FakeAdapter(request['contract'], request['workspace'])
adapter.execute(request['task'], request['folder'], lambda identity: atomic(request['marker'], identity))
# Owner blocks on its private pipe. The test terminates only this Popen handle.
os.read(0, 1)
adapter.close()
