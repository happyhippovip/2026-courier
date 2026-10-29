# Extracted and adapted from Phase-8 workforce commit 60ebd6a4cc33558a243d083baf3f04f3a16ab4ae
import json
import hashlib
import sys
import os
import subprocess
import shutil
import tempfile
import re
from pathlib import Path

try:  # PyYAML is optional at runtime; without it every file falls back to text mode
    import yaml
except ImportError:  # pragma: no cover - depends on environment
    yaml = None

VERIFIER_ID = "revenue-v1-independent-verifier"

def fail(message: str) -> None:
    raise SystemExit(f"revenue workforce rejected: {message}")

def hash_file(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()

def clone_and_extract(owner: str, repo: str, sha: str, dest: Path):
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    subprocess.run(["git", "-C", str(dest), "init"], check=True, capture_output=True)
    # Hash the exact committed blob bytes: no CRLF conversion on Windows checkouts.
    subprocess.run(["git", "-C", str(dest), "config", "core.autocrlf", "false"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(dest), "remote", "add", "origin", f"https://github.com/{owner}/{repo}.git"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(dest), "config", "core.sparseCheckout", "true"], check=True, capture_output=True)
    (dest / ".git" / "info" / "sparse-checkout").write_text(".github/workflows/\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(dest), "fetch", "--depth=1", "--filter=blob:none", "origin", sha], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(dest), "checkout", "FETCH_HEAD"], check=True, capture_output=True)

USES_RE = re.compile(r"^\s*-?\s*uses:\s*['\"]?([^'\"\s#]+)")
SHA_RE = re.compile(r"^[0-9a-f]{40}$")
RUN_RE = re.compile(r"^(\s*)-?\s*run:\s*(.*)$")

def _code_lines(content: str) -> list:
    return [l for l in content.splitlines() if not l.lstrip().startswith("#")]

def extra_findings(name: str, content: str) -> list:
    """Line-based checks: pull_request_target, unpinned actions, script injection in run:."""
    findings = []
    lines = _code_lines(content)
    if any(re.search(r"\bpull_request_target\b", l.split("#")[0]) for l in lines):
        findings.append({"rule": "pull_request_target", "file": name, "issue": "pull_request_target trigger detected."})
    for l in lines:
        m = USES_RE.match(l)
        if not m:
            continue
        ref = m.group(1)
        if ref.startswith("./") or ref.startswith("docker://"):
            continue
        if "@" not in ref or not SHA_RE.match(ref.rsplit("@", 1)[1]):
            findings.append({"rule": "unpinned_action", "file": name, "issue": f"Action not pinned to a full 40-char commit SHA: {ref}"})
    run_indent = None
    for l in lines:
        m = RUN_RE.match(l)
        if m:
            run_indent = len(m.group(1))
            if "${{ github.event." in m.group(2).replace("${{github.event.", "${{ github.event."):
                findings.append({"rule": "script_injection", "file": name, "issue": "github.event expression used directly in run: script."})
            continue
        if run_indent is not None:
            if l.strip() and (len(l) - len(l.lstrip())) <= run_indent:
                run_indent = None
            elif "${{ github.event." in l.replace("${{github.event.", "${{ github.event."):
                findings.append({"rule": "script_injection", "file": name, "issue": "github.event expression used directly in run: script."})
    return findings

def text_findings(name: str, content: str) -> list:
    """Fallback: plain text search (pre-YAML behaviour), used when PyYAML is missing or parsing fails."""
    findings = []
    if "runs-on: self-hosted" in content:
        findings.append({"rule": "runner_type", "file": name, "issue": "Self-hosted runner detected."})
    if "timeout-minutes:" not in content:
        findings.append({"rule": "timeout", "file": name, "issue": "Missing timeout-minutes configuration."})
    if "permissions:" not in content:
        findings.append({"rule": "permissions", "file": name, "issue": "Missing explicit permissions block."})
    elif "write-all" in content:
        findings.append({"rule": "permissions", "file": name, "issue": "Permissive write-all detected."})
    if "concurrency:" not in content:
        findings.append({"rule": "concurrency", "file": name, "issue": "Missing concurrency block."})
    if "git push" in content:
        findings.append({"rule": "mutation_risk", "file": name, "issue": "git push detected in workflow."})
    findings.extend(extra_findings(name, content))
    return findings

def parse_workflow(content: str):
    """Return the workflow mapping, or None if PyYAML is missing, parsing fails or it is not a workflow (no jobs mapping)."""
    if yaml is None:
        return None
    try:
        doc = yaml.safe_load(content)
    except yaml.YAMLError:
        return None
    if not isinstance(doc, dict) or not isinstance(doc.get("jobs"), dict):
        return None
    return doc

def _triggers(doc: dict) -> list:
    # PyYAML (YAML 1.1) reads the bare key `on` as boolean True
    on = doc.get("on", doc.get(True))
    if isinstance(on, str):
        return [on]
    if isinstance(on, list):
        return [str(t) for t in on]
    if isinstance(on, dict):
        return [str(t) for t in on]
    return []

def _labels(runs_on) -> list:
    if isinstance(runs_on, str):
        return [runs_on]
    if isinstance(runs_on, list):
        return [str(x) for x in runs_on]
    if isinstance(runs_on, dict):
        labels = runs_on.get("labels", [])
        return [labels] if isinstance(labels, str) else [str(x) for x in labels]
    return []

def _unpinned(ref: str) -> bool:
    if ref.startswith("./") or ref.startswith("docker://"):
        return False
    return "@" not in ref or not SHA_RE.match(ref.rsplit("@", 1)[1])

INJECTION_RE = re.compile(r"\$\{\{\s*github\.event\.")

def yaml_findings(name: str, doc: dict) -> list:
    """Structure-based checks on a parsed workflow."""
    findings = []
    jobs = {k: v for k, v in doc["jobs"].items() if isinstance(v, dict)}
    # reusable-workflow calls (job-level uses:) cannot set timeout-minutes/runs-on
    step_jobs = {k: v for k, v in jobs.items() if "uses" not in v}
    if any("self-hosted" in _labels(j.get("runs-on")) for j in jobs.values()):
        findings.append({"rule": "runner_type", "file": name, "issue": "Self-hosted runner detected."})
    missing = sorted(k for k, j in step_jobs.items() if "timeout-minutes" not in j)
    if missing:
        findings.append({"rule": "timeout", "file": name, "issue": f"Missing timeout-minutes configuration (jobs: {', '.join(missing)})."})
    perms = [doc.get("permissions")] + [j.get("permissions") for j in jobs.values()]
    if "permissions" not in doc and any("permissions" not in j for j in jobs.values()):
        findings.append({"rule": "permissions", "file": name, "issue": "Missing explicit permissions block."})
    elif any(p == "write-all" for p in perms):
        findings.append({"rule": "permissions", "file": name, "issue": "Permissive write-all detected."})
    if "concurrency" not in doc and any("concurrency" not in j for j in jobs.values()):
        findings.append({"rule": "concurrency", "file": name, "issue": "Missing concurrency block."})
    steps = [st for j in jobs.values() for st in (j.get("steps") or []) if isinstance(st, dict)]
    runs = [str(st["run"]) for st in steps if "run" in st]
    if any("git push" in r for r in runs):
        findings.append({"rule": "mutation_risk", "file": name, "issue": "git push detected in workflow."})
    if "pull_request_target" in _triggers(doc):
        findings.append({"rule": "pull_request_target", "file": name, "issue": "pull_request_target trigger detected."})
    refs = [str(st["uses"]) for st in steps if "uses" in st] + [str(j["uses"]) for j in jobs.values() if "uses" in j]
    for ref in refs:
        if _unpinned(ref):
            findings.append({"rule": "unpinned_action", "file": name, "issue": f"Action not pinned to a full 40-char commit SHA: {ref}"})
    for r in runs:
        if INJECTION_RE.search(r):
            findings.append({"rule": "script_injection", "file": name, "issue": "github.event expression used directly in run: script."})
    return findings

def analyze_workflows(repo_dir: Path) -> dict:
    workflows_dir = repo_dir / ".github" / "workflows"
    findings = []
    inspected_files = {}
    parse_modes = {}
    
    if workflows_dir.exists() and workflows_dir.is_dir():
        for wf_path in sorted([*workflows_dir.rglob("*.yml"), *workflows_dir.rglob("*.yaml")]):
            # relative path as key so same-named files in subfolders do not overwrite each other
            wf = wf_path.relative_to(workflows_dir)
            inspected_files[wf.as_posix()] = hash_file(wf_path)
            content = wf_path.read_text(encoding="utf-8")
            
            doc = parse_workflow(content)
            if doc is not None:
                parse_modes[wf.as_posix()] = "yaml"
                findings.extend(yaml_findings(wf.as_posix(), doc))
            else:
                parse_modes[wf.as_posix()] = "text"
                findings.extend(text_findings(wf.as_posix(), content))
    
    return {
        "inspected_files": inspected_files,
        "parse_modes": parse_modes,
        "findings": findings
    }

RULES_DE = {
    "runner_type": {
        "title": "Self-hosted Runner",
        "severity": "HOCH",
        "explain": "Der Workflow läuft auf einem selbst betriebenen Runner. Bei öffentlichen Repos kann fremder Code (z. B. aus Pull Requests) auf Ihrer eigenen Maschine ausgeführt werden.",
        "fix": "Für öffentliche Repos GitHub-gehostete Runner verwenden oder Self-hosted Runner nur für vertrauenswürdige Ereignisse freigeben.",
        "yaml": "jobs:\n  build:\n    runs-on: ubuntu-latest",
    },
    "timeout": {
        "title": "Fehlendes timeout-minutes",
        "severity": "NIEDRIG",
        "explain": "Ohne Zeitlimit kann ein hängender Job bis zum GitHub-Standardlimit (6 Stunden) laufen und Runner-Minuten verbrauchen.",
        "fix": "Pro Job ein passendes Zeitlimit setzen.",
        "yaml": "jobs:\n  test:\n    runs-on: ubuntu-latest\n    timeout-minutes: 15",
    },
    "permissions": {
        "title": "Fehlende oder zu weite Berechtigungen",
        "severity": "MITTEL",
        "explain": "Ohne expliziten permissions-Block (oder mit write-all) erhält der GITHUB_TOKEN je nach Repo-Einstellung mehr Rechte als nötig.",
        "fix": "Auf Workflow-Ebene minimale Rechte setzen und nur dort erweitern, wo ein Job sie braucht.",
        "yaml": "permissions:\n  contents: read",
    },
    "concurrency": {
        "title": "Fehlender concurrency-Block",
        "severity": "NIEDRIG",
        "explain": "Mehrere Läufe desselben Workflows können parallel laufen, sich gegenseitig stören und unnötig Minuten verbrauchen.",
        "fix": "Läufe pro Branch gruppieren und veraltete Läufe abbrechen (bei Deploy/Release ggf. cancel-in-progress: false).",
        "yaml": "concurrency:\n  group: ${{ github.workflow }}-${{ github.ref }}\n  cancel-in-progress: true",
    },
    "mutation_risk": {
        "title": "git push im Workflow",
        "severity": "MITTEL",
        "explain": "Der Workflow schreibt per git push in ein Repository. Das ist ein schreibender Effekt und braucht entsprechende Token-Rechte.",
        "fix": "Prüfen, ob der Push nötig ist; Rechte auf den betroffenen Job begrenzen und Änderungen möglichst per Pull Request statt direktem Push einbringen.",
        "yaml": "jobs:\n  update:\n    permissions:\n      contents: write",
    },
    "pull_request_target": {
        "title": "Trigger pull_request_target",
        "severity": "HOCH",
        "explain": "pull_request_target läuft im Kontext des Ziel-Repos mit Schreib-Token und Zugriff auf Secrets, auch für Pull Requests aus Forks. Wird dabei Code aus dem PR ausgecheckt oder ausgeführt, kann Fremdcode diese Rechte nutzen.",
        "fix": "Wenn möglich pull_request verwenden. Falls pull_request_target nötig ist: keinen PR-Code auschecken oder ausführen und Rechte minimal halten.",
        "yaml": "on:\n  pull_request:\n    branches: [main]\npermissions:\n  contents: read",
    },
    "unpinned_action": {
        "title": "Action nicht auf Commit-SHA festgelegt",
        "severity": "MITTEL",
        "explain": "Die Action wird über einen Tag oder Branch eingebunden. Der Inhalt hinter einem Tag kann sich ändern; eine kompromittierte Action würde dann automatisch in Ihrem Workflow laufen.",
        "fix": "Die Action auf den vollständigen 40-stelligen Commit-SHA festlegen und die Version als Kommentar notieren.",
        "yaml": "steps:\n  - uses: actions/checkout@<40-stelliger-commit-sha> # v4",
    },
    "script_injection": {
        "title": "Mögliche Script-Injection über github.event",
        "severity": "HOCH",
        "explain": "Ein Ausdruck ${{ github.event.* }} steht direkt in einem run:-Skript. Inhalte wie Issue-Titel oder Branch-Namen können von Außenstehenden gesetzt werden und werden vor der Ausführung ungefiltert in das Shell-Skript eingesetzt.",
        "fix": "Den Wert zuerst in eine Umgebungsvariable übergeben und im Skript nur die Variable in Anführungszeichen verwenden.",
        "yaml": "- name: Titel ausgeben\n  env:\n    TITLE: ${{ github.event.issue.title }}\n  run: echo \"$TITLE\"",
    },
}

def render_report_de(owner: str, repo: str, sha: str, analysis: dict) -> str:
    md = f"# GitHub Actions Safety Baseline - Bericht\n\n**Repository:** {owner}/{repo}\n**Commit:** {sha}\n"
    md += f"**Geprüfte Workflow-Dateien:** {len(analysis['inspected_files'])}\n"
    md += f"**Befunde:** {len(analysis['findings'])}\n\n"
    if not analysis["inspected_files"]:
        md += "## WARNUNG: NO_FILES_INSPECTED\n\nUnter `.github/workflows/` wurden keine Dateien (*.yml/*.yaml) gefunden. **Dies ist KEIN unbedenkliches Ergebnis**, sondern bedeutet, dass nichts geprüft wurde.\n\n"
    elif not analysis["findings"]:
        md += "## Befunde\n\nZu den geprüften Regeln wurden keine Befunde festgestellt.\n\n"
    else:
        md += "## Befunde\n\n"
        for i, f in enumerate(analysis["findings"], 1):
            r = RULES_DE.get(f["rule"], {"title": f["rule"], "severity": "UNBEKANNT", "explain": f["issue"], "fix": "-", "yaml": ""})
            md += f"### {i}. {r['title']} - `{f['file']}`\n\n"
            md += f"- **Regel:** `{f['rule']}`\n- **Schweregrad:** {r['severity']}\n"
            md += f"- **Erklärung:** {r['explain']}\n- **Fix-Hinweis:** {r['fix']}\n\n"
            if r["yaml"]:
                md += f"```yaml\n{r['yaml']}\n```\n\n"
    md += "## Geprüfte Dateien (SHA-256)\n\n"
    for name, h in analysis["inspected_files"].items():
        mode = analysis.get("parse_modes", {}).get(name, "text")
        md += f"- `{name}`: `{h}` (Prüfmodus: {mode})\n"
    md += "\n## Wichtige Hinweise\n\n"
    md += "- Geprüft wurden ausschließlich diese Regeln: Self-hosted Runner, timeout-minutes, permissions/write-all, concurrency, git push, pull_request_target, Actions ohne festen Commit-SHA, github.event-Ausdrücke direkt in run:. Die Prüfung erfolgt strukturbasiert per YAML-Parser (Prüfmodus yaml); ist eine Datei nicht parsebar oder PyYAML nicht verfügbar, wird auf eine Textsuche zurückgefallen (Prüfmodus text, ungenauer).\n"
    md += "- Nicht geprüft werden u. a. Anwendungscode, Abhängigkeiten, Secrets, wiederverwendbare Workflows/Composite Actions von außerhalb und weitere Injection-Quellen außer github.event.\n"
    md += "- Es wird keine Garantie für Sicherheit oder Vollständigkeit gegeben. Fehlende Befunde bedeuten nicht, dass die Workflows sicher sind. Kein Penetrationstest, keine Zertifizierung.\n"
    md += "- Dieser Bericht wurde automatisch erzeugt und erfordert vor Auslieferung eine menschliche Durchsicht.\n"
    return md

def worker(task: dict, work_dir: Path) -> dict:
    work_dir = Path(work_dir)
    if work_dir.is_symlink() or work_dir.parent.is_symlink():
        fail("refusing to follow a symlink")
    owner = task["target_owner"]
    repo = task["target_repo"]
    sha = task["target_sha"]
    run_id = os.environ.get("GITHUB_RUN_ID", "local-worker")
    run_attempt = os.environ.get("GITHUB_RUN_ATTEMPT", "1")
    
    repo_dir = work_dir / "target_repo"
    clone_and_extract(owner, repo, sha, repo_dir)
    
    analysis = analyze_workflows(repo_dir)
    
    worker_status = "PASS" if analysis["inspected_files"] else "WARN"
    report_md = f"# GitHub Actions Safety Baseline Report\n\n**Target:** {owner}/{repo} @ {sha}\n\n## Findings\n"
    if not analysis["inspected_files"]:
        report_md += "**WARN: NO_FILES_INSPECTED** - no workflow files (*.yml/*.yaml) found under .github/workflows/. This is not a clean result.\n"
    elif not analysis["findings"]:
        report_md += "No safety violations detected.\n"
    else:
        for f in analysis["findings"]:
            report_md += f"- **{f['file']}**: {f['issue']} ({f['rule']})\n"
            
    report_json = json.dumps(analysis, indent=2)
    
    (work_dir / "report.json").write_text(report_json, encoding="utf-8")
    (work_dir / "report.md").write_text(report_md, encoding="utf-8")
    (work_dir / "report_de.md").write_text(render_report_de(owner, repo, sha, analysis), encoding="utf-8")
    
    return {
        "schema_version": "1.0",
        "task_id": task["task_id"],
        "attempt_id": task["attempt_id"],
        "idempotency_key": task["idempotency_key"],
        "github_run_id": run_id,
        "github_run_attempt": run_attempt,
        "worker_result_id": f"worker-{task['attempt_id']}",
        "customer_reference": task["customer_reference"],
        "report_json_sha256": hash_file(work_dir / "report.json"),
        "report_md_sha256": hash_file(work_dir / "report.md"),
        "report_de_md_sha256": hash_file(work_dir / "report_de.md"),
        "effect_classification": "SAFE_READ_ONLY",
        "worker_status": worker_status,
        **({"warning": "NO_FILES_INSPECTED"} if worker_status != "PASS" else {}),
        "proposal_mode": "PR_ONLY"
    }

INDEPENDENT_VERIFIER = Path(__file__).resolve().parent / "revenue_v1_independent_verifier.py"

def independent_verifier_path() -> Path:
    """Path of the verifier to run. CI may pin it (e.g. a copy taken from integration/v1) via env var."""
    override = os.environ.get("REVENUE_V1_INDEPENDENT_VERIFIER")
    return Path(override) if override else INDEPENDENT_VERIFIER

def run_independent_verifier(task: dict, candidate: dict, work_dir: Path) -> dict:
    """Run the independent verifier as a separate process (no shared code); fail closed on any error."""
    try:
        with tempfile.TemporaryDirectory(prefix="rv1-verify-") as tmp:
            task_p, cand_p = Path(tmp) / "task.json", Path(tmp) / "candidate.json"
            task_p.write_text(json.dumps(task), encoding="utf-8")
            cand_p.write_text(json.dumps(candidate), encoding="utf-8")
            proc = subprocess.run([sys.executable, str(independent_verifier_path()), str(task_p), str(work_dir), str(cand_p)],
                                  capture_output=True, text=True)
        verdict = json.loads(proc.stdout)
        if not isinstance(verdict, dict):
            raise ValueError("verdict is not an object")
    except Exception as exc:  # noqa: BLE001 - fail closed, never PASS
        return {"verdict": "FAIL", "accepted": False, "reasons": [f"independent verifier not usable: {type(exc).__name__}"], "verifier": None}
    if proc.returncode != 0 or verdict.get("verdict") != "PASS" or verdict.get("accepted") is not True:
        verdict["accepted"] = False
    return verdict

def verify(task: dict, candidate: dict, work_dir: Path) -> dict:
    verdict = run_independent_verifier(task, candidate, work_dir)
    if not verdict.get("accepted"):
        fail(f"independent verifier {verdict.get('verdict', 'FAIL')}: {'; '.join(verdict.get('reasons', []))[:500]}")

    worker_status = candidate.get("worker_status")
    if worker_status not in ("PASS", "WARN"):
        fail(f"worker_status {worker_status!r} is not PASS or WARN")

    return {
        **candidate,
        "verifier_id": VERIFIER_ID,
        "verifier_status": "PASS" if worker_status == "PASS" else "WARN",
        "independent_verdict": verdict["verdict"],
        "independent_verifier": verdict["verifier"],
        "next_safe_state": "HUMAN_REVIEW_REQUIRED"
    }

def validate_verified_result(task: dict, result: dict, work_dir: Path) -> None:
    expected = verify(task, result, work_dir)
    if result != expected:
        fail("verifier-approved result does not satisfy the fenced contract")

# Derived directly from Phase-8 commit 60ebd6a4cc33558a243d083baf3f04f3a16ab4ae
def reconcile_handoff(
    task: dict,
    result: dict,
    handoff: dict,
    work_dir: Path,
    proposal_number: str,
    proposal_head: str,
    proposal_base: str,
) -> dict:
    run_id = result.get("github_run_id")
    run_attempt = result.get("github_run_attempt")
    if not isinstance(run_id, str) or not isinstance(run_attempt, str):
        fail("verified result has no valid GitHub run identity")
    validate_verified_result(task, result, work_dir)
    if not proposal_number.isdecimal() or proposal_base != "main" or not proposal_head.startswith("revenue/result-proposal-"):
        fail("proposal identity is not a human-reviewable PR")
    expected_handoff = {
        "task_id": result["task_id"],
        "attempt_id": result["attempt_id"],
        "result_path": f"revenue_v1/results/{result['task_id']}-{result['attempt_id']}-{result['github_run_id']}-{result['github_run_attempt']}.json",
        "verifier_id": VERIFIER_ID,
        "result_commit": handoff.get("result_commit"),
        "proposal_branch": proposal_head,
        "proposal_pr": f"https://github.com/happyhippovip/2026-courier/pull/{proposal_number}",
        "human_merge_required": True,
    }
    if not isinstance(expected_handoff["result_commit"], str) or not re.fullmatch(r"[0-9a-f]{40}", expected_handoff["result_commit"]):
        fail("handoff has no valid durable result commit")
    if handoff != expected_handoff:
        fail("handoff does not bind the verified result to the proposal")
    return {
        "status": "HANDOFF_RECONCILED",
        "task_id": result["task_id"],
        "attempt_id": result["attempt_id"],
        "idempotency_key": result["idempotency_key"],
        "github_run_id": result["github_run_id"],
        "github_run_attempt": result["github_run_attempt"],
        "worker_result_id": result["worker_result_id"],
        "verifier_id": VERIFIER_ID,
        "proposal_pr": proposal_number,
        "proposal_head": proposal_head,
        "next_safe_state": "HUMAN_REVIEW_REQUIRED",
    }

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python3 revenue_v1_safety_baseline.py <worker|verify|reconcile> <task_path> [work_dir] ...")
        sys.exit(2)
    cmd = sys.argv[1]
    task_path = Path(sys.argv[2])
    work_dir = Path(sys.argv[3]) if len(sys.argv) > 3 else Path(".")
    
    task = json.loads(task_path.read_text())
    work_dir.mkdir(parents=True, exist_ok=True)
    
    if cmd == "worker":
        res = worker(task, work_dir)
        print(json.dumps(res, indent=2))
    elif cmd == "verify":
        candidate_path = Path(sys.argv[4])
        candidate = json.loads(candidate_path.read_text())
        verified = verify(task, candidate, work_dir)
        print(json.dumps(verified, indent=2))
    elif cmd == "reconcile":
        result_path = Path(sys.argv[4])
        handoff_path = Path(sys.argv[5])
        proposal_number = sys.argv[6]
        proposal_head = sys.argv[7]
        proposal_base = sys.argv[8]
        reconciliation = reconcile_handoff(
            task, json.loads(result_path.read_text()), json.loads(handoff_path.read_text()), work_dir,
            proposal_number, proposal_head, proposal_base
        )
        print(json.dumps(reconciliation, indent=2))
