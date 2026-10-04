"""Courier v1 golden acceptance harness (L1-owned). Contract: tests/golden/README.md.

Every test in tests/golden is skipped with an explicit reason until the v1
modules it drives exist. It is never xfailed or disabled: once the modules
land, all assertions here are the merge gate for L2-L6.
"""

from pathlib import Path

import pytest

from golden_harness import GOLDEN_DIR, Courier, missing_modules


def pytest_collection_modifyitems(config, items):
    missing = missing_modules()
    for item in items:
        if Path(str(item.path)).resolve().parent != GOLDEN_DIR:
            continue
        item.add_marker(pytest.mark.golden)
        if missing:
            item.add_marker(pytest.mark.skip(
                reason="golden harness waiting for v1 components: " + ", ".join(missing)))


@pytest.hookimpl(wrapper=True)
def pytest_runtest_makereport(item, call):
    report = yield
    setattr(item, "golden_rep_" + report.when, report)
    return report


@pytest.fixture
def courier(tmp_path, request):
    home = tmp_path / "courier_home"
    logs = tmp_path / "logs"
    home.mkdir()
    logs.mkdir()
    instance = Courier(home, logs)
    yield instance
    failed = any(getattr(getattr(request.node, "golden_rep_" + phase, None), "failed", False)
                 for phase in ("setup", "call"))
    if failed:
        for log in sorted(logs.glob("*.log")):
            print(f"\n----- {log.name} (tail) -----\n{instance.log_tail(log.name)}")
    instance.close()
