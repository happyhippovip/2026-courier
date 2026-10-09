#!/usr/bin/env python3
"""Repo Reality Check: the delivery tool behind the first paid offer.

Read-only scan of a local git checkout. Produces report.json + report.md
with findings a small team can act on in a day:

  workflows    CI hygiene (reuses scripts/revenue_v1_safety_baseline.py rules)
               + actions pinned by tag instead of commit SHA, curl|sh in CI
  safety       kill-by-name and wildcard binds (scripts/check_local_safety.py)
  hygiene      tracked runtime/session/log/db/env files, large files,
               committed binaries, gitlinks without .gitmodules
  supply       missing lockfile / hashes
  secrets      credential-shaped strings: file, line and pattern TYPE only -
               the value is never read into the report

It never executes the customer's code and never sends anything anywhere.
Every report answers the customer's first questions itself (what it means,
how to fix it, how long it takes), says what was NOT checked, and carries a
digest that anyone can re-verify against the same commit.

Usage: python scripts/repo_reality_check.py <checkout> <out_dir>
       python scripts/repo_reality_check.py --verify <report.json> <checkout>
"""
import hashlib
import html
import json
import os
import re
import subprocess
import sys
import os
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from ci_truth import run_ci_truth
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts.check_local_safety import scan as scan_local_safety  # noqa: E402
from scripts.revenue_v1_safety_baseline import analyze_workflows  # noqa: E402

LARGE_FILE_BYTES = 5 * 1024 * 1024
BINARY_SUFFIXES = (".exe", ".dll", ".so", ".dylib", ".zip", ".7z", ".msi", ".jar", ".whl")
RUNTIME_PATTERNS = [re.compile(p) for p in (
    r"(^|/)(sessions?|session-index|local-tracing|\.tmp_pytest|__pycache__|node_modules)/",
    r"\.(sqlite3?|db|db-wal|db-shm|log|pyc)$", r"(^|/)\.env(\..*)?$", r"\.(pem|key|p12|pfx)$")]
SECRET_PATTERNS = {
    "github_token": re.compile(r"\b(ghp|gho|ghs|ghu)_[A-Za-z0-9]{30,}\b|\bgithub_pat_[A-Za-z0-9_]{40,}\b"),
    "aws_access_key": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    "private_key_block": re.compile(r"-----BEGIN (RSA |EC |OPENSSH |)PRIVATE KEY-----"),
    "slack_token": re.compile(r"\bxox[abpr]-[A-Za-z0-9-]{10,}\b"),
    "openai_style_key": re.compile(r"\bsk-[A-Za-z0-9]{32,}\b"),
}
EMAIL = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
TOOL_VERSION = "rrc-2"
_SECRET_GUIDE = ("A credential-shaped string is in the repository. If it is real, anyone with read access can use it.",
                 "Revoke and rotate it at the provider first, then remove it from the code and load it from the environment "
                 "or a secret store. Removing it from history alone is not enough - rotate.", "30-60 min per secret")
GUIDE = {  # rule -> (what it means, how to fix, typical effort)
    **{kind: _SECRET_GUIDE for kind in ("github_token", "aws_access_key", "private_key_block", "slack_token",
                                         "openai_style_key")},
    "WILDCARD_BIND": ("A server listens on all network interfaces, so other machines on the network (or the internet) "
                      "can reach it.", "Bind to 127.0.0.1 by default; open it only through an explicit setting.", "15 min"),
    "KILL_BY_NAME": ("Processes are stopped by name, which can kill unrelated programs with the same name.",
                     "Record the process id (plus start time) when starting and stop exactly that process.", "1-2 h"),
    "curl_pipe_shell": ("CI downloads a script and runs it unseen; whoever controls that URL controls your build.",
                        "Download a pinned version, verify its checksum, then run it.", "30 min"),
    "action_pinned_by_tag": ("A CI action is referenced by a movable tag; the tag can be moved to different code.",
                             "Pin to the full commit SHA (a comment can keep the version name).", "10 min per action"),
    "generated_or_private_file_tracked": ("A file that is usually private or generated is committed.",
                                          "Remove it from git, add it to .gitignore; rotate anything secret it held.",
                                          "15 min"),
    "binary_committed": ("A binary is committed without a record of how it was built, so nobody can check what it contains.",
                         "Build it in CI from source, or document its source and checksum.", "1 h"),
    "large_file": ("A large file slows every clone.", "Move it to release assets or Git LFS.", "30 min"),
    "gitlink_without_gitmodules": ("Embedded repositories without .gitmodules break fresh checkouts.",
                                   "Add a proper .gitmodules or remove the embedded repos.", "30 min"),
    "pinned_without_hashes": ("Versions are pinned but not hash-checked.",
                              "Generate hashes (pip-compile --generate-hashes or uv) and install with --require-hashes.",
                              "30 min"),
    "test_data_archive": ("An archive is committed as test data.", "Fine if it is only data; keep it small and documented.",
                          "–"),
    "no_lockfile": ("There is no lockfile, so an install can pull in a new release nobody reviewed. "
                    "(Normal for libraries; important for applications and bots.)",
                    "Commit a lockfile (or hashed requirements) and install from it.", "30-60 min"),
    "permissions": ("A workflow has broad default token permissions.", "Set `permissions:` to the minimum per job.", "15 min"),
    "timeout": ("A CI job has no timeout and can hang for hours.", "Set `timeout-minutes` per job.", "5 min"),
    "concurrency": ("Parallel runs can overlap and race.", "Add a `concurrency` group.", "5 min"),
    "runner_type": ("Self-hosted or unusual runner configuration.", "Check that the runner is isolated and ephemeral.", "1 h"),
    "mutation_risk": ("A workflow can write to the repository or releases.", "Limit write steps to protected branches.",
                      "30 min"),
}
NOT_CHECKED = [
    "Smart contracts, cryptographic design and business logic were not audited.",
    "No code was executed and no running system, server or network was tested.",
    "Git history before this commit was not scanned; secrets removed earlier may still be in history.",
    "Dependencies were not checked for known vulnerabilities (CVE scan).",
    "Secret detection uses known patterns; unusual or custom secret formats can be missed.",
    "A clean report means 'nothing found by these checks', not 'secure'.",
]
LOCKFILES = ("poetry.lock", "uv.lock", "Pipfile.lock", "package-lock.json", "yarn.lock", "pnpm-lock.yaml",
             "Cargo.lock", "go.sum", "Gemfile.lock", "composer.lock")


def _looks_like_fixture(path, token):
    """Test data such as ghp_123456789012... or sk-abcdef...xyz0123456789: low entropy or a
    plain alphabet run, inside tests/. Reported as low, never hidden."""
    if not re.search(r"(^|/)tests?/", path):
        return False
    body = re.split(r"[-_]", token, maxsplit=1)[-1].lower()
    alphabet = "abcdefghijklmnopqrstuvwxyz0123456789"
    return len(set(body)) <= 12 or body[:12] in alphabet + alphabet or token.startswith("-----BEGIN")


KEY_BODY = re.compile(r"[A-Za-z0-9+/=]{64,}")


def _has_key_body(lines, n, line):
    """A PEM header alone (code that builds or strips headers, docs with <...>
    placeholders) is not a leak; a real key has a long base64 body right after."""
    after = line.split("PRIVATE KEY-----", 1)[-1]
    return bool(KEY_BODY.search(after.replace("\\n", ""))) or any(KEY_BODY.search(l) for l in lines[n:n + 3])


def git_files(repo):
    out = subprocess.run(["git", "-C", str(repo), "ls-files", "-s"], capture_output=True, text=True, check=True).stdout
    entries = []
    for line in out.splitlines():
        meta, path = line.split("\t", 1)
        entries.append((meta.split()[0], path))
    return entries


def head_sha(repo):
    out = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"], capture_output=True, text=True)
    return out.stdout.strip() if out.returncode == 0 else "uncommitted"


def leak_check(text):
    """Second pass over the finished report: secret shapes or e-mail addresses
    must never reach the customer file. Returns the kinds found (never values)."""
    kinds = [kind for kind, pattern in SECRET_PATTERNS.items() if pattern.search(text)]
    if EMAIL.search(text):
        kinds.append("email_address")
    return kinds


def check(repo, run_ci=False):
    repo = Path(repo).resolve()
    entries = git_files(repo)
    files = [p for mode, p in entries if mode != "160000"]
    findings = []

    def add(area, severity, rule, where, detail):
        findings.append({"area": area, "severity": severity, "rule": rule, "where": where, "detail": detail})

    for f in analyze_workflows(repo)["findings"]:
        add("workflows", "medium", f["rule"], f".github/workflows/{f['file']}", f["issue"])
    for wf in sorted((repo / ".github" / "workflows").glob("*.y*ml")) if (repo / ".github" / "workflows").is_dir() else []:
        text = wf.read_text(encoding="utf-8", errors="replace")
        for n, line in enumerate(text.splitlines(), 1):
            m = re.search(r"uses:\s*([\w.-]+/[\w./-]+)@([\w.-]+)", line)
            if m and not re.fullmatch(r"[0-9a-f]{40}", m.group(2)):
                add("supply", "low", "action_pinned_by_tag", f"{wf.relative_to(repo)}:{n}", f"{m.group(1)}@{m.group(2)}")
            if re.search(r"curl[^|\n]*\|\s*(ba)?sh", line):
                add("supply", "high", "curl_pipe_shell", f"{wf.relative_to(repo)}:{n}", "remote script piped to a shell")

    checker = Path(__file__).resolve().parent / "check_local_safety.py"
    for f in scan_local_safety(str(repo), skip={str(checker), str(repo / "scripts" / "check_local_safety.py")}):
        acknowledged = re.search(r"#\s*(noqa:\s*S10[0-9]|nosec)", f["text"])
        severity = "low" if acknowledged else "high" if f["rule"] == "KILL_BY_NAME" else "medium"
        detail = ("acknowledged in code by the maintainers: " if acknowledged else "") + f["text"][:120]
        add("safety", severity, f["rule"], f"{f['path']}:{f['line']}", detail)

    for path in files:
        if any(p.search(path) for p in RUNTIME_PATTERNS):
            add("hygiene", "high" if re.search(r"\.env|\.(pem|key|p12|pfx)$", path) else "medium",
                "generated_or_private_file_tracked", path, "tracked; usually belongs in .gitignore")
        full = repo / path
        try:
            size = full.stat().st_size
        except OSError:
            continue
        if path.lower().endswith(BINARY_SUFFIXES):
            if re.search(r"(^|/)(tests?|testdata|fixtures?)/", path) and path.lower().endswith((".zip", ".7z")):
                add("hygiene", "low", "test_data_archive", path, f"{size // 1024} KiB archive used as test data")
            else:
                add("hygiene", "medium", "binary_committed", path, f"{size // 1024} KiB without build provenance")
        elif size > LARGE_FILE_BYTES:
            add("hygiene", "low", "large_file", path, f"{size // (1024 * 1024)} MiB")
        if size <= 2 * 1024 * 1024:
            try:
                text = full.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            lines = text.splitlines()
            for n, line in enumerate(lines, 1):
                for kind, pattern in SECRET_PATTERNS.items():
                    m = pattern.search(line)
                    if m and kind == "private_key_block" and not _has_key_body(lines, n, line):
                        continue
                    if m and _looks_like_fixture(path, m.group(0)):
                        add("secrets", "low", kind, f"{path}:{n}", "test fixture shape (low entropy, in tests/)")
                    elif m:
                        add("secrets", "high", kind, f"{path}:{n}", "credential-shaped string (value not shown)")
    gitlinks = [p for mode, p in entries if mode == "160000"]
    if gitlinks and not (repo / ".gitmodules").exists():
        add("hygiene", "medium", "gitlink_without_gitmodules", ", ".join(gitlinks[:3]),
            f"{len(gitlinks)} embedded repos; breaks clean checkouts")

    names = {Path(p).name for p in files}
    has_py = any(p.endswith(".py") for p in files)
    if not names & set(LOCKFILES):
        hashed = any(n.startswith("requirements") and "--hash" in (repo / p).read_text(errors="replace")
                     for p in files for n in [Path(p).name] if n.startswith("requirements") and n.endswith(".txt"))
        reqs = [p for p in files if Path(p).name.startswith("requirements") and p.endswith(".txt")]
        deps = [l.split("#")[0].strip() for p in reqs for l in (repo / p).read_text(errors="replace").splitlines()]
        deps = [d for d in deps if d and not d.startswith("-")]
        pinned = deps and sum("==" in d for d in deps) / len(deps) >= 0.9
        if has_py and not hashed and pinned:
            add("supply", "low", "pinned_without_hashes", "requirements*.txt",
                "versions pinned with ==, but no hashes; a replaced release file would not be detected")
        elif has_py and not hashed:
            add("supply", "medium", "no_lockfile", "repository", "no lockfile; installs can pick up new, unreviewed releases")
    result = {"repository": repo.name, "sha": head_sha(repo), "tool": TOOL_VERSION, "files_scanned": len(files),
              "findings": findings,
              "summary": {sev: sum(f["severity"] == sev for f in findings) for sev in ("high", "medium", "low")}}
    
    if run_ci:
        try:
            ci_res = run_ci_truth(str(repo), result.get("sha", "HEAD"))
            result["ci_truth"] = ci_res
        except Exception as e:
            result["ci_truth"] = {"status": "error", "error": str(e)}
    
    result["digest"] = digest(result)
    return result


def digest(result):
    """Fingerprint of what was found on which commit with which tool version.
    Re-running the same tool on the same commit gives the same digest."""
    core = {k: result[k] for k in ("sha", "tool", "findings")}
    return hashlib.sha256(json.dumps(core, sort_keys=True).encode()).hexdigest()


def verify(report_path, repo):
    """True if the report matches a fresh run on the same checkout."""
    report = json.loads(Path(report_path).read_text(encoding="utf-8"))
    fresh = check(repo)
    return report.get("digest") == digest(report) == fresh["digest"]


def to_markdown(result):
    lines = [f"# Repo Reality Check — {result['repository']}", "",
             f"Commit: `{result.get('sha', 'unknown')}`", "",
             f"Files scanned: {result['files_scanned']} · high {result['summary']['high']} · "
             f"medium {result['summary']['medium']} · low {result['summary']['low']}", "",
             "Read-only scan; no code was executed. Secret findings show location and type only.", "",
             f"Tool: `{result.get('tool', '?')}` · Digest: `{result.get('digest', '?')}`  ",
             "Anyone can re-check this report: `python scripts/repo_reality_check.py --verify report.json <checkout>`", ""]
    rules = sorted({f["rule"] for f in result["findings"]})
    if rules:
        lines += ["## What the findings mean and how to fix them", ""]
        for rule in rules:
            meaning, fix, effort = GUIDE.get(rule, ("See the finding detail.", "Review the listed locations.", "varies"))
            lines.append(f"- **`{rule}`** — {meaning} **Fix:** {fix} **Effort:** {effort}")
        lines.append("")
    for area in ("secrets", "safety", "hygiene", "supply", "workflows"):
        items = [f for f in result["findings"] if f["area"] == area]
        if not items:
            continue
        lines += [f"## {area.capitalize()} ({len(items)})", ""]
        for f in sorted(items, key=lambda f: ("high", "medium", "low").index(f["severity"]))[:40]:
            lines.append(f"- **{f['severity']}** `{f['rule']}` — {f['where']}: {f['detail']}")
        if len(items) > 40:
            lines.append(f"- … {len(items) - 40} more in report.json")
        lines.append("")
    lines += ["## What this check did NOT cover", ""] + [f"- {item}" for item in NOT_CHECKED] + [""]
    return "\n".join(lines)


def to_html(result):
    """Self-contained printable page (browser: Print -> Save as PDF). Everything is escaped."""
    body, in_list = [], False
    for line in to_markdown(result).splitlines():
        if line.startswith("- "):
            if not in_list:
                body.append("<ul>")
                in_list = True
            item = html.escape(line[2:])
            item = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", item)
            body.append("<li>" + re.sub(r"`(.+?)`", r"<code>\1</code>", item) + "</li>")
            continue
        if in_list:
            body.append("</ul>")
            in_list = False
        if line.startswith("## "):
            body.append(f"<h2>{html.escape(line[3:])}</h2>")
        elif line.startswith("# "):
            body.append(f"<h1>{html.escape(line[2:])}</h1>")
        elif line.strip():
            body.append("<p>" + re.sub(r"`(.+?)`", r"<code>\1</code>", html.escape(line)) + "</p>")
    if in_list:
        body.append("</ul>")
    style = ("body{font:15px/1.5 system-ui,sans-serif;max-width:860px;margin:32px auto;padding:0 16px;color:#111}"
             "code{background:#f2f2f2;padding:1px 4px;border-radius:3px;word-break:break-all}"
             "h2{border-bottom:1px solid #ddd;padding-bottom:4px;margin-top:28px}"
             "@media print{body{margin:0}}")
    return (f"<!doctype html><html lang=en><head><meta charset=utf-8><title>Repo Reality Check - "
            f"{html.escape(result['repository'])}</title><style>{style}</style></head><body>"
            + "\n".join(body) + "</body></html>")



def to_pdf(html_str, out_path):
    try:
        from weasyprint import HTML
        HTML(string=html_str).write_pdf(out_path)
        return True
    except Exception:
        return False


def main(argv=None):
    argv = argv or sys.argv[1:]
    run_ci = "--ci-truth" in argv
    argv = [a for a in argv if a != "--ci-truth"]
    if len(argv) == 3 and argv[0] == "--verify":
        ok = verify(argv[1], argv[2])
        print("VERIFIED: report matches this checkout" if ok else "MISMATCH: report does not match this checkout")
        return 0 if ok else 1
    if len(argv) != 2:
        print("\n".join(__doc__.strip().splitlines()[-2:]), file=sys.stderr)
        return 2
    result = check(argv[0], run_ci=run_ci)
    report_json, report_md, report_html = json.dumps(result, indent=1), to_markdown(result), to_html(result)
    leaks = leak_check(report_json + report_md + report_html)
    if leaks:
        print(f"refusing to write report: second pass found {', '.join(leaks)}", file=sys.stderr)
        return 3
    out = Path(argv[1])
    out.mkdir(parents=True, exist_ok=True)
    (out / "report.json").write_text(report_json, encoding="utf-8")
    (out / "report.md").write_text(report_md, encoding="utf-8")
    (out / "report.html").write_text(report_html, encoding="utf-8")
    if not to_pdf(report_html, out / "report.pdf"):
        print("Note: PDF generation skipped. Install 'weasyprint' to enable PDF output.", file=sys.stderr)
    print(json.dumps(result["summary"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
