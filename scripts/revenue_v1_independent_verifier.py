"""Independent verifier for Revenue V1 (GitHub Actions Safety Baseline).

Deliberately self-contained: it imports nothing from revenue_v1_safety_baseline or the worker.
It fetches the target commit itself, reads the raw workflow blobs with `git show SHA:path`
(never a working tree), re-derives the expected findings with its own rule implementation,
checks the per-file sha256 in report.json against git at the SHA and checks the report hashes
claimed by the worker result. Fail-closed: any deviation -> MISMATCH, any missing input or
exception -> FAIL. Only an exact match -> PASS.
"""
import hashlib
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

try:
    import yaml
except ImportError:  # without PyYAML every file is expected in text mode
    yaml = None

VERIFIER_NAME = "revenue_v1_independent_verifier.verify"
VERIFIER_VERSION = "1.0.0"
WORKFLOW_PREFIX = ".github/workflows/"
_SHA40 = re.compile(r"^[0-9a-f]{40}$")


def verifier_identity() -> dict:
    """Name, version and sha256 of this module's source (analogous to courier_core.verification.verifier_identity)."""
    try:
        digest = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    except OSError:
        digest = None
    return {"kind": "independent_verifier", "name": VERIFIER_NAME, "version": VERIFIER_VERSION,
            "source_sha256": digest}


# ---------------------------------------------------------------- git source (raw blobs at SHA)

def _git(repo: Path, *args: str) -> bytes:
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True).stdout


def fetch_commit(remote_url: str, sha: str, dest: Path) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    _git(dest, "init", "-q")
    _git(dest, "remote", "add", "origin", remote_url)
    _git(dest, "fetch", "-q", "--depth=1", "--filter=blob:none", "origin", sha)


def workflow_blobs(git_dir: Path, sha: str) -> dict:
    """{path relative to .github/workflows: raw bytes} read via git show SHA:path."""
    names = _git(git_dir, "ls-tree", "-r", "--name-only", sha, "--", WORKFLOW_PREFIX).decode("utf-8").splitlines()
    blobs = {}
    for full in sorted(names):
        if full.endswith(".yml") or full.endswith(".yaml"):
            blobs[full[len(WORKFLOW_PREFIX):]] = _git(git_dir, "show", f"{sha}:{full}")
    return blobs


# ---------------------------------------------------------------- own rule implementation

def _f(rule, name, issue):
    return {"rule": rule, "file": name, "issue": issue}


def _pinned(ref: str) -> bool:
    if ref.startswith("./") or ref.startswith("docker://"):
        return True
    return "@" in ref and bool(_SHA40.match(ref.rsplit("@", 1)[1]))


def _text_rules(name: str, text: str) -> list:
    out = []
    if "runs-on: self-hosted" in text:
        out.append(_f("runner_type", name, "Self-hosted runner detected."))
    if "timeout-minutes:" not in text:
        out.append(_f("timeout", name, "Missing timeout-minutes configuration."))
    if "permissions:" not in text:
        out.append(_f("permissions", name, "Missing explicit permissions block."))
    elif "write-all" in text:
        out.append(_f("permissions", name, "Permissive write-all detected."))
    if "concurrency:" not in text:
        out.append(_f("concurrency", name, "Missing concurrency block."))
    if "git push" in text:
        out.append(_f("mutation_risk", name, "git push detected in workflow."))
    code = [l for l in text.splitlines() if not l.lstrip().startswith("#")]
    if any(re.search(r"\bpull_request_target\b", l.split("#")[0]) for l in code):
        out.append(_f("pull_request_target", name, "pull_request_target trigger detected."))
    for l in code:
        m = re.match(r"^\s*-?\s*uses:\s*['\"]?([^'\"\s#]+)", l)
        if m and not _pinned(m.group(1)):
            out.append(_f("unpinned_action", name, f"Action not pinned to a full 40-char commit SHA: {m.group(1)}"))
    block = None
    for l in code:
        m = re.match(r"^(\s*)-?\s*run:\s*(.*)$", l)
        norm = l.replace("${{github.event.", "${{ github.event.")
        if m:
            block = len(m.group(1))
            if "${{ github.event." in m.group(2).replace("${{github.event.", "${{ github.event."):
                out.append(_f("script_injection", name, "github.event expression used directly in run: script."))
        elif block is not None:
            if l.strip() and len(l) - len(l.lstrip()) <= block:
                block = None
            elif "${{ github.event." in norm:
                out.append(_f("script_injection", name, "github.event expression used directly in run: script."))
    return out


def _load(text: str):
    if yaml is None:
        return None
    try:
        doc = yaml.safe_load(text)
    except yaml.YAMLError:
        return None
    return doc if isinstance(doc, dict) and isinstance(doc.get("jobs"), dict) else None


def _as_list(v) -> list:
    if isinstance(v, str):
        return [v]
    if isinstance(v, (list, dict)):
        return [str(x) for x in v]
    return []


def _yaml_rules(name: str, doc: dict) -> list:
    out = []
    jobs = {k: v for k, v in doc["jobs"].items() if isinstance(v, dict)}

    def labels(job):
        ro = job.get("runs-on")
        return _as_list(ro.get("labels", [])) if isinstance(ro, dict) else _as_list(ro)

    if any("self-hosted" in labels(j) for j in jobs.values()):
        out.append(_f("runner_type", name, "Self-hosted runner detected."))
    no_timeout = sorted(k for k, j in jobs.items() if "uses" not in j and "timeout-minutes" not in j)
    if no_timeout:
        out.append(_f("timeout", name, f"Missing timeout-minutes configuration (jobs: {', '.join(no_timeout)})."))
    if "permissions" not in doc and not all("permissions" in j for j in jobs.values()):
        out.append(_f("permissions", name, "Missing explicit permissions block."))
    elif doc.get("permissions") == "write-all" or any(j.get("permissions") == "write-all" for j in jobs.values()):
        out.append(_f("permissions", name, "Permissive write-all detected."))
    if "concurrency" not in doc and not all("concurrency" in j for j in jobs.values()):
        out.append(_f("concurrency", name, "Missing concurrency block."))
    steps = [s for j in jobs.values() for s in (j.get("steps") or []) if isinstance(s, dict)]
    scripts = [str(s["run"]) for s in steps if "run" in s]
    if any("git push" in r for r in scripts):
        out.append(_f("mutation_risk", name, "git push detected in workflow."))
    trig = doc["on"] if "on" in doc else doc.get(True)  # YAML 1.1: bare `on` -> True
    if "pull_request_target" in _as_list(trig):
        out.append(_f("pull_request_target", name, "pull_request_target trigger detected."))
    for ref in [str(s["uses"]) for s in steps if "uses" in s] + [str(j["uses"]) for j in jobs.values() if "uses" in j]:
        if not _pinned(ref):
            out.append(_f("unpinned_action", name, f"Action not pinned to a full 40-char commit SHA: {ref}"))
    for r in scripts:
        if re.search(r"\$\{\{\s*github\.event\.", r):
            out.append(_f("script_injection", name, "github.event expression used directly in run: script."))
    return out


def expected_analysis(blobs: dict) -> dict:
    files, modes, findings = {}, {}, []
    for name, raw in blobs.items():
        files[name] = hashlib.sha256(raw).hexdigest()
        text = raw.decode("utf-8")
        doc = _load(text)
        modes[name] = "yaml" if doc is not None else "text"
        findings.extend(_yaml_rules(name, doc) if doc is not None else _text_rules(name, text))
    return {"inspected_files": files, "parse_modes": modes, "findings": findings}


# ---------------------------------------------------------------- verdict

def _sha_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _key(f: dict):
    return (f.get("rule"), f.get("file"), f.get("issue"))


def compare(task: dict, work_dir: Path, candidate: dict, blobs: dict) -> tuple:
    """Return (status, reasons). status is PASS only if every check matches."""
    reasons = []
    report_path = work_dir / "report.json"
    for fname, field in (("report.json", "report_json_sha256"), ("report.md", "report_md_sha256"),
                         ("report_de.md", "report_de_md_sha256")):
        p = work_dir / fname
        if not p.exists():
            return "FAIL", [f"missing {fname}"]
        if candidate.get(field) != _sha_file(p):
            reasons.append(f"{field} in result does not match {fname}")
    report = json.loads(report_path.read_text(encoding="utf-8"))
    exp = expected_analysis(blobs)
    if report.get("inspected_files") != exp["inspected_files"]:
        reasons.append("inspected_files hashes differ from git blobs at SHA")
    if report.get("parse_modes") != exp["parse_modes"]:
        reasons.append("parse_modes differ")
    got, want = sorted(map(_key, report.get("findings", []))), sorted(map(_key, exp["findings"]))
    if got != want:
        reasons.append(f"findings differ (report {len(got)}, expected {len(want)})")
    expected_status = "PASS" if exp["inspected_files"] else "WARN"
    if candidate.get("worker_status") != expected_status:
        reasons.append(f"worker_status {candidate.get('worker_status')!r} != expected {expected_status!r}")
    if candidate.get("task_id") != task.get("task_id"):
        reasons.append("task_id differs from task")
    return ("MISMATCH", reasons) if reasons else ("PASS", [])


def verify(task: dict, work_dir: Path, candidate: dict, remote_url: str = None) -> dict:
    identity = verifier_identity()
    try:
        sha = task["target_sha"]
        if not isinstance(sha, str) or not _SHA40.match(sha.lower()):
            raise ValueError("target_sha is not a 40-char hex SHA")
        url = remote_url or f"https://github.com/{task['target_owner']}/{task['target_repo']}.git"
        with tempfile.TemporaryDirectory(prefix="rv1-indep-") as tmp:
            git_dir = Path(tmp) / "git"
            fetch_commit(url, sha, git_dir)
            blobs = workflow_blobs(git_dir, sha)
        status, reasons = compare(task, work_dir, candidate, blobs)
        expected_files = len(blobs)
    except Exception as exc:  # noqa: BLE001 - fail closed, never PASS
        status, reasons, expected_files = "FAIL", [f"verifier raised {type(exc).__name__}: {str(exc)[:200]}"], None
    return {"verdict": status, "accepted": status == "PASS", "reasons": reasons,
            "expected_file_count": expected_files, "verifier": identity}


if __name__ == "__main__":
    # usage: revenue_v1_independent_verifier.py task.json work_dir result.json [remote_url]
    _task = json.loads(Path(sys.argv[1]).read_text())
    _cand = json.loads(Path(sys.argv[3]).read_text())
    _v = verify(_task, Path(sys.argv[2]), _cand, sys.argv[4] if len(sys.argv) > 4 else None)
    print(json.dumps(_v, indent=2, sort_keys=True))
    sys.exit(0 if _v["accepted"] else 1)
