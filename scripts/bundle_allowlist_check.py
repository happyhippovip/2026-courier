"""Check a runtime bundle manifest against the explicit customer-runtime allowlist.

Default deny: a file may ship only if an allow pattern names it and no deny pattern matches.
Deny always wins, so a broad allow can never carry fleet tooling, internal strategy, runtime
state or secrets onto a customer machine. Every violation is reported, not only the first.
"""
import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

DEFAULT_ALLOWLIST = Path(__file__).resolve().parent.parent / "acceptance" / "runtime_allowlist.yaml"


def load_allowlist(path=DEFAULT_ALLOWLIST):
    text = Path(path).read_text(encoding="utf-8")
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        import yaml  # only needed when the allowlist is not written in JSON syntax

        data = yaml.safe_load(text)
    if not data.get("allow"):
        raise ValueError("allowlist has no allow patterns")
    return data


def pattern_to_regex(pattern):
    """`**` crosses folders; `*` and `?` stay inside one path segment."""
    out, i, pattern = [], 0, pattern.replace("\\", "/").lower()
    while i < len(pattern):
        if pattern.startswith("**/", i):
            out.append("(?:.*/)?")
            i += 3
        elif pattern.startswith("**", i):
            out.append(".*")
            i += 2
        elif pattern[i] == "*":
            out.append("[^/]*")
            i += 1
        elif pattern[i] == "?":
            out.append("[^/]")
            i += 1
        else:
            out.append(re.escape(pattern[i]))
            i += 1
    return re.compile("^" + "".join(out) + "$")


def normalize(path):
    return str(path).replace("\\", "/").strip()


def unsafe_reason(path):
    if not path:
        return "empty path"
    if path.startswith("/") or re.match(r"^[A-Za-z]:", path):
        return "absolute path"
    if any(part in ("..", ".") for part in path.split("/")):
        return "path leaves the bundle"
    return None


def manifest_paths(manifest):
    """Accept a list of paths, a list of {path: ...} objects, or {files: [...]}."""
    entries = manifest.get("files", []) if isinstance(manifest, dict) else manifest
    return [normalize(entry["path"] if isinstance(entry, dict) else entry) for entry in entries]


def read_manifest(path):
    text = Path(path).read_text(encoding="utf-8")
    try:
        return manifest_paths(json.loads(text))
    except json.JSONDecodeError:
        return [normalize(line) for line in text.splitlines() if line.strip()]


def manifest_from_dir(root):
    root = Path(root)
    files = []
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        files.append({"path": path.relative_to(root).as_posix(), "bytes": path.stat().st_size,
                      "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
    return {"files": files}


def check(paths, allowlist):
    allow = [pattern_to_regex(pattern) for pattern in allowlist["allow"]]
    deny = [(pattern_to_regex(entry["pattern"]), entry) for entry in allowlist.get("deny", [])]
    violations = []
    if not paths:
        violations.append({"path": "", "reason": "empty manifest", "class": "manifest"})
    for original in paths:
        path = normalize(original)
        unsafe = unsafe_reason(path)
        if unsafe:
            violations.append({"path": path, "reason": unsafe, "class": "unsafe-path"})
            continue
        key = path.lower()
        denied = next((entry for regex, entry in deny if regex.match(key)), None)
        if denied:
            violations.append({"path": path, "reason": f"denied by {denied['pattern']}", "class": denied["class"]})
        elif not any(regex.match(key) for regex in allow):
            violations.append({"path": path, "reason": "not on the allowlist", "class": "unlisted"})
    by_class = {}
    for violation in violations:
        by_class[violation["class"]] = by_class.get(violation["class"], 0) + 1
    return {"ok": not violations, "checked": len(paths), "violation_count": len(violations),
            "violations_by_class": dict(sorted(by_class.items())), "violations": violations}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--manifest", help="JSON manifest or a text file with one path per line")
    source.add_argument("--from-dir", help="build the manifest from an unpacked bundle directory")
    parser.add_argument("--allowlist", default=str(DEFAULT_ALLOWLIST))
    parser.add_argument("--write-manifest", help="with --from-dir: write the manifest (path, bytes, sha256) here")
    parser.add_argument("--max-listed", type=int, default=40, help="violations printed in full (all are counted)")
    args = parser.parse_args(argv)
    allowlist = load_allowlist(args.allowlist)
    if args.from_dir:
        manifest = manifest_from_dir(args.from_dir)
        if args.write_manifest:
            Path(args.write_manifest).write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        paths = manifest_paths(manifest)
    else:
        paths = read_manifest(args.manifest)
    report = check(paths, allowlist)
    printed = dict(report, violations=report["violations"][:args.max_listed])
    print(json.dumps(printed, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
