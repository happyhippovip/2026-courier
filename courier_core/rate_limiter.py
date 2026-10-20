"""Token-Bucket and Sliding-Window Multi-Tier Rate Limiter (P33)

Provides robust throughput regulation and API quota enforcement using
token-bucket burst smoothing, sliding-window rolling intervals, and
atomic multi-tier rule evaluation.
"""

from __future__ import annotations

import argparse
import collections
import json
import sys
import threading
import time
from dataclasses import dataclass
from typing import Dict, List, Optional


class TokenBucketLimiter:
    """Thread-safe Token Bucket rate limiter with configurable burst capacity."""

    def __init__(self, rate: float, capacity: float) -> None:
        if rate <= 0:
            raise ValueError("Rate must be greater than 0")
        if capacity <= 0:
            raise ValueError("Capacity must be greater than 0")

        self.rate = float(rate)
        self.capacity = float(capacity)
        self.tokens = float(capacity)
        self.last_refill = time.time()
        self._lock = threading.Lock()

    def _refill(self) -> None:
        now = time.time()
        elapsed = now - self.last_refill
        if elapsed > 0:
            self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)
            self.last_refill = now

    def acquire(
        self,
        tokens: float = 1.0,
        block: bool = True,
        timeout: Optional[float] = None,
    ) -> bool:
        """Attempt to acquire a given number of tokens."""
        if tokens <= 0:
            raise ValueError("Tokens to acquire must be positive")
        if tokens > self.capacity:
            raise ValueError(f"Requested {tokens} tokens exceeds capacity {self.capacity}")

        start_time = time.time()

        while True:
            with self._lock:
                self._refill()
                if self.tokens >= tokens:
                    self.tokens -= tokens
                    return True

                if not block:
                    return False

                # Calculate required sleep duration
                deficit = tokens - self.tokens
                needed_wait = deficit / self.rate

            now = time.time()
            elapsed = now - start_time
            if timeout is not None:
                remaining = timeout - elapsed
                if remaining <= 0:
                    return False
                if needed_wait > remaining:
                    time.sleep(max(0.001, remaining))
                    return False
                sleep_chunk = min(needed_wait, remaining, 0.05)
            else:
                sleep_chunk = min(needed_wait, 0.05)

            time.sleep(max(0.001, sleep_chunk))


class SlidingWindowLimiter:
    """Thread-safe Sliding Window rate limiter tracking exact rolling timestamps."""

    def __init__(self, window_seconds: float, max_requests: int) -> None:
        if window_seconds <= 0:
            raise ValueError("Window must be positive")
        if max_requests <= 0:
            raise ValueError("Max requests must be positive")

        self.window_seconds = float(window_seconds)
        self.max_requests = int(max_requests)
        self._timestamps: collections.deque[float] = collections.deque()
        self._lock = threading.Lock()

    def allow_request(self) -> bool:
        with self._lock:
            now = time.time()
            cutoff = now - self.window_seconds
            while self._timestamps and self._timestamps[0] <= cutoff:
                self._timestamps.popleft()

            if len(self._timestamps) < self.max_requests:
                self._timestamps.append(now)
                return True

            return False


@dataclass
class RateLimitRule:
    name: str
    rate: float
    capacity: float


class MultiTierRateLimiter:
    """Coordinates multiple rate limit tiers (e.g., burst/sec + sustained/min)."""

    def __init__(self, rules: List[RateLimitRule]) -> None:
        self.rules = list(rules)
        self._buckets: Dict[str, TokenBucketLimiter] = {
            r.name: TokenBucketLimiter(rate=r.rate, capacity=r.capacity)
            for r in self.rules
        }
        self._lock = threading.Lock()

    def acquire(self, tokens: float = 1.0) -> bool:
        with self._lock:
            # First pass: check if all tiers have sufficient tokens
            for bucket in self._buckets.values():
                bucket._refill()
                if bucket.tokens < tokens:
                    return False

            # Second pass: atomic deduction across all tiers
            for bucket in self._buckets.values():
                bucket.tokens -= tokens

            return True


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Rate Limiter CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    sim_parser = subparsers.add_parser("simulate", help="Simulate immediate burst requests")
    sim_parser.add_argument("--rate", type=float, required=True)
    sim_parser.add_argument("--capacity", type=float, required=True)
    sim_parser.add_argument("--requests", type=int, default=10)

    args = parser.parse_args(argv)

    if args.command == "simulate":
        limiter = TokenBucketLimiter(rate=args.rate, capacity=args.capacity)
        allowed = 0
        rejected = 0

        for _ in range(args.requests):
            if limiter.acquire(tokens=1.0, block=False):
                allowed += 1
            else:
                rejected += 1

        print(json.dumps({
            "total_requests": args.requests,
            "allowed_immediate": allowed,
            "rejected_immediate": rejected,
            "remaining_tokens": limiter.tokens,
        }, indent=2))
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
