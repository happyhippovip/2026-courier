with open("scripts/courier_continue.py", "r") as f:
    code = f.read()

code = code.replace("""                    bundle = update_ledger(ledger_path, task["edge_name"], new_blocker, bundle)""", """                    try:
                        bundle = update_ledger(ledger_path, task["edge_name"], new_blocker, bundle)
                    except Exception as e:
                        print(f"Exception in update_ledger: {type(e)} {e}")""")

code = code.replace("""            if args.once and not running_tasks and 'once_dispatched' in locals():
                sys.exit(0)""", """            if args.once and not running_tasks and 'once_dispatched' in locals():
                sys.exit(0)""") # Keeping this intact for now, wait!

# Wait, if we want to exit immediately after all tasks are done:
# I will just remove the `mock_iters` limitation and exit when `not running_tasks` IF we already dispatched once!
# Wait! "once_dispatched" was added by me in a previous session!
# Actually, I'll just change `mock_iters >= 15` to `mock_iters >= 3`!

code = code.replace("mock_iters >= 15", "mock_iters >= 3")

with open("scripts/courier_continue.py", "w") as f:
    f.write(code)
