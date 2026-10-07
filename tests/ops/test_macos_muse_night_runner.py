from __future__ import annotations

import os
import pathlib
import subprocess


ROOT = pathlib.Path(__file__).resolve().parents[2]
RUNNER = ROOT / "scripts" / "macos_muse_night_once.sh"
INSTALLER = ROOT / "scripts" / "install_macos_muse_night_runner.sh"


def test_installer_hands_path_to_launchd() -> None:
    # launchd starts agents with a minimal PATH; without the installing
    # shell's PATH in the job the runner cannot find muse and only backs off.
    text = INSTALLER.read_text(encoding="utf-8")
    assert "<key>PATH</key>" in text
    assert "<string>$PATH</string>" in text
    assert "command -v muse" in text


def _fake_muse(tmp_path: pathlib.Path, body: str, exit_code: int = 0) -> pathlib.Path:
    bindir = tmp_path / "bin"
    bindir.mkdir()
    muse = bindir / "muse"
    muse.write_text(
        "#!/bin/sh\n"
        "echo \"$@\" > \"$FAKE_MUSE_ARGS\"\n"
        f"printf '%s\\n' {body!r}\n"
        f"exit {exit_code}\n",
        encoding="utf-8",
    )
    muse.chmod(0o755)
    return bindir


def _fake_git(bindir: pathlib.Path, status_output: str) -> None:
    git = bindir / "git"
    git.write_text(
        "#!/bin/sh\n"
        "echo \"$@\" >> \"$FAKE_GIT_CALLS\"\n"
        "if [ \"$1\" = status ]; then\n"
        f"  printf '%s' {status_output!r}\n"
        "fi\n"
        "exit 0\n",
        encoding="utf-8",
    )
    git.chmod(0o755)


def _run(
    tmp_path: pathlib.Path,
    body: str,
    exit_code: int = 0,
    git_status: str | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run the runner once. The self-update is off unless ``git_status`` is
    given; then a fake git records its calls and reports that status."""
    state = tmp_path / "state"
    state.mkdir(exist_ok=True)
    args_file = tmp_path / "muse-args.txt"
    bindir = _fake_muse(tmp_path, body, exit_code=exit_code)

    env = os.environ.copy()
    env.update(
        {
            "PATH": f"{bindir}:{env.get('PATH', '')}",
            "FAKE_MUSE_ARGS": str(args_file),
            "COURIER_REPO_ROOT": str(ROOT),
            "COURIER_NIGHT_STATE_DIR": str(state),
            "COURIER_NIGHT_LOCK_DIR": str(tmp_path / "runner.lock"),
            "COURIER_NIGHT_BACKOFF_SECONDS": "60",
            "COURIER_NIGHT_AUTO_UPDATE": "0",
        }
    )
    if git_status is not None:
        _fake_git(bindir, git_status)
        env["FAKE_GIT_CALLS"] = str(tmp_path / "git-calls.txt")
        env["COURIER_NIGHT_AUTO_UPDATE"] = "1"
    return subprocess.run(
        ["/bin/bash", str(RUNNER)],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def test_clean_checkout_is_fast_forwarded_before_the_batch(tmp_path: pathlib.Path) -> None:
    result = _run(tmp_path, "COURIER_NIGHT_BATCH_COMPLETE", git_status="")
    assert result.returncode == 0, result.stderr
    calls = (tmp_path / "git-calls.txt").read_text(encoding="utf-8")
    assert "status --porcelain" in calls
    assert "pull --ff-only --quiet" in calls
    assert "update=ok" in (tmp_path / "state" / "runner.log").read_text(encoding="utf-8")


def test_dirty_checkout_is_not_updated(tmp_path: pathlib.Path) -> None:
    result = _run(tmp_path, "COURIER_NIGHT_BATCH_COMPLETE", git_status=" M somefile")
    assert result.returncode == 0, result.stderr
    calls = (tmp_path / "git-calls.txt").read_text(encoding="utf-8")
    assert "status --porcelain" in calls
    assert "pull" not in calls
    assert "update=skipped (checkout not clean)" in (tmp_path / "state" / "runner.log").read_text(encoding="utf-8")


def test_runner_invokes_muse_exec_prompt_file(tmp_path: pathlib.Path) -> None:
    result = _run(tmp_path, "COURIER_NIGHT_BATCH_COMPLETE")
    assert result.returncode == 0, result.stderr
    args = (tmp_path / "muse-args.txt").read_text(encoding="utf-8")
    assert args.startswith("exec --prompt-file ")
    log = (tmp_path / "state" / "runner.log").read_text(encoding="utf-8")
    assert "COURIER_NIGHT_BATCH_COMPLETE" in log


def test_resource_error_creates_sticky_pause(tmp_path: pathlib.Path) -> None:
    result = _run(tmp_path, "Too many open files (os error 24)", exit_code=1)
    assert result.returncode == 75
    pause = tmp_path / "state" / "RESOURCE_PAUSE"
    assert pause.exists()
    assert "RESOURCE_PAUSE" in pause.read_text(encoding="utf-8")


def test_provider_failure_sets_backoff(tmp_path: pathlib.Path) -> None:
    result = _run(tmp_path, "transport error", exit_code=9)
    assert result.returncode == 9
    backoff = tmp_path / "state" / "BACKOFF_UNTIL"
    assert backoff.exists()
    assert backoff.read_text(encoding="utf-8").strip().isdigit()


def test_successful_no_emfile_text_does_not_pause(tmp_path: pathlib.Path) -> None:
    result = _run(tmp_path, "No EMFILE / os error 24 encountered; batch complete.")
    assert result.returncode == 0
    assert not (tmp_path / "state" / "RESOURCE_PAUSE").exists()
