import sys
content = open("scripts/courier_continue.py").read()

content = content.replace(
'''def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", action="store_true", help="Run unattended mode")
    args = parser.parse_args()''',
'''def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", action="store_true", help="Run unattended mode")
    parser.add_argument("--once", action="store_true", help="Run once and exit")
    args = parser.parse_args()''')

open("scripts/courier_continue.py", "w").write(content)
