import pytest
from courier_core.marketing_authority import MarketingAuthorityBoundary, MarketingAction
from courier_core.dynamic_ports import DynamicPortAllocator

def test_marketing_authority_allows_preview():
    res = MarketingAuthorityBoundary.execute(MarketingAction.PREVIEW, {"copy": "Draft text"})
    assert res["status"] == "SUCCESS"
    assert res["action"] == "PREVIEW"

def test_marketing_authority_blocks_spend_and_publish():
    with pytest.raises(PermissionError):
        MarketingAuthorityBoundary.execute(MarketingAction.PUBLISH, {"copy": "Live text"})
    
    with pytest.raises(PermissionError):
        MarketingAuthorityBoundary.execute(MarketingAction.SPEND, {"amount": 100})

def test_dynamic_port_allocation():
    sock, port = DynamicPortAllocator.allocate_port()
    try:
        assert port > 0
        assert port <= 65535
        
        # Test collision handling: bind another to 0, they should differ
        sock2, port2 = DynamicPortAllocator.allocate_port()
        try:
            assert port != port2
        finally:
            sock2.close()
    finally:
        sock.close()
