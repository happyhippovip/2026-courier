import tempfile
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from scripts import agent_handoff_ledger

def test_edge_conservation_regression():
    with tempfile.TemporaryDirectory() as temporary:
        ledger = Path(temporary) / "ledger.json"
        
        # We need default record and guard
        from tests.test_agent_handoff_ledger import record, guard
        agent_handoff_ledger.initialize(ledger, record(), guard(), 1.0)
        bundle = agent_handoff_ledger.load_bundle(ledger)
        initial_unproven = bundle["record"].get("UNPROVEN_EDGES", [])
        fake_edge = "THIN_AIR_EDGE"
        
        # Negative test: proving an edge that never existed
        try:
            agent_handoff_ledger.update(
                path=ledger,
                expected_revision=bundle["revision"],
                updates={"PROVEN_EDGES": [fake_edge]},
                updated_by="test-worker",
                timeout=1.0
            )
            assert False, "Edge Conservation regression: Allowed a PROVEN_EDGE out of thin air!"
        except agent_handoff_ledger.LedgerError as e:
            assert "edge conservation violated" in str(e)
            

        # Positive test: properly moving an edge from UNPROVEN to PROVEN
        legit_edge = "issue state" # we know it's in initial_unproven
        try:
            agent_handoff_ledger.update(
                path=ledger,
                expected_revision=bundle["revision"],
                updates={
                    "PROVEN_EDGES": [legit_edge],
                    "UNPROVEN_EDGES": ["runtime artifact"] # The other one
                },
                updated_by="test-worker",
                timeout=1.0
            )
        except Exception as e:
            assert False, f"Legitimate edge proof failed: {e}"
