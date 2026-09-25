import sys

content = open("scripts/revenue_v1_safety_baseline.py").read()
new_func = """def clone_and_extract(owner: str, repo: str, sha: str, dest: Path):
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    subprocess.run(["git", "-C", str(dest), "init"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(dest), "remote", "add", "origin", f"https://github.com/{owner}/{repo}.git"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(dest), "config", "core.sparseCheckout", "true"], check=True, capture_output=True)
    (dest / ".git" / "info" / "sparse-checkout").write_text(".github/workflows/\\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(dest), "fetch", "--depth=1", "--filter=blob:none", "origin", sha], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(dest), "checkout", "FETCH_HEAD"], check=True, capture_output=True)"""

old_func = """def clone_and_extract(owner: str, repo: str, sha: str, dest: Path):
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    subprocess.run(["git", "-C", str(dest), "init"], check=True, capture_output=False)
    subprocess.run(["git", "-C", str(dest), "remote", "add", "origin", f"https://github.com/{owner}/{repo}.git"], check=True, capture_output=False)
    subprocess.run(["git", "-C", str(dest), "config", "core.sparseCheckout", "true"], check=True, capture_output=False)
    (dest / ".git" / "info" / "sparse-checkout").write_text(".github/workflows/\\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(dest), "fetch", "--depth=1", "--filter=blob:none", "origin", sha], check=True, capture_output=False)
    subprocess.run(["git", "-C", str(dest), "checkout", "FETCH_HEAD"], check=True, capture_output=False)"""

content = content.replace(old_func, new_func)
open("scripts/revenue_v1_safety_baseline.py", "w").write(content)
