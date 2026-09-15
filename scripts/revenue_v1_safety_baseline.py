import json
import hashlib
import sys
import os
import subprocess
import shutil
from pathlib import Path

def hash_file(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()

def clone_and_extract(owner: str, repo: str, sha: str, dest: Path):
    if dest.exists():
        shutil.rmtree(dest)
    subprocess.run(["git", "clone", "--no-checkout", f"https://github.com/{owner}/{repo}.git", str(dest)], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(dest), "checkout", sha], check=True, capture_output=True)

def analyze_workflows(repo_dir: Path) -> dict:
    workflows_dir = repo_dir / ".github" / "workflows"
    findings = []
    inspected_files = {}
    
    if workflows_dir.exists() and workflows_dir.is_dir():
        for wf in workflows_dir.rglob("*.yml"):
            inspected_files[wf.name] = hash_file(wf)
            content = wf.read_text(encoding="utf-8")
            
            if "runs-on: self-hosted" in content:
                findings.append({"rule": "runner_type", "file": wf.name, "issue": "Self-hosted runner detected."})
            if "timeout-minutes:" not in content:
                findings.append({"rule": "timeout", "file": wf.name, "issue": "Missing timeout-minutes configuration."})
            if "permissions:" not in content:
                findings.append({"rule": "permissions", "file": wf.name, "issue": "Missing explicit permissions block."})
            elif "write-all" in content:
                findings.append({"rule": "permissions", "file": wf.name, "issue": "Permissive write-all detected."})
            if "concurrency:" not in content:
                findings.append({"rule": "concurrency", "file": wf.name, "issue": "Missing concurrency block."})
            if "git push" in content:
                findings.append({"rule": "mutation_risk", "file": wf.name, "issue": "git push detected in workflow."})
    
    return {
        "inspected_files": inspected_files,
        "findings": findings
    }

def worker(task: dict, work_dir: Path) -> dict:
    owner = task["target_owner"]
    repo = task["target_repo"]
    sha = task["target_sha"]
    
    repo_dir = work_dir / "target_repo"
    clone_and_extract(owner, repo, sha, repo_dir)
    
    analysis = analyze_workflows(repo_dir)
    
    report_md = f"# GitHub Actions Safety Baseline Report\n\n**Target:** {owner}/{repo} @ {sha}\n\n## Findings\n"
    if not analysis["findings"]:
        report_md += "No safety violations detected.\n"
    else:
        for f in analysis["findings"]:
            report_md += f"- **{f['file']}**: {f['issue']} ({f['rule']})\n"
            
    report_json = json.dumps(analysis, indent=2)
    
    (work_dir / "report.json").write_text(report_json, encoding="utf-8")
    (work_dir / "report.md").write_text(report_md, encoding="utf-8")
    
    return {
        "schema_version": "1.0",
        "task_id": task["task_id"],
        "attempt_id": task["attempt_id"],
        "idempotency_key": task["idempotency_key"],
        "worker_id": os.environ.get("GITHUB_RUN_ID", "local-worker"),
        "customer_reference": task["customer_reference"],
        "report_json_sha256": hash_file(work_dir / "report.json"),
        "report_md_sha256": hash_file(work_dir / "report.md"),
        "effect_classification": "SAFE_READ_ONLY",
        "worker_status": "PASS",
        "proposal_mode": "PR_ONLY"
    }

def verify(task: dict, result: dict, work_dir: Path) -> dict:
    # Use a separate verifier directory to avoid stomping the worker's files
    verify_dir = work_dir / "verifier_sandbox"
    verify_dir.mkdir(parents=True, exist_ok=True)
    
    expected = worker(task, verify_dir)
    if expected["report_json_sha256"] != result["report_json_sha256"]:
        raise ValueError("Verification failed: report hashes do not match deterministic output.")
    
    return {
        **result,
        "verifier_id": "revenue-v1-independent-verifier",
        "verifier_status": "PASS",
        "next_safe_state": "HUMAN_REVIEW_REQUIRED"
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
        result_path = Path(sys.argv[4])
        result = json.loads(result_path.read_text())
        verified = verify(task, result, work_dir)
        print(json.dumps(verified, indent=2))
