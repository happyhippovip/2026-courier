import unittest
from unittest import mock
import scripts.agent_handoff_ledger as ledger_module

class TestP(unittest.TestCase):
    @mock.patch("scripts.agent_handoff_ledger._verify_attestation")
    def test_mock(self, mock_v):
        mock_v.return_value = "hello"
        print("MOCK RETURNS:", ledger_module._verify_attestation("url"))

TestP("test_mock").test_mock()
