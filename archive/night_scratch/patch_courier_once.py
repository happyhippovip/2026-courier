import sys
content = open("scripts/courier_continue.py").read()

content = content.replace(
'''def main():
    import argparse
    parser = argparse.ArgumentParser(description="Courier Autonomous Loop")
    parser.add_argument("--run", action="store_true", help="Execute tasks (otherwise dry-run)")
    args = parser.parse_args()''',
'''def main():
    import argparse
    parser = argparse.ArgumentParser(description="Courier Autonomous Loop")
    parser.add_argument("--run", action="store_true", help="Execute tasks (otherwise dry-run)")
    parser.add_argument("--once", action="store_true", help="Run once and exit (for testing)")
    args = parser.parse_args()''')

content = content.replace(
'''            import time
            time.sleep(10)
            continue''',
'''            if args.once:
                sys.exit(0)
            import time
            time.sleep(10)
            continue''')

content = content.replace(
'''        import time
        time.sleep(10)''',
'''        if args.once:
            sys.exit(0)
        import time
        time.sleep(10)''')

open("scripts/courier_continue.py", "w").write(content)
