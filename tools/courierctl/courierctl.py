#!/usr/bin/env python3
import os
import sys
import json
import argparse
import requests

def get_config():
    server = os.environ.get("COURIER_SERVER", "http://127.0.0.1:8080").rstrip("/")
    api_key = os.environ.get("COURIER_API_KEY")
    if not api_key:
        print("ERROR: COURIER_API_KEY environment variable is not set.", file=sys.stderr)
        sys.exit(1)
    return server, api_key

def make_request(method, endpoint, payload=None):
    server, api_key = get_config()
    url = f"{server}{endpoint}"
    headers = {"Authorization": f"Bearer {api_key}"}
    if payload is not None:
        headers["Content-Type"] = "application/json"
    
    try:
        if method == "GET":
            res = requests.get(url, headers=headers, timeout=10)
        else:
            res = requests.post(url, json=payload, headers=headers, timeout=10)
        
        if res.status_code == 404 and "application/json" not in res.headers.get("Content-Type", ""):
            return None, 404
            
        try:
            return res.json(), res.status_code
        except json.JSONDecodeError:
            return res.text, res.status_code
    except requests.exceptions.RequestException as e:
        print(f"ERROR: Connection to Courier Server failed: {e}", file=sys.stderr)
        sys.exit(1)

def print_result(data, as_json):
    if as_json:
        print(json.dumps(data, indent=2))
    else:
        if isinstance(data, dict):
            for k, v in data.items():
                print(f"{k.upper()}: {v}")
        else:
            print(data)

def cmd_submit(args):
    payload = {"goal_text": args.goal}
    data, status = make_request("POST", "/goals", payload)
    if status == 200:
        if not args.json:
            print(f"Goal submitted successfully. ID: {data.get('goal_id')}")
        else:
            print_result(data, True)
    else:
        print(f"ERROR: Failed to submit goal (HTTP {status})", file=sys.stderr)
        print_result(data, args.json)

def cmd_status(args):
    data, status = make_request("GET", "/status")
    if status == 200:
        if not args.json:
            print("--- COURIER SYSTEM STATUS ---")
        print_result(data, args.json)
    else:
        print(f"ERROR: Failed to get status (HTTP {status})", file=sys.stderr)
        print_result(data, args.json)

def cmd_goal(args):
    data, status = make_request("GET", f"/goals/{args.id}")
    if status == 200:
        if not args.json:
            goal = data.get("goal", {})
            tasks = data.get("tasks", [])
            print(f"--- GOAL {args.id} ---")
            print(f"Status: {goal.get('status')}")
            print(f"Text: {goal.get('goal_text')}")
            print("Plan Steps:")
            for i, step in enumerate(goal.get("workflow_plan", [])):
                print(f"  [{i+1}] Task: {step.get('task_id')} | Target: {step.get('target_agent')} | Status: {step.get('status')}")
                if step.get('worker_id'):
                    print(f"        Worker: {step.get('worker_id')}")
            if tasks:
                print("Task Executions:")
                for t in tasks:
                    print(f"  Task: {t.get('task_id')} | Worker: {t.get('worker_id')} | Status: {t.get('status')} | Attempts: {t.get('attempts', 0)}")
        else:
            print_result(data, True)
    else:
        print(f"ERROR: Failed to get goal (HTTP {status})", file=sys.stderr)
        print_result(data, args.json)

def cmd_workers(args):
    data, status = make_request("GET", "/workers")
    if status == 404:
        if args.json:
            print(json.dumps({"error": "Missing server endpoint GET /workers"}, indent=2))
        else:
            print("ERROR: Server is missing endpoint GET /workers")
            print("Handoff: The server needs a read endpoint to list workers.")
    elif status == 200:
        print_result(data, args.json)
    else:
        print(f"ERROR: Failed to get workers (HTTP {status})", file=sys.stderr)
        print_result(data, args.json)

def cmd_health(args):
    data, status = make_request("GET", "/health")
    if status == 200:
        if not args.json:
            print("Server is HEALTHY.")
        else:
            print_result(data, True)
    else:
        print(f"ERROR: Server health check failed (HTTP {status})", file=sys.stderr)
        print_result(data, args.json)

def cmd_wall(args):
    data, status = make_request("GET", "/walls")
    if status == 404:
        if args.json:
            print(json.dumps({"error": "Missing server endpoint GET /walls"}, indent=2))
        else:
            print("ERROR: Server is missing endpoint GET /walls")
            print("Handoff: The server needs a read endpoint to list external walls/blocked goals.")
    elif status == 200:
        print_result(data, args.json)
    else:
        print(f"ERROR: Failed to get walls (HTTP {status})", file=sys.stderr)
        print_result(data, args.json)

def main():
    parser = argparse.ArgumentParser(description="Courier CLI Operator Client")
    parser.add_argument("--json", action="store_true", help="Output in JSON format")
    
    subparsers = parser.add_subparsers(dest="command", required=True)
    
    parser_submit = subparsers.add_parser("submit", help="Submit a new goal")
    parser_submit.add_argument("goal", help="The goal text")
    
    parser_status = subparsers.add_parser("status", help="Get system status")
    
    parser_goal = subparsers.add_parser("goal", help="Get specific goal details")
    parser_goal.add_argument("id", help="Goal ID")
    
    parser_workers = subparsers.add_parser("workers", help="List registered workers")
    
    parser_health = subparsers.add_parser("health", help="Check server health")
    
    parser_wall = subparsers.add_parser("wall", help="List external walls")
    
    args = parser.parse_args()
    
    if args.command == "submit":
        cmd_submit(args)
    elif args.command == "status":
        cmd_status(args)
    elif args.command == "goal":
        cmd_goal(args)
    elif args.command == "workers":
        cmd_workers(args)
    elif args.command == "health":
        cmd_health(args)
    elif args.command == "wall":
        cmd_wall(args)

if __name__ == "__main__":
    main()
