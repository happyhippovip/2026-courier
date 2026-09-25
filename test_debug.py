import pytest
from tests.test_ledger_freshness_binding_epoch import TestLongLivedEpochMutableEvidence
import sys

def test_run():
    pytest.main(["tests/test_ledger_freshness_binding_epoch.py::TestLongLivedEpochMutableEvidence::test_evidence_at_47h_qualifies_as_fresh", "-s"])

