import json
import subprocess
import sys
from pathlib import Path
import tempfile
import textwrap

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from courier_core.test_report import classify_log, runner_fields

def generate_dockerfile(repo_path: Path):
    if (repo_path / "requirements.txt").exists():
        install_cmd = "pip install -r requirements.txt"
    elif (repo_path / "pyproject.toml").exists():
        install_cmd = "pip install ."
    else:
        install_cmd = "echo 'No requirements found'"
        
    return textwrap.dedent(f"""\
        FROM python:3.11-slim
        WORKDIR /app
        COPY . /app
        RUN {install_cmd}
        RUN pip install pytest
        CMD ["pytest", "--tb=short"]
    """)

def run_ci_truth(repo_path_str: str, sha: str = "HEAD") -> dict:
    repo = Path(repo_path_str).resolve()
    
    # We create a temporary directory to copy the codebase at the given SHA
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        # Archive the specific SHA and extract to tmp_path
        subprocess.run(["git", "archive", "--format=tar", sha], cwd=repo, stdout=subprocess.PIPE, check=True)
        # Wait, git archive writes to stdout. We can extract it in tmpdir.
        archive_proc = subprocess.Popen(["git", "archive", "--format=tar", sha], cwd=repo, stdout=subprocess.PIPE)
        subprocess.run(["tar", "-xf", "-"], cwd=tmp_path, stdin=archive_proc.stdout, check=True)
        archive_proc.wait()
        
        dockerfile_content = generate_dockerfile(tmp_path)
        (tmp_path / "Dockerfile.citruth").write_text(dockerfile_content)
        
        # Build image
        image_tag = f"citruth-{sha[:8]}"
        build_res = subprocess.run(["docker", "build", "-t", image_tag, "-f", "Dockerfile.citruth", "."], 
                                   cwd=tmp_path, capture_output=True, text=True)
        if build_res.returncode != 0:
            return {"status": "error", "classification": "env", "stage": "build", "log": build_res.stderr}
            
        # Run tests
        run_res = subprocess.run(["docker", "run", "--rm", image_tag], capture_output=True, text=True)
        
        # Cleanup image
        subprocess.run(["docker", "rmi", image_tag], capture_output=True)
        
        output = (run_res.stdout or "") + "\n" + (run_res.stderr or "")
        verdict = classify_log(output, run_res.returncode)
        fields = runner_fields(verdict)
        return {
            "status": fields["status"],
            "classification": fields["classification"],
            "stage": "test",
            "log": output,
            "verdict": verdict.to_record(),
        }

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python ci_truth.py <repo_path> [sha]")
        sys.exit(1)
    res = run_ci_truth(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "HEAD")
    print(json.dumps(res, indent=2))
