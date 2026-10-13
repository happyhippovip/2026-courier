import pytest
import time
from courier_runtime.provider_circuit import (
    CircuitBreaker, ProviderAvailability, AuthorizedFallbackRouter, WorkClassification
)

def test_quota_exhausted_opens_circuit():
    cb = CircuitBreaker()
    cb.record_error("openai-prod", "gpt-4", 429, {"retry_after": 3600})
    state = cb.get_state("openai-prod", "gpt-4")
    
    assert state.availability == ProviderAvailability.QUOTA_EXHAUSTED
    assert state.open_circuit is True
    assert state.retry_after is not None

def test_coalesced_wakes_do_not_hammer():
    cb = CircuitBreaker()
    cb.record_error("openai-prod", "gpt-4", 429, {"retry_after": 3600})
    state = cb.get_state("openai-prod", "gpt-4")
    
    # Simulate 100 wakes
    calls = 0
    recheck_markers = 0
    for _ in range(100):
        if not state.open_circuit:
            calls += 1
        elif state.check_recovery():
            recheck_markers += 1
            
    assert calls == 0
    assert recheck_markers == 0

def test_fallback_router_finds_authorized_connection():
    cb = CircuitBreaker()
    router = AuthorizedFallbackRouter(cb)
    router.register_connection("openai-prod", ["gpt-4", "gpt-3.5"], {"project": "core"})
    router.register_connection("anthropic-prod", ["gpt-4", "claude-3"], {"project": "core"})
    
    cb.record_error("openai-prod", "gpt-4", 429, {"retry_after": 3600})
    
    fallback = router.find_fallback("gpt-4", {"project": "core"})
    assert fallback == "anthropic-prod"

def test_fallback_router_no_fallback():
    cb = CircuitBreaker()
    router = AuthorizedFallbackRouter(cb)
    router.register_connection("openai-prod", ["gpt-4", "gpt-3.5"], {"project": "core"})
    
    cb.record_error("openai-prod", "gpt-4", 429, {"retry_after": 3600})
    
    fallback = router.find_fallback("gpt-4", {"project": "core"})
    assert fallback is None

def test_recovery_probe_due():
    cb = CircuitBreaker()
    cb.record_error("openai-prod", "gpt-4", 429, {"retry_after": 0.1})
    state = cb.get_state("openai-prod", "gpt-4")
    
    time.sleep(0.15)
    
    assert state.check_recovery() is True
    assert state.availability == ProviderAvailability.RECOVERY_PROBE_DUE

def test_successful_recovery():
    cb = CircuitBreaker()
    cb.record_error("openai-prod", "gpt-4", 429, {"retry_after": 0.1})
    time.sleep(0.15)
    
    state = cb.get_state("openai-prod", "gpt-4")
    assert state.check_recovery() is True
    
    cb.record_success("openai-prod", "gpt-4")
    state = cb.get_state("openai-prod", "gpt-4")
    
    assert state.open_circuit is False
    assert state.availability == ProviderAvailability.AVAILABLE

