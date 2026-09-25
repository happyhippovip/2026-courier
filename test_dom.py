import subprocess
import json
with open("tmp_status.json", "w") as f:
    f.write(json.dumps({"state": {"status": "RUNNING"}, "session": {}, "live": {"text": "LÄUFT · 0001\n\nprint('x')"}}))

out = subprocess.run(["node", "tests/dom_harness.js", "app/cannon.js", "tmp_status.json", "3"], capture_output=True, text=True).stdout
for entry in json.loads(out):
    if entry[0] == "result" and entry[1] == "textContent":
        print(entry)
