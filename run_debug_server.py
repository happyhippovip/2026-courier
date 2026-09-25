import pytest

pytest.main(["-v", "-s", "tests/test_server_integration_contract.py::test_worker_success_cannot_advance_goal_without_independent_verifier"])
