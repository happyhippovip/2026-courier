#!/usr/bin/env python3
"""Read-only ratchet for two proven Windows field incidents.

1. Name-based process kills. Cleanup by executable name (``Stop-Process -Name
   python``, ``taskkill /IM``, ``pkill``, ``killall``) terminated unrelated
   PowerShell, Python, IDE and agent sessions. Courier may only stop the exact
   process tree it started and recorded (PID plus start identity, Job Object).
2. Wildcard binds. Local services bound ``0.0.0.0`` or ``""`` and triggered
   repeated firewall prompts. Local Courier services bind loopback only.

The scan prints every finding. With ``--baseline`` it fails only on findings
that are not in the baseline, so existing debt is visible but new debt is
blocked; ``--write-baseline`` records the current findings. Standard library
only, never executes or imports the scanned code.
"""
import argparse
import hashlib
import json
import os
import re
import sys

SCANNED_SUFFIXES = (".py", ".ps1", ".psm1", ".bat", ".cmd", ".sh", ".cs", ".yml", ".yaml")
SKIPPED_DIRS = {".git", "__pycache__", "node_modules", "attic", "runtime", "docs", "venv", ".venv",
                "dist", "site-packages",  # build output and vendored third-party code
                "tests"}  # tests use these commands as data for guard tests

RULES = {
    "KILL_BY_NAME": [
        re.compile(r"Stop-Process\b[^\n#]*\s-(Name|ProcessName)\b", re.I),
        # shell form and argv-list form: taskkill /F /IM x, ["taskkill", "/IM", "x"]
        re.compile(r"""\btaskkill\b[^\n]*[\s'",]/IM\b""", re.I),
        re.compile(r"""(^|[\s;&|(`'"\[])(pkill|killall)(\s|['"])""", re.I),
        re.compile(r"Get-Process\b[^\n|]*\|[^\n]*Stop-Process", re.I),
        # psutil scan that kills by name on the same line
        re.compile(r"""\.name\(\)[^\n]*\.(kill|terminate)\(""", re.I),
    ],
    "WILDCARD_BIND": [
        # a 0.0.0.0 literal in code is a bind address in practice; "::" only in bind context
        re.compile(r"""['"]0\.0\.0\.0['"]"""),
        re.compile(r"""(host\s*=\s*|bind\(\s*\(\s*)['"]::['"]"""),
        re.compile(r"""--host[\s=]+['"]?0\.0\.0\.0"""),
        re.compile(r"""(\s-b|--bind)[\s=]+['"]?(0\.0\.0\.0|\[::\])"""),
        re.compile(r"""(TCPServer|HTTPServer|ThreadingHTTPServer|bind)\(\s*\(\s*['"]['"]\s*,"""),
        re.compile(r"""IPAddress\.(Any|IPv6Any)\b"""),
    ],
}

# Whole-line comments describe the rules; they are never executed.
COMMENT_LINE = re.compile(r"^\s*(#|//|::|REM\b|rem\b)")

# A reviewed exception carries its reason on the same line:
#   subprocess.run(["taskkill", "/IM", ...])  # local-safety: allow <reason>
ALLOW_PRAGMA = re.compile(r"local-safety:\s*allow\s+\S")

# Credential-shaped substrings must never leave this module inside finding
# text: findings print to CI logs and feed customer reports. Patterns mirror
# scripts/repo_reality_check.py SECRET_PATTERNS (+ e-mail); that module owns
# the canonical set and already imports this file, so this ratchet keeps a
# local copy instead of creating a circular import.
_SCRUB_PATTERNS = (
    re.compile(r"\b(ghp|gho|ghs|ghu)_[A-Za-z0-9]{30,}\b|\bgithub_pat_[A-Za-z0-9_]{40,}\b"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"-----BEGIN (RSA |EC |OPENSSH |)PRIVATE KEY-----"),
    re.compile(r"\bxox[abpr]-[A-Za-z0-9-]{10,}\b"),
    re.compile(r"\bsk-[A-Za-z0-9]{32,}\b"),
    re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
)
REDACTED = "[redacted]"


def scrub_credential_shapes(text):
    """Replace credential-shaped substrings with a marker (see above)."""
    for pattern in _SCRUB_PATTERNS:
        text = pattern.sub(REDACTED, text)
    return text


def iter_files(root):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIPPED_DIRS)
        for name in sorted(filenames):
            if name.endswith(SCANNED_SUFFIXES):
                yield os.path.join(dirpath, name)


def scan_text(text):
    """Yield (rule, line_number, stripped_line) for every rule hit in text."""
    for number, line in enumerate(text.splitlines(), 1):
        if ALLOW_PRAGMA.search(line) or COMMENT_LINE.match(line):
            continue
        for rule, patterns in RULES.items():
            if any(p.search(line) for p in patterns):
                yield rule, number, line.strip()


def finding_key(rule, relpath, line):
    """Stable across line moves: rule + file + normalized line text."""
    digest = hashlib.sha256(" ".join(line.split()).encode("utf-8")).hexdigest()[:16]
    return f"{rule}:{relpath}:{digest}"


def scan(root, skip=()):
    """skip: absolute paths never scanned (compared with os.path.normcase)."""
    skip = {os.path.normcase(os.path.abspath(p)) for p in skip}
    findings = []
    for path in iter_files(root):
        relpath = os.path.relpath(path, root).replace(os.sep, "/")
        if os.path.normcase(os.path.abspath(path)) in skip:
            continue
        try:
            with open(path, encoding="utf-8", errors="replace") as handle:
                text = handle.read()
        except OSError:
            continue
        for rule, number, line in scan_text(text):
            findings.append({"rule": rule, "path": relpath, "line": number,
                             "text": scrub_credential_shapes(line[:200]),
                             "key": finding_key(rule, relpath, line)})
    return findings


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("root", nargs="?", default=".")
    parser.add_argument("--baseline", help="JSON list of accepted finding keys")
    parser.add_argument("--write-baseline", help="write current finding keys to this file and exit 0")
    args = parser.parse_args(argv)

    # The checker and its tests name the forbidden patterns; never flag them.
    here = os.path.abspath(__file__)
    own = {here, os.path.join(os.path.dirname(os.path.dirname(here)), "tests", "test_check_local_safety.py")}
    # Absolute paths: relpath across drives raises on Windows (repo on D:, temp on C:).
    findings = scan(args.root, skip=own)

    for f in findings:
        print(f"{f['rule']} {f['path']}:{f['line']}: {f['text']}")
    print(f"total={len(findings)} kill_by_name={sum(f['rule'] == 'KILL_BY_NAME' for f in findings)} "
          f"wildcard_bind={sum(f['rule'] == 'WILDCARD_BIND' for f in findings)}")

    if args.write_baseline:
        with open(args.write_baseline, "w", encoding="utf-8") as handle:
            json.dump(sorted({f["key"] for f in findings}), handle, indent=1)
            handle.write("\n")
        return 0
    if args.baseline:
        with open(args.baseline, encoding="utf-8") as handle:
            accepted = set(json.load(handle))
        new = [f for f in findings if f["key"] not in accepted]
        for f in new:
            print(f"NEW {f['rule']} {f['path']}:{f['line']}: {f['text']}")
        print(f"new={len(new)}")
        return 1 if new else 0
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
