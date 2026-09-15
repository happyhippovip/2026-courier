with open("social_platform/client/interactive.py", "r") as f:
    text = f.read()

cmd_logic = """        elif cmd in ("push-list", "push-devices"):
            if not self.session:
                print("Please login first.")
                return
            subs = self.session.list_push_subscriptions()
            print(f"\\n--- Registered Push Devices ({len(subs)}) ---")
            for s in subs:
                print(f"[{s.get('id')}] Platform: {s.get('platform')} | Endpoint: {s.get('endpoint')}")
        elif cmd == "genesis-registry":
            blocks = self.client.get_genesis_registry()
            print(f"\\n--- POW-001 Genesis Sponsorship Blocks ---")
            for block_id in range(1, 22):
                block_id_str = str(block_id)
                data = blocks.get(block_id_str)
                if data is None:
                    print(f"[{block_id_str}] AVAILABLE (499 EUR)")
                else:
                    print(f"[{block_id_str}] RESERVED by {data.get('company_name')} (Status: {data.get('status')})")
        elif cmd == "genesis-reserve":
            if len(args) < 1:
                print("Usage: genesis-reserve <company_name> [logo_url]")
                return
            company_name = args[0]
            logo_url = args[1] if len(args) > 1 else ""
            res = self.client.reserve_genesis_block(company_name, logo_url)
            if res.get("status") == "success":
                inv = res.get("invoice", {})
                print(f"Success! Block {res.get('block_id')} reserved for {company_name}.")
                print(f"Invoice ID: {inv.get('invoice_id')}")
                print(f"Send {inv.get('amount_btc')} BTC to {inv.get('btc_address')}")
            else:
                print(f"Error: {res.get('message')}")
        else:"""

if "genesis-registry" not in text:
    text = text.replace('        elif cmd in ("push-list", "push-devices"):\n            if not self.session:\n                print("Please login first.")\n                return\n            subs = self.session.list_push_subscriptions()\n            print(f"\\n--- Registered Push Devices ({len(subs)}) ---")\n            for s in subs:\n                print(f"[{s.get(\'id\')}] Platform: {s.get(\'platform\')} | Endpoint: {s.get(\'endpoint\')}")\n        else:', cmd_logic)

help_logic = """        print("  communities                   - List communities")
        print("  genesis-registry              - View 21 POW-001 Genesis blocks")
        print("  genesis-reserve <company>     - Reserve next available Genesis block")
        print("  exit                          - Exit console\\n")"""

if "genesis-registry" not in text: # It might already be in if the first replace worked, but wait, we need to check both independently
    pass

# We will just replace it directly
text = text.replace('        print("  communities                   - List communities")\n        print("  exit                          - Exit console\\n")', help_logic)

with open("social_platform/client/interactive.py", "w") as f:
    f.write(text)
