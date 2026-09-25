import os
import sys
sys.path.append(os.path.abspath("."))
import pytest
pytest.main(["tests/test_ledger_freshness_binding_epoch.py::TestLongLivedEpochMutableEvidence::test_evidence_at_47h_qualifies_as_fresh", "-s"])
