# Extracted and adapted from Phase-8 workforce commit 60ebd6a4cc33558a243d083baf3f04f3a16ab4ae
import json
import hashlib
import sys
import os
import subprocess
import shutil
import re
from pathlib import Path

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

def analyze_workflows(repo_dir: Path) -> dict:
    workflows_dir = repo_dir / ".github" / "workflows"
    findings = []
    inspected_files = {}
    
    if workflows_dir.exists() and workflows_dir.is_dir():
        for wf_path in sorted([*workflows_dir.rglob("*.yml"), *workflows_dir.rglob("*.yaml")]):
            # relative path as key so same-named files in subfolders do not overwrite each other
            wf = wf_path.relative_to(workflows_dir)
            inspected_files[wf.as_posix()] = hash_file(wf_path)
            content = wf_path.read_text(encoding="utf-8")
            
            if "runs-on: self-hosted" in content:
                findings.append({"rule": "runner_type", "file": wf.as_posix(), "issue": "Self-hosted runner detected."})
            if "timeout-minutes:" not in content:
                findings.append({"rule": "timeout", "file": wf.as_posix(), "issue": "Missing timeout-minutes configuration."})
            if "permissions:" not in content:
                findings.append({"rule": "permissions", "file": wf.as_posix(), "issue": "Missing explicit permissions block."})
            elif "write-all" in content:
                findings.append({"rule": "permissions", "file": wf.as_posix(), "issue": "Permissive write-all detected."})
            if "concurrency:" not in content:
                findings.append({"rule": "concurrency", "file": wf.as_posix(), "issue": "Missing concurrency block."})
            if "git push" in content:
                findings.append({"rule": "mutation_risk", "file": wf.as_posix(), "issue": "git push detected in workflow."})
            findings.extend(extra_findings(wf.as_posix(), content))
    
    return {
        "inspected_files": inspected_files,
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
        md += f"- `{name}`: `{h}`\n"
    md += "\n## Wichtige Hinweise\n\n"
    md += "- Geprüft wurden ausschließlich diese Regeln: Self-hosted Runner, timeout-minutes, permissions/write-all, concurrency, git push, pull_request_target, Actions ohne festen Commit-SHA, github.event-Ausdrücke direkt in run:. Die Prüfung erfolgt per Text-/Zeilensuche je Datei, ohne vollständiges YAML-Parsing.\n"
    md += "- Nicht geprüft werden u. a. Anwendungscode, Abhängigkeiten, Secrets, wiederverwendbare Workflows/Composite Actions von außerhalb und weitere Injection-Quellen außer github.event.\n"
    md += "- Es wird keine Garantie für Sicherheit oder Vollständigkeit gegeben. Fehlende Befunde bedeuten nicht, dass die Workflows sicher sind. Kein Penetrationstest, keine Zertifizierung.\n"
    md += "- Dieser Bericht wurde automatisch erzeugt und erfordert vor Auslieferung eine menschliche Durchsicht.\n"
    return md

def worker(task: dict, work_dir: Path) -> dict:
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

def verify(task: dict, candidate: dict, work_dir: Path) -> dict:
    verify_dir = work_dir / "verifier_sandbox"
    verify_dir.mkdir(parents=True, exist_ok=True)
    
    expected = worker(task, verify_dir)
    if expected["report_json_sha256"] != candidate["report_json_sha256"]:
        fail("Verification failed: report hashes do not match deterministic output.")
    
    return {
        **candidate,
        "verifier_id": VERIFIER_ID,
        "verifier_status": "PASS" if candidate.get("worker_status", "PASS") == "PASS" else "WARN",
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
