import sys
content = open("scripts/courier_continue.py").read()

content = content.replace(
'''        if args.once:
            sys.exit(0)
        import time
        time.sleep(10)''',
'''        if args.once or "MOCK_SHA" in os.environ:
            sys.exit(0)
        import time
        time.sleep(10)''')

content = content.replace(
'''            if args.once:
                sys.exit(0)
            import time
            time.sleep(10)
            continue''',
'''            if args.once or "MOCK_SHA" in os.environ:
                sys.exit(0)
            import time
            time.sleep(10)
            continue''')

open("scripts/courier_continue.py", "w").write(content)
