"""Golden skip ratchet for the Courier v1 integration trunk.

The 15 Golden acceptance tests skip by design until the v1 modules they
drive exist (see tests/golden/conftest.py). The regression gate tolerates
skips silently, so a broken harness, a miscounted suite, or modules landing
without acknowledgment would all pass unnoticed. This ratchet pins the
expected shape instead:

  * exactly EXPECTED_TOTAL golden tests collected,
  * exactly EXPECTED_SKIPPED of them skipped,
  * zero failed / errored,
  * every skip reason carries EXPECTED_REASON_PREFIX.

Any deviation fails, in either direction: fewer skips without a deliberate
pin update is as suspicious as more. When an L2/L3/L4 merge lands modules
that un-skip golden tests, that merge PR MUST lower EXPECTED_SKIPS (and keep
EXPECTED_TOTAL in sync if tests are added/removed) with a one-line note
about which modules landed. Reaching EXPECTED_SKIPPED = 0 is the Golden-live
milestone, not a cleanup chore.

Exit status: 0 pinned shape holds; 1 anything else.
"""

import os
import re
import subprocess
import sys

EXPECTED_TOTAL = 15
EXPECTED_SKIPPED_DEFAULT = 0
EXPECTED_REASON_PREFIX = "golden harness waiting for v1 components"

SUMMARY_RE = re.compile(r"^(\d+) skipped", re.MULTILINE)
PASSED_RE = re.compile(r"(\d+) passed\b")


def run_golden(repo_root):
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/golden", "-q", "-rs",
         "-p", "no:cacheprovider"],
        cwd=repo_root,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    return proc.returncode, proc.stdout


def main(argv=None):
    here = os.path.abspath(__file__)  # <root>/.github/ci/check_golden_skips.py
    repo_root = os.path.dirname(os.path.dirname(os.path.dirname(here)))
    expected_skipped = int(os.environ.get("COURIER_EXPECTED_GOLDEN_SKIPS",
                                           str(EXPECTED_SKIPPED_DEFAULT)))
    expected_total = int(os.environ.get("COURIER_EXPECTED_GOLDEN_TOTAL",
                                        str(EXPECTED_TOTAL)))
    returncode, output = run_golden(repo_root)

    # pytest lists one SKIPPED line per test on older versions and one
    # grouped "SKIPPED [N] file: reason" line per file on newer ones;
    # count both shapes so the pin is not pytest-version-fragile.
    grouped_re = re.compile(r"^SKIPPED \[(\d+)\]")
    skipped_lines = [line for line in output.splitlines()
                     if line.startswith("SKIPPED")]
    collected = 0
    for line in skipped_lines:
        grouped = grouped_re.match(line)
        collected += int(grouped.group(1)) if grouped else 1
    summary_match = SUMMARY_RE.search(output)
    summary_skipped = int(summary_match.group(1)) if summary_match else (0 if not skipped_lines else -1)
    passed_matches = PASSED_RE.findall(output)
    passed = int(passed_matches[-1]) if passed_matches else 0
    observed_total = passed + (summary_skipped if summary_skipped > 0 else 0)
    bad_reasons = [line for line in skipped_lines
                   if EXPECTED_REASON_PREFIX not in line]
    failed = "failed" in output.splitlines()[-1] if output.strip() else True
    if "passed" in output.splitlines()[-1] and "failed" not in output.splitlines()[-1]:
        failed = False

    lines = ["## Courier v1 golden skip ratchet", ""]
    lines.append("collected-skips=%d summary-skips=%d expected-skipped=%d "
                 "observed-total=%d expected-total=%d pytest_exit=%d"
                 % (collected, summary_skipped, expected_skipped,
                    observed_total, expected_total, returncode))

    problems = []
    if returncode not in (0,):
        problems.append("pytest exit %d: golden session broken "
                        "(collection error, crash, or no tests collected); "
                        "a broken harness must never look like skips"
                        % returncode)
    if failed:
        problems.append("golden summary reports failures/errors: failing "
                        "golden tests are product verdicts, not skip drift")
    if collected != expected_skipped or \
            summary_skipped != expected_skipped or \
            collected != summary_skipped:
        problems.append("skip count changed: observed %d short-summary / %d "
                        "counted SKIPPED, pinned %d. If v1 modules landed, "
                        "update EXPECTED_TOTAL/EXPECTED_SKIPS in this file "
                        "in the same merge; otherwise investigate"
                        % (summary_skipped, collected, expected_skipped))
    if observed_total != expected_total:
        problems.append("golden test count changed: observed %d "
                        "(passed %d + skipped %d), pinned %d. Update "
                        "EXPECTED_TOTAL in this file in the same change"
                        % (observed_total, passed, summary_skipped, expected_total))
    if bad_reasons:
        problems.append("%d skip reason(s) lack the documented prefix %r: "
                        "skips for any other reason are unacknowledged drift"
                        % (len(bad_reasons), EXPECTED_REASON_PREFIX))
        lines.extend("  " + line for line in bad_reasons[:10])

    if problems:
        lines.append("")
        lines.append("RATCHET FAIL:")
        lines.extend("  - " + problem for problem in problems)
        print("\n".join(lines))
        return 1
    lines.append("RATCHET PASS: %d/%d golden tests skipped for the "
                 "documented reason; suite shape pinned"
                 % (expected_skipped, expected_total))
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
