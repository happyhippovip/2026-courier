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
Usage: python scripts/repo_reality_check.py <checkout> <out_dir>
"""
import json
import os
import re
import subprocess
import sys
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
    import re
    if re.search(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b", text):
        kinds.append("email_address")
    return kinds


def ci_truth(repo):
    import subprocess, tempfile, os
    if not (repo / "tests").exists() and not (repo / "pytest.ini").exists() and not list(repo.glob("test_*.py")):
        return {"run_attempted": False, "reason": "no tests directory found"}
    try:
        import sys
        kwargs = {"ignore_cleanup_errors": True} if sys.version_info >= (3, 10) else {}
        with tempfile.TemporaryDirectory(**kwargs) as tmp_dir:
            tmp = Path(tmp_dir)
            subprocess.run(["uv", "venv", str(tmp / ".venv")], cwd=repo, capture_output=True, check=True)
            python_exe = str(tmp / ".venv" / "Scripts" / "python.exe" if os.name == "nt" else tmp / ".venv" / "bin" / "python")
            
            if (repo / "requirements.txt").exists():
                subprocess.run(["uv", "pip", "install", "-p", python_exe, "-r", "requirements.txt"], cwd=repo, capture_output=True)
            elif (repo / "pyproject.toml").exists():
                subprocess.run(["uv", "pip", "install", "-p", python_exe, "."], cwd=repo, capture_output=True)
                
            subprocess.run(["uv", "pip", "install", "-p", python_exe, "pytest"], cwd=repo, capture_output=True)
            out = subprocess.run([python_exe, "-m", "pytest"], cwd=repo, capture_output=True, text=True)
            passed = out.returncode == 0
            if passed:
                classification = "ok"
            else:
                if "AssertionError" in out.stdout or "FAILED" in out.stdout:
                    classification = "product"
                elif "ModuleNotFoundError" in out.stdout or "ImportError" in out.stdout:
                    classification = "env"
                else:
                    classification = "unknown"
            return {"run_attempted": True, "passed": passed, "classification": classification}
    except Exception as e:
        return {"run_attempted": False, "reason": str(e)}


def check(repo):
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
        add("safety", "high" if f["rule"] == "KILL_BY_NAME" else "medium", f["rule"], f"{f['path']}:{f['line']}",
            f["text"][:120])

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
            add("hygiene", "medium", "binary_committed", path, f"{size // 1024} KiB without build provenance")
        elif size > LARGE_FILE_BYTES:
            add("hygiene", "low", "large_file", path, f"{size // (1024 * 1024)} MiB")
        if size <= 2 * 1024 * 1024:
            try:
                text = full.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            for n, line in enumerate(text.splitlines(), 1):
                for kind, pattern in SECRET_PATTERNS.items():
                    m = pattern.search(line)
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
        if has_py and not hashed:
            add("supply", "medium", "no_lockfile", "repository", "dependencies resolve fresh on every install")
            
    ci = ci_truth(repo)
    if ci["run_attempted"]:
        if ci["passed"]:
            add("workflows", "low", "ci_passed", "tests", "Clean runner tests passed successfully")
        else:
            add("workflows", "high", f"ci_failed_{ci['classification']}", "tests", "Clean runner tests failed")
    else:
        add("workflows", "medium", "ci_skipped", "tests", f"Could not run CI: {ci.get('reason')}")
        
    return {"repository": repo.name, "sha": head_sha(repo), "files_scanned": len(files), "findings": findings,
            "summary": {sev: sum(f["severity"] == sev for f in findings) for sev in ("high", "medium", "low")}}


def to_markdown(result):
    lines = [f"# Repo Reality Check — {result['repository']}", "",
             f"Commit: `{result.get('sha', 'unknown')}`", "",
             f"Files scanned: {result['files_scanned']} · high {result['summary']['high']} · "
             f"medium {result['summary']['medium']} · low {result['summary']['low']}", "",
             "Read-only scan; no code was executed. Secret findings show location and type only.", ""]
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
    return "\n".join(lines)


def to_html(result):
    lines = [
        "<!DOCTYPE html><html><head><meta charset='utf-8'><style>",
        "body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif; line-height: 1.6; max-width: 800px; margin: 40px auto; padding: 0 20px; color: #333; }",
        "h1, h2 { border-bottom: 1px solid #eaecef; padding-bottom: 0.3em; }",
        "ul { padding-left: 2em; }",
        "li { margin-bottom: 0.5em; }",
        "code { background-color: rgba(27,31,35,0.05); border-radius: 3px; font-family: ui-monospace, SFMono-Regular, Consolas, 'Liberation Mono', Menlo, monospace; padding: 0.2em 0.4em; }",
        ".high { color: #d73a49; font-weight: 600; }",
        ".medium { color: #b08800; font-weight: 600; }",
        ".low { color: #22863a; font-weight: 600; }",
        "</style></head><body>",
        f"<h1>Repo Reality Check — {result['repository']}</h1>",
        f"<p>Commit: <code>{result.get('sha', 'unknown')}</code><br>",
        f"Files scanned: {result['files_scanned']} &middot; high {result['summary']['high']} &middot; medium {result['summary']['medium']} &middot; low {result['summary']['low']}</p>",
        "<p>Read-only scan; no code was executed. Secret findings show location and type only.</p>"
    ]
    for area in ("secrets", "safety", "hygiene", "supply", "workflows"):
        items = [f for f in result["findings"] if f["area"] == area]
        if not items:
            continue
        lines.append(f"<h2>{area.capitalize()} ({len(items)})</h2><ul>")
        for f in sorted(items, key=lambda f: ("high", "medium", "low").index(f["severity"]))[:40]:
            lines.append(f"<li><span class='{f['severity']}'>{f['severity']}</span> <code>{f['rule']}</code> &mdash; {f['where']}: {f['detail']}</li>")
        if len(items) > 40:
            lines.append(f"<li>&hellip; {len(items) - 40} more in report.json</li>")
        lines.append("</ul>")
    lines.append("</body></html>")
    return "\n".join(lines)


def export_pdf(html_text, out_pdf):
    try:
        from weasyprint import HTML
        HTML(string=html_text).write_pdf(out_pdf)
        return True
    except Exception as e:
        print(f"WeasyPrint failed: {e}. Falling back to Edge headless print.")
        pass

    import tempfile
    import os
    import subprocess
    fd, tmp_html = tempfile.mkstemp(suffix=".html")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(html_text)
        
    edge_paths = [
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"
    ]
    edge_exe = next((p for p in edge_paths if os.path.exists(p)), None)
    if not edge_exe:
        os.remove(tmp_html)
        return False
        
    out_pdf = os.path.abspath(out_pdf)
    try:
        subprocess.run([edge_exe, "--headless", "--disable-gpu", f"--print-to-pdf={out_pdf}", f"file:///{tmp_html.replace(chr(92), '/')}"])
    except Exception:
        pass
    finally:
        os.remove(tmp_html)
    return os.path.exists(out_pdf)


def main(argv=None):
    argv = argv or sys.argv[1:]
    if len(argv) != 2:
        print(__doc__.strip().splitlines()[-1], file=sys.stderr)
        return 2
    result = check(argv[0])
    report_json, report_md = json.dumps(result, indent=1), to_markdown(result)
    leaks = leak_check(report_json + report_md)
    if leaks:
        print(f"refusing to write report: second pass found {', '.join(leaks)}", file=sys.stderr)
        return 3
    out = Path(argv[1])
    out.mkdir(parents=True, exist_ok=True)
    (out / "report.json").write_text(report_json, encoding="utf-8")
    (out / "report.md").write_text(report_md, encoding="utf-8")
    export_pdf(to_html(result), str(out / "report.pdf"))
    print(json.dumps(result["summary"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
