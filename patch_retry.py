with open("scripts/courier_continue.py", "r") as f:
    code = f.read()

retry_code = """
                    branch, sha = get_git_info()
                    for _retry in range(5):
                        bundle = check_freshness(ledger_path, branch, sha)
                        try:
                            bundle = update_ledger(ledger_path, task["edge_name"], new_blocker, bundle)
                            break
                        except Exception as e:
                            if "meaningful change" in str(e):
                                break
                            if "revision conflict" in str(e):
                                import time, random
                                time.sleep(0.5 + random.random())
                                continue
                            raise e
"""

import re
code = re.sub(r"                    branch, sha = get_git_info\(\)\n                    bundle = check_freshness\(ledger_path, branch, sha\)\n                    try:\n                        bundle = update_ledger\(ledger_path, task\[\"edge_name\"\], new_blocker, bundle\)\n                    except Exception as e:\n                        print\(f\"Exception in update_ledger: \{type\(e\)\} \{e\}\"\)\n                        if \"meaningful change\" not in str\(e\):\n                            raise e", retry_code.strip('\n'), code)

with open("scripts/courier_continue.py", "w") as f:
    f.write(code)
