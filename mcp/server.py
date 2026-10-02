#!/usr/bin/env python3
import sys
import json
import urllib.request
import urllib.error

# Basic MCP Server for Courier Ledger
# Implements: mcp_courier_status, mcp_courier_claim, mcp_courier_complete

BASE_URL = "http://localhost:8000"

def respond(result):
    print(json.dumps(result))
    sys.stdout.flush()

def handle_request(req):
    method = req.get("method")
    params = req.get("params", {})
    
    if method == "tools/list":
        respond({
            "tools": [
                {
                    "name": "mcp_courier_status",
                    "description": "Read the global ledger state and unassigned tasks.",
                    "inputSchema": {"type": "object", "properties": {}}
                },
                {
                    "name": "mcp_courier_claim",
                    "description": "Claim a specific unassigned task.",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "worker_id": {"type": "string"}
                        },
                        "required": ["worker_id"]
                    }
                }
            ]
        })
    elif method == "tools/call":
        tool_name = params.get("name")
        args = params.get("arguments", {})
        
        if tool_name == "mcp_courier_status":
            try:
                req = urllib.request.Request(f"{BASE_URL}/status")
                with urllib.request.urlopen(req) as response:
                    data = json.loads(response.read().decode())
                respond({"content": [{"type": "text", "text": json.dumps(data, indent=2)}]})
            except Exception as e:
                respond({"error": str(e)})
                
        elif tool_name == "mcp_courier_claim":
            try:
                data = json.dumps({"worker_id": args.get("worker_id", "mcp-agent")}).encode("utf-8")
                req = urllib.request.Request(f"{BASE_URL}/tasks/claim", data=data, headers={'Content-Type': 'application/json'})
                with urllib.request.urlopen(req) as response:
                    data = json.loads(response.read().decode())
                respond({"content": [{"type": "text", "text": json.dumps(data, indent=2)}]})
            except Exception as e:
                respond({"error": str(e)})
        else:
            respond({"error": "Unknown tool"})

def main():
    for line in sys.stdin:
        if not line.strip(): continue
        try:
            req = json.loads(line)
            handle_request(req)
        except json.JSONDecodeError:
            pass

if __name__ == "__main__":
    main()
