import pytest
from courier_core.revenue_economics import RevenueCalculator, UnitEconomics
from courier_core.revenue_state import RevenueStateMachine, RevenueState

def test_unit_economics():
    eco = RevenueCalculator.calculate_economics(cost=20.0, revenue=100.0)
    assert eco.gross_margin_usd == 80.0
    assert eco.gross_margin_percent == 80.0
    
    with pytest.raises(ValueError):
        RevenueCalculator.calculate_economics(-10.0, 50.0)

def test_revenue_state_machine():
    fsm = RevenueStateMachine()
    assert fsm.state == RevenueState.PROSPECT
    
    # Valid flow
    assert fsm.transition(RevenueState.QUALIFIED)
    assert fsm.transition(RevenueState.DRAFT_READY)
    assert fsm.transition(RevenueState.WAITING_FOR_HUMAN)
    
    # Invalid jump
    assert not fsm.transition(RevenueState.WON)
    assert fsm.state == RevenueState.WAITING_FOR_HUMAN
    
    # Drop to lost
    assert fsm.transition(RevenueState.LOST)
    assert fsm.state == RevenueState.LOST
