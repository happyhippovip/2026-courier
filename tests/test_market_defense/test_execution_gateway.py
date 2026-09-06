import unittest, sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from scripts.market_defense.execution_gateway import (
    ExecutionGateway, GatewayAction, ForbiddenAction, SignerInterface,
    PaperExecutionSimulator, PaperOrderBook, ExecutionPipeline
)

class TestExecutionGateway(unittest.TestCase):
    def test_permitted_actions(self):
        gateway = ExecutionGateway()
        for action in GatewayAction:
            self.assertTrue(gateway.is_action_permitted(action.name))

    def test_forbidden_send_asset(self):
        self.assertTrue(ExecutionGateway().deny(ForbiddenAction.SEND_ASSET).denied)

    def test_forbidden_usd_send(self):
        self.assertTrue(ExecutionGateway().deny(ForbiddenAction.USD_SEND).denied)

    def test_forbidden_withdraw(self):
        self.assertTrue(ExecutionGateway().deny(ForbiddenAction.WITHDRAW).denied)

    def test_forbidden_arbitrary_transfer(self):
        self.assertTrue(ExecutionGateway().deny(ForbiddenAction.ARBITRARY_TRANSFER).denied)

    def test_forbidden_approve_agent(self):
        self.assertTrue(ExecutionGateway().deny(ForbiddenAction.APPROVE_AGENT).denied)

    def test_forbidden_change_security(self):
        self.assertTrue(ExecutionGateway().deny(ForbiddenAction.CHANGE_ACCOUNT_SECURITY).denied)

    def test_forbidden_unknown(self):
        self.assertTrue(ExecutionGateway().deny(ForbiddenAction.UNKNOWN_ACTION).denied)

    def test_signer_no_raw_key(self):
        self.assertFalse(SignerInterface().has_raw_key_access())

    def test_signer_paper_signature(self):
        self.assertEqual(SignerInterface().sign_order({}), 'PAPER_MODE_NO_REAL_SIGNATURE')

    def test_paper_simulator_fill(self):
        simulator = PaperExecutionSimulator()
        fill = simulator.simulate_fill(instrument='BTC', direction='LONG', size=0.01, current_price=50000.0)
        self.assertTrue(hasattr(fill, 'price'))
        self.assertTrue(hasattr(fill, 'size'))
        self.assertEqual(fill.size, 0.01)
        self.assertGreater(fill.price, 50000.0)

    def test_execute_query_balance(self):
        res = ExecutionGateway().execute(GatewayAction.QUERY_BALANCE, {})
        self.assertTrue(res.success)

if __name__ == '__main__':
    unittest.main()
