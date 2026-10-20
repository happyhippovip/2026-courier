import json
import time
import pytest
from courier_core.rate_limiter import (
    TokenBucketLimiter,
    SlidingWindowLimiter,
    MultiTierRateLimiter,
    RateLimitRule,
)


def test_token_bucket_burst_and_drain():
    # 10 tokens/sec, burst capacity 5
    bucket = TokenBucketLimiter(rate=10.0, capacity=5.0)

    # 5 instantaneous tokens allowed
    for _ in range(5):
        assert bucket.acquire(tokens=1.0, block=False) is True

    # 6th immediate token rejected
    assert bucket.acquire(tokens=1.0, block=False) is False


def test_token_bucket_refill_over_time():
    # 20 tokens/sec, capacity 2
    bucket = TokenBucketLimiter(rate=20.0, capacity=2.0)

    assert bucket.acquire(tokens=2.0, block=False) is True
    assert bucket.acquire(tokens=1.0, block=False) is False

    # Sleep 0.1s -> refills ~2 tokens
    time.sleep(0.12)
    assert bucket.acquire(tokens=1.0, block=False) is True


def test_token_bucket_blocking_acquisition_with_timeout():
    bucket = TokenBucketLimiter(rate=10.0, capacity=1.0)
    assert bucket.acquire(tokens=1.0, block=False) is True

    # Next acquire with timeout=0.05s should fail (needs ~0.1s for 1 token)
    t0 = time.time()
    assert bucket.acquire(tokens=1.0, block=True, timeout=0.04) is False
    assert time.time() - t0 >= 0.03

    # Next acquire with timeout=0.3s should succeed
    assert bucket.acquire(tokens=1.0, block=True, timeout=0.3) is True


def test_sliding_window_limiter():
    # Max 3 requests in 0.2s window
    limiter = SlidingWindowLimiter(window_seconds=0.2, max_requests=3)

    assert limiter.allow_request() is True
    assert limiter.allow_request() is True
    assert limiter.allow_request() is True
    # 4th in same window blocked
    assert limiter.allow_request() is False

    # Wait for window to expire
    time.sleep(0.22)
    assert limiter.allow_request() is True


def test_multi_tier_limiter_both_rules_must_pass():
    # Tier 1: 5 req/sec burst
    # Tier 2: 10 req/min sustained
    multi = MultiTierRateLimiter([
        RateLimitRule(name="burst", rate=5.0, capacity=5.0),
        RateLimitRule(name="sustained", rate=0.2, capacity=2.0),
    ])

    # Drain sustained capacity (2 tokens)
    assert multi.acquire(1.0) is True
    assert multi.acquire(1.0) is True

    # 3rd request blocked by sustained limit even though burst bucket has capacity
    assert multi.acquire(1.0) is False


def test_invalid_token_quantity_rejected():
    bucket = TokenBucketLimiter(rate=10.0, capacity=5.0)
    with pytest.raises(ValueError):
        bucket.acquire(tokens=-1.0)
    with pytest.raises(ValueError):
        bucket.acquire(tokens=0.0)
    with pytest.raises(ValueError):
        bucket.acquire(tokens=100.0)  # Exceeds capacity


def test_cli_invocation():
    import subprocess
    import sys

    # Check CLI
    cmd = [
        sys.executable,
        "-m",
        "courier_core.rate_limiter",
        "simulate",
        "--rate",
        "10.0",
        "--capacity",
        "5.0",
        "--requests",
        "7",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=True)
    out = json.loads(proc.stdout)
    assert out["total_requests"] == 7
    assert out["allowed_immediate"] == 5
    assert out["rejected_immediate"] == 2
