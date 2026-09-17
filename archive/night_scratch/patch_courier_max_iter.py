import sys
content = open("scripts/courier_continue.py").read()

content = content.replace(
'''def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", action="store_true", help="Run unattended mode")
    parser.add_argument("--once", action="store_true", help="Run once and exit")
    args = parser.parse_args()''',
'''def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", action="store_true", help="Run unattended mode")
    parser.add_argument("--once", action="store_true", help="Run once and exit")
    args = parser.parse_args()
    
    mock_iters = 0''')

content = content.replace(
'''            if args.once or "MOCK_SHA" in os.environ:
                sys.exit(0)
            import time
            time.sleep(10)
            continue''',
'''            if args.once:
                sys.exit(0)
            if "MOCK_SHA" in os.environ:
                mock_iters += 1
                if mock_iters >= 3:
                    sys.exit(0)
            import time
            time.sleep(0.01)
            continue''')

content = content.replace(
'''        if args.once or "MOCK_SHA" in os.environ:
            sys.exit(0)
        import time
        time.sleep(10)''',
'''        if args.once:
            sys.exit(0)
        if "MOCK_SHA" in os.environ:
            mock_iters += 1
            if mock_iters >= 3:
                sys.exit(0)
        import time
        time.sleep(0.01)''')

open("scripts/courier_continue.py", "w").write(content)
