import json
import os
import sys
import tempfile
from pathlib import Path
from datetime import datetime, timedelta
sys.path.append(os.path.abspath("."))
from tests.test_ledger_freshness_binding_epoch import *

tmp = Path(tempfile.mkdtemp())
path = tmp / "ledger.json"

rec = _base_record()
g = _base_guard()
g["acceptance_predicate"]["required_results"] = ["ISSUE_STATE"]
g["acceptance_predicate"]["results"] = {
    "ISSUE_STATE": {
        "status": "UNKNOWN",
        "observed_value": "PENDING",
        "evidence_urls": [],
    }
}
initialize(path, rec, g, 5.0)

just_fresh = datetime.utcnow() - timedelta(hours=47)
g1 = copy.deepcopy(g)
g1["evidence"].append(_artifact("https://test.com/47h", _ts(just_fresh)))
print("EVIDENCE G1:", g1["evidence"])
update(path, 0, {"TASKS_COMPLETED": 3}, "writer-a", 5.0, guard=g1)

with open(path) as f:
    bundle = json.load(f)
    print("SAVED EVIDENCE:", bundle["acceptance_guard"]["evidence"])
