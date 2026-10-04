"""Golden skip ratchet for the Courier v1 integration trunk.

The Golden acceptance suite is pinned in two dimensions:

  * exactly EXPECTED_TOTAL golden tests are represented in the pytest summary,
  * exactly EXPECTED_SKIPPED of them are skipped,
  * zero failed / errored / xfailed / xpassed / deselected,
  * every skip reason carries EXPECTED_REASON_PREFIX.

Any deviation fails, in either direction. When v1 modules land and deliberately
un-skip golden tests, the same merge must lower EXPECTED_SKIPPED. Reaching
EXPECTED_SKIPPED = 0 is the Golden-live milestone and remains pinned so a later
regression cannot silently reintroduce skips.

Exit status: 0 pinned shape holds; 1 anything else.
"""

import os
import re
import subprocess
import sys

EXPECTED_TOTAL = 11
EXPECTED_SKIPPED = 0
EXPECTED_REASON_PREFIX = "golden harness waiting for v1 components"

SUMMARY_COUNT_RE = re.compile(
    r"(\d+)\s+(passed|failed|skipped|errors?|xfailed|xpassed|deselected)\b"
)


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


def parse_summary_counts(output):
    """Return (summary_line, counts) from pytest's final non-empty line."""
    lines = [line.strip() for line in output.splitlines() if line.strip()]
    summary = lines[-1] if lines else ""
    counts = {}
    for count, kind in SUMMARY_COUNT_RE.findall(summary):
        key = "error" if kind in ("error", "errors") else kind
        counts[key] = counts.get(key, 0) + int(count)
    return summary, counts


def main(argv=None):
    here = os.path.abspath(__file__)  # <root>/.github/ci/check_golden_skips.py
    repo_root = os.path.dirname(os.path.dirname(os.path.dirname(here)))
    expected_skipped = int(os.environ.get(
        "COURIER_EXPECTED_GOLDEN_SKIPS", str(EXPECTED_SKIPPED)
    ))
    expected_total = int(os.environ.get(
        "COURIER_EXPECTED_GOLDEN_TOTAL", str(EXPECTED_TOTAL)
    ))
    returncode, output = run_golden(repo_root)

    # pytest lists one SKIPPED line per test on older versions and one
    # grouped "SKIPPED [N] file: reason" line per file on newer ones.
    grouped_re = re.compile(r"^SKIPPED \[(\d+)\]")
    skipped_lines = [line for line in output.splitlines()
                     if line.startswith("SKIPPED")]
    collected_skips = 0
    for line in skipped_lines:
        grouped = grouped_re.match(line)
        collected_skips += int(grouped.group(1)) if grouped else 1

    summary_line, counts = parse_summary_counts(output)
    summary_skipped = counts.get("skipped", 0)
    observed_total = sum(
        counts.get(kind, 0)
        for kind in ("passed", "failed", "skipped", "xfailed", "xpassed")
    )
    unexpected = {
        kind: counts.get(kind, 0)
        for kind in ("failed", "error", "xfailed", "xpassed", "deselected")
        if counts.get(kind, 0)
    }
    bad_reasons = [line for line in skipped_lines
                   if EXPECTED_REASON_PREFIX not in line]

    lines = ["## Courier v1 golden skip ratchet", ""]
    lines.append(
        "observed-total=%d collected-skips=%d summary-skips=%d "
        "expected-skipped=%d expected-total=%d pytest_exit=%d"
        % (
            observed_total,
            collected_skips,
            summary_skipped,
            expected_skipped,
            expected_total,
            returncode,
        )
    )

    problems = []
    if returncode != 0:
        problems.append(
            "pytest exit %d: golden session broken "
            "(collection error, crash, failing test, or no tests collected); "
            "a broken harness must never look healthy" % returncode
        )
    if observed_total != expected_total:
        problems.append(
            "golden test count changed: observed %d, pinned %d; "
            "update EXPECTED_TOTAL only with an intentional suite-shape change"
            % (observed_total, expected_total)
        )
    if unexpected:
        problems.append(
            "unexpected golden outcomes: %s"
            % ", ".join("%s=%d" % item for item in sorted(unexpected.items()))
        )
    if (
        collected_skips != expected_skipped
        or summary_skipped != expected_skipped
        or collected_skips != summary_skipped
    ):
        problems.append(
            "skip count changed: observed %d summary / %d counted SKIPPED, "
            "pinned %d. If modules intentionally changed Golden readiness, "
            "update EXPECTED_SKIPPED in the same merge; otherwise investigate"
            % (summary_skipped, collected_skips, expected_skipped)
        )
    if bad_reasons:
        problems.append(
            "%d skip reason(s) lack the documented prefix %r: "
            "skips for any other reason are unacknowledged drift"
            % (len(bad_reasons), EXPECTED_REASON_PREFIX)
        )
        lines.extend("  " + line for line in bad_reasons[:10])

    if problems:
        lines.append("")
        lines.append("RATCHET FAIL:")
        lines.extend("  - " + problem for problem in problems)
        lines.append("pytest-summary: " + (summary_line or "<missing>"))
        print("\n".join(lines))
        return 1

    lines.append(
        "RATCHET PASS: %d/%d golden tests skipped; suite shape pinned"
        % (expected_skipped, expected_total)
    )
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
