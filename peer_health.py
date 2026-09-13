"""
peer_health.py - Courier Cross-Platform Health Probe & Peer Synchronization Client
Part of TASK-WIN-60: Cross-Platform Health Ping & Status Synchronization Protocol.

Enables automated, bidirectional health and synchronization inspection between
Windows and Mac supervisor nodes without filesystem race conditions.
"""

import sys
import os
import json
import time
import hashlib
import urllib.request
import urllib.parse
import urllib.error
import argparse
from typing import Dict, Any, Optional

DEFAULT_BASE_URL = "http://127.0.0.1:8088"

class CourierPeerHealth:
    def __init__(self, base_url: str = DEFAULT_BASE_URL, timeout: float = 5.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def ping(self) -> Dict[str, Any]:
        """Queries local or remote node's /api/courier/ping."""
        url = f"{self.base_url}/api/courier/ping"
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return data
        except urllib.error.HTTPError as e:
            return {
                "success": False,
                "error": f"HTTP {e.code}: {e.reason}",
                "body": e.read().decode("utf-8", errors="replace")
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

    def peer_health(self, peer_url: Optional[str] = None) -> Dict[str, Any]:
        """Queries /api/courier/peer-health, optionally specifying a remote peer URL."""
        url = f"{self.base_url}/api/courier/peer-health"
        if peer_url:
            encoded_peer = urllib.parse.quote(peer_url)
            url += f"?peer={encoded_peer}"
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return data
        except urllib.error.HTTPError as e:
            return {
                "success": False,
                "error": f"HTTP {e.code}: {e.reason}",
                "body": e.read().decode("utf-8", errors="replace")
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

    @staticmethod
    def verify_zero_spend(data: Dict[str, Any]) -> bool:
        """Verifies that all reported spend values across local and peer nodes are strictly 0.00 EUR."""
        # Check spend_firewall in ping response
        spend_firewall = data.get("spend_firewall", {})
        if spend_firewall:
            if float(spend_firewall.get("spend_eur", 0.0)) != 0.0:
                return False
            if float(spend_firewall.get("spend_limit_eur", 0.0)) != 0.0:
                return False

        # Check local health in peer-health response
        local_health = data.get("local", {})
        if local_health and float(local_health.get("spend_eur", 0.0)) != 0.0:
            return False

        # Check peer health in peer-health response
        peer_health = data.get("peer", {})
        if peer_health and peer_health.get("reachable"):
            if float(peer_health.get("spend_eur", 0.0)) != 0.0:
                return False

        return True

    @staticmethod
    def compute_evidence_fingerprint(data: Dict[str, Any]) -> str:
        """Produces a deterministic SHA-256 fingerprint of the health probe data."""
        canonical_json = json.dumps(data, sort_keys=True)
        return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()

def main():
    parser = argparse.ArgumentParser(description="Courier Peer Health Probe CLI")
    parser.add_argument("--probe", action="store_true", help="Probe local supervisor health via /api/courier/ping")
    parser.add_argument("--peer", type=str, default=None, help="Probe synchronization against a remote peer node URL")
    parser.add_argument("--base-url", type=str, default=DEFAULT_BASE_URL, help="Base URL of local Courier server")
    parser.add_argument("--assert-zero-spend", action="store_true", help="Fail with non-zero exit if spend > 0.00 EUR")
    parser.add_argument("--json", action="store_true", help="Output raw JSON")
    parser.add_argument("--timeout", type=float, default=5.0, help="Request timeout in seconds")

    args = parser.parse_args()
    client = CourierPeerHealth(base_url=args.base_url, timeout=args.timeout)

    if args.peer:
        result = client.peer_health(peer_url=args.peer)
    elif args.probe:
        result = client.ping()
    else:
        # Default action: probe local
        result = client.ping()

    zero_spend = CourierPeerHealth.verify_zero_spend(result)
    fingerprint = CourierPeerHealth.compute_evidence_fingerprint(result)

    if args.assert_zero_spend and not zero_spend:
        sys.stderr.write("[SPEND_FIREWALL_VIOLATION] Non-zero spend detected in health response!\n")
        sys.exit(2)

    if args.json:
        result["evidence_fingerprint"] = fingerprint
        result["zero_spend_verified"] = zero_spend
        print(json.dumps(result, indent=2))
    else:
        print("=" * 60)
        print("COURIER PEER HEALTH PROBE REPORT")
        print("=" * 60)
        print(f"Status:             {'HEALTHY' if result.get('success') else 'UNHEALTHY'}")
        print(f"Host:               {result.get('host', result.get('local', {}).get('host', 'UNKNOWN'))}")
        checkpoint = result.get('control_plane', {}).get('checkpoint', result.get('local', {}).get('checkpoint', 'UNKNOWN'))
        tasks_count = result.get('control_plane', {}).get('certified_tasks_count', result.get('local', {}).get('certified_tasks_count', 0))
        print(f"Latest Checkpoint:  {checkpoint} ({tasks_count} tasks certified)")
        print(f"Spend Firewall:     {'VERIFIED ZERO SPEND (0.00 EUR)' if zero_spend else 'VIOLATION'}")
        print(f"Evidence SHA-256:   {fingerprint}")
        if "peer" in result and result["peer"].get("queried"):
            p = result["peer"]
            print("-" * 60)
            print(f"Peer URL:           {p.get('url')}")
            print(f"Peer Reachable:     {p.get('reachable')}")
            print(f"Peer Latency:       {p.get('latency_ms')} ms")
            print(f"Peer Sync Status:   {p.get('sync_status')}")
            print(f"Peer Checkpoint:    {p.get('checkpoint')}")
        print("=" * 60)

    if not result.get("success"):
        sys.exit(1)

if __name__ == "__main__":
    main()
