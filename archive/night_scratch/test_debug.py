import json
from scripts import agent_handoff_ledger as ledger_module
import tempfile
from pathlib import Path
from tests.test_agent_handoff_ledger import initialize

with tempfile.TemporaryDirectory() as temporary:
    ledger = Path(temporary) / "ledger.json"
    initialize(ledger)
    bundle = ledger_module.load_bundle(ledger)
    print("INITIAL:", json.dumps(bundle["acceptance_guard"]["evidence"], indent=2))
    landed = ledger_module.copy.deepcopy(bundle["acceptance_guard"])
    proof = {
        "source_url": "https://github.com/example/project/actions/runs/99",
        "source_type": "MACHINE_ARTIFACT",
        "observed_at": "2026-09-17T18:00:00Z",
        "evidence_sha": "a" * 40,
        "runtime_binding": "runtime-a",
        "validity": "UNKNOWN",
        "reason": "foreign attestation",
        "producer_id": "foreign-producer",
        "verifier_id": "foreign-verifier",
    }
    landed["evidence"].append(proof)
    b2 = ledger_module.update(ledger, bundle["revision"], {"CURRENT_SHA": "a"*40, "RUNTIME_IDENTITY": "runtime-a"}, "worker1", 1.0, landed)
    print("B2:", json.dumps(b2["acceptance_guard"]["evidence"], indent=2))
