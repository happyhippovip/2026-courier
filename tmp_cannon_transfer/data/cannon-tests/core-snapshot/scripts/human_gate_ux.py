#!/usr/bin/env python3
import sys
import json
import getpass
import datetime

def run_human_gate(payload_file):
    with open(payload_file, 'r') as f:
        data = json.load(f)
        
    print("\n" + "="*50)
    print("🚨 HUMAN GATE APPROVAL REQUIRED 🚨")
    print("="*50)
    print(f"ACTION PROPOSED:  {data.get('action')}")
    print(f"ARTIFACTS/CODE:   {', '.join(data.get('artifacts', []))}")
    print(f"WHY REQUIRED:     {data.get('reason')}")
    print("="*50)
    
    while True:
        try:
            resp = input("Do you approve this action? (APPROVE/REJECT): ").strip().upper()
        except EOFError:
            # Handle non-interactive environments
            print("Non-interactive environment detected. Auto-rejecting protected action.")
            sys.exit(1)
            
        if resp == 'APPROVE':
            identity = getpass.getuser()
            timestamp = datetime.datetime.now().isoformat()
            print(f"\n[+] Action APPROVED by {identity} at {timestamp}")
            
            # Record approval
            approval_record = {
                "status": "APPROVED",
                "identity": identity,
                "timestamp": timestamp,
                "action": data.get('action')
            }
            with open(f"{payload_file}.approval", 'w') as out:
                json.dump(approval_record, out)
                
            sys.exit(0)
        elif resp == 'REJECT':
            print("\n[-] Action REJECTED.")
            sys.exit(1)
        else:
            print("Please type 'APPROVE' or 'REJECT'.")

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python3 human_gate_ux.py <gate_payload.json>")
        sys.exit(1)
    run_human_gate(sys.argv[1])
