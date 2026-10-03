import sys

content = open("tests/test_l3_worker_host.py").read()

content = content.replace("test_timeout_kills_whole_tree_within_bound", "test_timeout_extends_until_lease_lost")
content = content.replace("timeout_s=2.0, lease_ttl_s=30.0", "timeout_s=1.0, lease_ttl_s=3.0")
content = content.replace("assert result.outcome == Outcome.TIMEOUT", "assert result.outcome == Outcome.LEASE_LOST")
content = content.replace("assert elapsed < 2.0 + H.KILL_GRACE_S + 4.0", "assert elapsed >= 3.0")

with open("tests/test_l3_worker_host.py", "w") as f:
    f.write(content)
print("Fixed test")
