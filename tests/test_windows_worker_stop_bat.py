"""stop.bat must not report Stopped when taskkill exits non-zero.

This host has no taskkill and no cmd.exe. The regression executes the
batch file's own control flow with a stubbed taskkill exit code. It does
not launch Windows taskkill and it does not claim a Windows host ran.
"""

from pathlib import Path

STOP_BAT = Path(__file__).resolve().parents[1] / "scripts" / "windows_worker" / "stop.bat"


def run_stop_bat(taskkill_exit: int):
    """Execute stop.bat statements. ``taskkill`` is not invoked."""
    lines = STOP_BAT.read_text(encoding="utf-8").replace("\r\n", "\n").split("\n")
    errorlevel = 0
    output = []
    skip_stack = []
    saw_taskkill = False

    for raw in lines:
        line = raw.strip()
        if not line or line.lower().startswith("rem ") or line.startswith("::"):
            continue
        low = line.lower()
        if low == ")":
            if not skip_stack:
                raise AssertionError(f"unbalanced block closer in {STOP_BAT}")
            skip_stack.pop()
            continue
        skipping = any(skip_stack)
        if low.startswith("if ") and low.rstrip().endswith("("):
            if skipping:
                skip_stack.append(True)
                continue
            if not low.startswith("if errorlevel "):
                raise AssertionError(f"unsupported conditional: {line}")
            threshold = int(low.split()[2])
            skip_stack.append(errorlevel < threshold)
            continue
        if skipping:
            continue
        if low.startswith("@echo ") or low == "setlocal" or low.startswith("setlocal "):
            continue
        if low.startswith("echo "):
            output.append(line.split(" ", 1)[1])
            errorlevel = 0
            continue
        if low.startswith("taskkill"):
            saw_taskkill = True
            errorlevel = taskkill_exit
            continue
        if low.startswith("exit /b"):
            if not saw_taskkill:
                raise AssertionError("stop.bat exited before taskkill")
            return int(line.split()[-1]), output
        raise AssertionError(f"unsupported stop.bat statement: {line}")

    if not saw_taskkill:
        raise AssertionError("stop.bat never calls taskkill")
    return errorlevel, output


def test_nonzero_taskkill_is_not_reported_as_stopped():
    code, output = run_stop_bat(1)
    assert "Stopped." not in output
    assert code != 0
    assert any("not proven" in line.lower() for line in output)


def test_taskkill_not_found_is_not_reported_as_stopped():
    code, output = run_stop_bat(128)
    assert "Stopped." not in output
    assert code != 0


def test_zero_taskkill_reports_stopped():
    code, output = run_stop_bat(0)
    assert "Stopped." in output
    assert code == 0
