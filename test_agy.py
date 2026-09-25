"""Manual agy probe (NOT part of the automated suite).

Run directly: ``python3 test_agy.py``. Importing this module must have
no side effects so bare ``pytest`` collection from the repo root stays
clean (previously it spawned an ``agy`` subprocess at import time).
"""
import subprocess


def main():
    cmd = [
        "agy",
        "-p", "test prompt",
        "--dangerously-skip-permissions"
    ]
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    stdout, stderr = process.communicate()
    print("RC:", process.returncode)
    print("STDOUT:", stdout)
    print("STDERR:", stderr)


if __name__ == "__main__":
    main()
