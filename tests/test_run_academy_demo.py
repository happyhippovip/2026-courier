import json
import pytest
from pathlib import Path
from scripts.run_academy_demo import run_academy_demo, main


@pytest.fixture
def academy_demo_env(tmp_path):
    repo_dir = tmp_path / "repo"
    memory_dir = tmp_path / "memory"
    repo_dir.mkdir(parents=True)
    memory_dir.mkdir(parents=True)

    (memory_dir / "PROJECT_STATE.md").write_text("# Project State\nStatus: VERIFIED_CURRENT\n", encoding="utf-8")
    return repo_dir, memory_dir


def test_run_academy_demo_pipeline(academy_demo_env):
    repo_dir, memory_dir = academy_demo_env

    result = run_academy_demo(reset=False, repo_dir=repo_dir, memory_dir=memory_dir)

    assert result["status"] == "COMPLETED"
    assert result["eval_verdict"] == "PASS"
    assert "lesson_id" in result
    assert result["context_version_after"] >= result["context_version_before"]
    assert result["measured_minutes_saved"] > 0

    # Verify that files were created under repo_dir
    academy_dir = repo_dir / "events/academy"
    assert (academy_dir / "lessons" / f"{result['lesson_id']}.json").exists()
    assert (academy_dir / "evaluations" / f"eval-{result['lesson_id']}.json").exists()
    assert (academy_dir / "adoptions" / f"adopt-{result['lesson_id']}.json").exists()


def test_run_academy_demo_cli(academy_demo_env, capsys):
    repo_dir, memory_dir = academy_demo_env

    code = main([
        "--repo-dir", str(repo_dir),
        "--memory-dir", str(memory_dir),
        "--json",
    ])
    assert code == 0
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data["status"] == "COMPLETED"
    assert data["eval_verdict"] == "PASS"
