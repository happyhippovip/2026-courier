"""
peer_bridge.py - Cross-Device HTTP Peer Transport Client and Bridge
Provides deterministic, zero-prompt HTTP peer communication between Mac Chief and Windows PC2.
Usage:
  uv run python courier/peer_bridge.py --host 127.0.0.1 --status
  uv run python courier/peer_bridge.py --host 127.0.0.1 --submit request.json
  uv run python courier/peer_bridge.py --host 127.0.0.1 --get-result REQ-WIN-001
  uv run python courier/peer_bridge.py --host 127.0.0.1 --trigger-cycle
"""

import os
import sys
import json
import urllib.request
import urllib.error
import argparse

def send_request(url, data=None, method="GET"):
    headers = {"Content-Type": "application/json"}
    body = json.dumps(data).encode("utf-8") if data else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=95) as response:
            res_body = response.read().decode("utf-8")
            return json.loads(res_body)
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8")
        return {"error": f"HTTP {e.code}: {e.reason}", "detail": err_body}
    except Exception as e:
        return {"error": str(e)}

def main():
    parser = argparse.ArgumentParser(description="Courier Chief Cross-Device Peer Bridge")
    parser.add_argument("--host", default="127.0.0.1", help="Target host IP or domain (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8088, help="Target port (default: 8088)")
    parser.add_argument("--status", action="store_true", help="Query remote Courier Chief delta and status")
    parser.add_argument("--autonomy-status", action="store_true", help="Query remote Unified Autonomy status")
    parser.add_argument("--submit", type=str, help="Submit a structured request JSON file or raw string")
    parser.add_argument("--get-result", type=str, help="Retrieve result by request_id")
    parser.add_argument("--trigger-cycle", action="store_true", help="Trigger an on-demand unified autonomy cycle")
    parser.add_argument("--submit-thought", type=str, help="Submit a new thought (JSON file, JSON string, or title string) to Gedanken-Lagerhalle")
    parser.add_argument("--money-cycle", action="store_true", help="Trigger an on-demand Money Factory re-ranking with adversarial pass")
    parser.add_argument("--archive-report", action="store_true", help="Retrieve and display the Consolidated Archive Report (DEC-006)")

    args = parser.parse_args()
    base_url = f"http://{args.host}:{args.port}"

    if args.archive_report:
        url = f"{base_url}/api/archive/report"
        req = urllib.request.Request(url)
        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                print(response.read().decode("utf-8"))
        except Exception as e:
            print(f"Error: {e}")
        return

    if args.money_cycle:
        url = f"{base_url}/api/money-factory/cycle"
        res = send_request(url, data={}, method="POST")
        print(json.dumps(res, indent=2))
        return

    if args.submit_thought:
        url = f"{base_url}/api/ingest"
        if os.path.exists(args.submit_thought):
            with open(args.submit_thought, "r", encoding="utf-8") as f:
                payload = json.load(f)
        else:
            try:
                payload = json.loads(args.submit_thought)
            except Exception:
                payload = {
                    "source": "mac_peer_bridge",
                    "items": [{
                        "title": args.submit_thought[:60],
                        "content": args.submit_thought,
                        "summary": args.submit_thought[:120],
                        "category": "Idea",
                        "tags": ["peer_bridge", "mac_dispatch"]
                    }]
                }
        res = send_request(url, data=payload, method="POST")
        print(json.dumps(res, indent=2))
        return

    if args.status:
        url = f"{base_url}/api/courier/status"
        res = send_request(url)
        print(json.dumps(res, indent=2))
        return

    if args.autonomy_status:
        url = f"{base_url}/api/autonomy/status"
        res = send_request(url)
        print(json.dumps(res, indent=2))
        return

    if args.submit:
        url = f"{base_url}/api/courier/request"
        if os.path.exists(args.submit):
            with open(args.submit, "r", encoding="utf-8") as f:
                payload = json.load(f)
        else:
            payload = json.loads(args.submit)
        res = send_request(url, data=payload, method="POST")
        print(json.dumps(res, indent=2))
        return

    if args.get_result:
        url = f"{base_url}/api/courier/result/{args.get_result}"
        res = send_request(url)
        print(json.dumps(res, indent=2))
        return

    if args.trigger_cycle:
        url = f"{base_url}/api/autonomy/cycle"
        res = send_request(url, data={}, method="POST")
        print(json.dumps(res, indent=2))
        return

    parser.print_help()

if __name__ == "__main__":
    main()
