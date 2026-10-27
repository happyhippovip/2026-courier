"""[DRUIDE | ACCOUNT 2] Run-time rule for tests/automation: a skip (or xfail) is only allowed with the visible reason prefix.

`SKIPPED, NOT PASSED: <why>` makes a skip impossible to mistake for a pass in the -rs listing. The AST scan in
test_round5_k0.py is only a lint (it sees the spelling `pytest.skip(...)` / `pytest.mark.skip[if](...)` in this folder);
this hook looks at what actually happens at run time, so `from pytest import skip`, `importorskip`, `unittest.skip`,
`pytest.skip.Exception`, `xfail(...)`, a skip without a reason and module-level skips are all caught. A skip without the prefix
turns into a FAILED test (or a collection error) that names the rule.
"""

import pytest

PREFIX = "SKIPPED, NOT PASSED: "


def _reason(report):
    if not getattr(report, "skipped", False):
        return None
    if hasattr(report, "wasxfail"):  # xfail(...) is a skip in disguise: it also needs the prefix
        return str(report.wasxfail)
    longrepr = report.longrepr
    text = longrepr[2] if isinstance(longrepr, tuple) and len(longrepr) == 3 else str(longrepr)
    return text[len("Skipped: "):] if text.startswith("Skipped: ") else text


def _enforce(report):
    reason = _reason(report)
    if reason is not None and not reason.startswith(PREFIX):
        report.outcome = "failed"
        if hasattr(report, "wasxfail"):
            del report.wasxfail  # else the terminal reporter still files it under "xfailed" and the exit code stays 0
        report.longrepr = (f"skip without the prefix {PREFIX!r}: got reason {reason!r}. "
                           "Every skip/xfail in tests/automation must say why in the form 'SKIPPED, NOT PASSED: <why>'.")


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    _enforce(outcome.get_result())


@pytest.hookimpl(hookwrapper=True)
def pytest_make_collect_report(collector):
    outcome = yield
    _enforce(outcome.get_result())
