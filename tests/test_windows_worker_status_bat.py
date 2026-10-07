"""status.bat must not treat an unrelated python.exe as the Courier worker.

stop.bat addresses Courier.exe. status.bat succeeds when findstr matches
any python process, so an unrelated interpreter is reported as the worker
and a running Courier.exe with no python process is reported as absent.

This host has no tasklist. The regression executes the batch file's control
flow with stubbed tasklist rows. It does not run tasklist and it does not
claim a Windows host ran. An image name is still not process identity.
"""

from pathlib import Path

STATUS_BAT = Path(__file__).resolve().parents[1] / "scripts" / "windows_worker" / "status.bat"


def _image_name(row: str) -> str:
    return row.split()[0]


def run_status_bat(rows):
    """Execute status.bat statements. ``tasklist`` is not invoked."""
    lines = STATUS_BAT.read_text(encoding="utf-8").replace("\r\n", "\n").split("\n")
    errorlevel = 0
    output = []
    skip_stack = []

    def tasklist_rows(command: str):
        selected = list(rows)
        low = command.lower()
        marker = 'imagename eq '
        if marker in low:
            image = command[low.index(marker) + len(marker):].strip().strip('"')
            selected = [row for row in selected if _image_name(row).lower() == image.lower()]
        return selected

    def findstr_matches(command: str, selected):
        low = command.lower()
        if "/c:" in low:
            pattern = command.split("/C:", 1)[-1].split("/c:", 1)[-1]
            pattern = pattern.strip().strip('"')
        else:
            pattern = command.split()[-1].strip('"')
        ignore = "/i" in low.split()
        matched = []
        for row in selected:
            hay = row.lower() if ignore else row
            needle = pattern.lower() if ignore else pattern
            if needle in hay:
                matched.append(row)
        return matched

    for raw in lines:
        line = raw.strip()
        if not line or line.lower().startswith("rem ") or line.startswith("::"):
            continue
        low = line.lower()
        if low == ")":
            if not skip_stack:
                raise AssertionError(f"unbalanced block closer in {STATUS_BAT}")
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
        if "|" in line and low.startswith("tasklist"):
            left, right = line.split("|", 1)
            if not right.strip().lower().startswith("findstr"):
                raise AssertionError(f"unsupported pipe: {line}")
            matched = findstr_matches(right.strip(), tasklist_rows(left.strip()))
            output.extend(matched)
            errorlevel = 0 if matched else 1
            continue
        if low.startswith("exit /b"):
            return int(line.split()[-1]), output
        raise AssertionError(f"unsupported status.bat statement: {line}")
    return errorlevel, output


def test_unrelated_python_is_not_reported_as_the_worker():
    code, output = run_status_bat([
        "python.exe                    4321 Console                    1     20,000 K",
    ])
    assert code != 0
    joined = "\n".join(output).lower()
    assert "python.exe" not in joined
    assert "not proven" in joined


def test_courier_exe_without_python_is_listed():
    code, output = run_status_bat([
        "Courier.exe                   1500 Console                    1     40,000 K",
    ])
    assert code == 0
    assert any("Courier.exe" in line for line in output)


def test_no_courier_process_is_not_proven():
    code, output = run_status_bat([
        "notepad.exe                   2000 Console                    1      5,000 K",
    ])
    assert code != 0
    assert "not proven" in "\n".join(output).lower()
