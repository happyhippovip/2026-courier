#!/usr/bin/env python3
"""
CLI tool: Verbindliche Prüfung des Windows-Hostnamens gemäß FRZ-01.
Gibt Exit-Code 0 bei validem Hostnamen, Exit-Code 1 bei Mismatch oder unautorisiertem Host.
"""
import argparse
import sys
import os

repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

try:
    from scripts.host_guardian import verify_windows_hostname, AUTHORIZED_WINDOWS_HOSTNAMES
except ImportError:
    from host_guardian import verify_windows_hostname, AUTHORIZED_WINDOWS_HOSTNAMES



def verify_host(expected_hostname=None, require_windows=True):
    expected = expected_hostname if expected_hostname else AUTHORIZED_WINDOWS_HOSTNAMES
    valid, details = verify_windows_hostname(expected_hostname=expected, require_windows=require_windows)

    if valid:
        print(f"WINDOWS HOSTNAME VALID: '{details}' matches authorized host configuration.")
        return 0
    else:
        print(f"WINDOWS HOSTNAME FAILED (REFUSED): {details}")
        return 1


def main():
    parser = argparse.ArgumentParser(description="Verbindliche Prüfung des Windows-Hostnamens.")
    parser.add_argument("--expected-host", type=str, default=None, help="Erwarteter Hostname (default: autorisierter Host)")
    parser.add_argument("--require-windows", action="store_true", default=True, help="Erfordert Windows OS (default: True)")
    parser.add_argument("--allow-any-os", dest="require_windows", action="store_false", help="Erlaube Nicht-Windows OS für Tests")
    args = parser.parse_args()

    rc = verify_host(expected_hostname=args.expected_host, require_windows=args.require_windows)
    sys.exit(rc)


if __name__ == "__main__":
    main()
