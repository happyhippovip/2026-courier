from scripts.provider_circuit import ProviderCircuitBreaker
b1 = ProviderCircuitBreaker()
b2 = ProviderCircuitBreaker()
b1.restore({"muse|completion": {"state": "QUOTA_EXHAUSTED", "reset_time": None, "probe_in_flight": False}})
print(b1.circuits is b2.circuits)
