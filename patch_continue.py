import re

with open("scripts/courier_continue.py", "r") as f:
    content = f.read()

content = content.replace(
    'from scripts.agent_handoff_ledger import freshness, load_bundle, update',
    'from scripts.agent_handoff_ledger import freshness, load_bundle, update, NoMeaningfulChangeError, RevisionConflictError'
)

old_try = '''                        try:
                            bundle = update_ledger(ledger_path, task["edge_name"], new_blocker, bundle)
                            break
                        except Exception as e:
                            if "meaningful change" in str(e):
                                break
                            if "revision conflict" in str(e):
                                import time, random
                                time.sleep(0.5 + random.random())
                                continue
                            print(f"Failed to update ledger for {task['edge_name']}: {e}")
                            break'''

new_try = '''                        try:
                            bundle = update_ledger(ledger_path, task["edge_name"], new_blocker, bundle)
                            break
                        except NoMeaningfulChangeError:
                            break
                        except RevisionConflictError:
                            import time, random
                            time.sleep(0.5 + random.random())
                            continue
                        except Exception as e:
                            print(f"Failed to update ledger for {task['edge_name']}: {e}")
                            break'''

content = content.replace(old_try, new_try)

with open("scripts/courier_continue.py", "w") as f:
    f.write(content)
