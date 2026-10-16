"""Classify a test report without calling it verified too early.

A verified pass is a pytest count with return code 0 and no skip, failure,
error, flake, or timeout. The same node passing and failing is flaky, not a
product defect and not a pass. An import error or skip is environment.
A timeout stays a timeout even when the summary says "failed". Agent prose
is not a receipt.

Pure: no clock, no I/O, no network. Garbage returns UNKNOWN and never raises.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

VERIFIED_PASS = "VERIFIED_PASS"
PRODUCT_FAIL = "PRODUCT_FAIL"
FLAKY = "FLAKY"
ENVIRONMENT = "ENVIRONMENT"
TIMEOUT = "TIMEOUT"
UNKNOWN = "UNKNOWN"

_KNOWN = frozenset({VERIFIED_PASS, PRODUCT_FAIL, FLAKY, ENVIRONMENT, TIMEOUT, UNKNOWN})

_CASE_LINE = re.compile(
    r"^(?:(?P<lead>PASSED|FAILED|SKIPPED|ERROR|TIMEOUT)\s+(?P<lead_node>\S+)"
    r"|(?P<node>\S+::\S+)\s+(?P<trail>PASSED|FAILED|SKIPPED|ERROR|TIMEOUT))\b",
    re.MULTILINE,
)
_BANNER = re.compile(r"^=+ .* =+\s*$", re.MULTILINE)
_COUNT_LINE = re.compile(
    r"^\d+ (?:passed|failed|skipped|error|errors|warning|warnings|flaky)\b.*$",
    re.MULTILINE,
)
_TIMEOUT_MARK = re.compile(r"TimeoutExpired|pytest-timeout|Failed:\s*Timeout|Timeout\s*>", re.IGNORECASE)
_ENV_MARK = re.compile(
    r"ModuleNotFoundError|ImportError|FileNotFoundError|Missing credentials",
    re.IGNORECASE,
)
_ASSERT_MARK = re.compile(r"AssertionError")
_FLAKY_MARK = re.compile(r"\bFLAKY\b|\bRERUN\b", re.IGNORECASE)
_PASSED = re.compile(r"(\d+)\s+passed\b")
_FAILED = re.compile(r"(\d+)\s+failed\b")
_SKIPPED = re.compile(r"(\d+)\s+skipped\b")
_ERRORS = re.compile(r"(\d+)\s+errors?\b")


@dataclass(frozen=True)
class Verdict:
    classes: frozenset[str]
    verified: bool
    cases: tuple[tuple[str, str], ...]

    def to_record(self) -> dict:
        return {
            "classes": sorted(self.classes),
            "verified": self.verified is True,
            "cases": [{"nodeid": nodeid, "klass": klass} for nodeid, klass in self.cases],
        }

    def to_json(self) -> str:
        return json.dumps(self.to_record(), sort_keys=True)

    @classmethod
    def from_json(cls, text: str) -> "Verdict":
        try:
            data = json.loads(text)
            raw = data["classes"]
            if not isinstance(raw, list) or any(item not in _KNOWN for item in raw):
                return _unknown()
            cases_in = data.get("cases", [])
            if not isinstance(cases_in, list):
                return _unknown()
            cases = tuple((str(item["nodeid"]), str(item["klass"])) for item in cases_in)
            if any(klass not in _KNOWN for _, klass in cases):
                return _unknown()
            classes = frozenset(raw)
            verified = (
                data.get("verified") is True
                and classes == {VERIFIED_PASS}
                and len(cases) > 0
                and all(klass == VERIFIED_PASS for _, klass in cases)
            )
            return cls(classes, verified, cases)
        except (TypeError, ValueError, KeyError, json.JSONDecodeError):
            return _unknown()


def _unknown() -> Verdict:
    return Verdict(frozenset({UNKNOWN}), False, ())


def _summary(text: str) -> str:
    lines = _BANNER.findall(text) + _COUNT_LINE.findall(text)
    return "\n".join(lines)


def _total(pattern: re.Pattern[str], summary: str) -> int:
    return sum(int(match.group(1)) for match in pattern.finditer(summary))


def _case_lines(text: str) -> list[tuple[str, str]]:
    found = []
    for match in _CASE_LINE.finditer(text):
        if match.group("lead"):
            found.append((match.group("lead_node"), match.group("lead").lower()))
        else:
            found.append((match.group("node"), match.group("trail").lower()))
    return found


def _from_cases(pairs: list[tuple[str, str]], text: str) -> Verdict:
    grouped: dict[str, set[str]] = {}
    for nodeid, outcome in pairs:
        grouped.setdefault(nodeid, set()).add(outcome)
    cases: list[tuple[str, str]] = []
    for nodeid, outcomes in grouped.items():
        if "passed" in outcomes and len(outcomes) > 1:
            klass = FLAKY
        elif "timeout" in outcomes:
            klass = TIMEOUT
        elif "skipped" in outcomes:
            klass = ENVIRONMENT
        elif "failed" in outcomes or "error" in outcomes:
            klass = PRODUCT_FAIL
        elif outcomes == {"passed"}:
            klass = VERIFIED_PASS
        else:
            klass = UNKNOWN
        cases.append((nodeid, klass))
    classes = {klass for _, klass in cases}
    summary = _summary(text)
    if _TIMEOUT_MARK.search(text) and not _ASSERT_MARK.search(text):
        cases = [(nodeid, TIMEOUT if klass == PRODUCT_FAIL else klass) for nodeid, klass in cases]
        classes = {klass for _, klass in cases}
    elif _TIMEOUT_MARK.search(text):
        classes.add(TIMEOUT)
        cases.append(("<timeout>", TIMEOUT))
    if _FLAKY_MARK.search(text):
        classes.add(FLAKY)
        classes.discard(VERIFIED_PASS)
    if (_ENV_MARK.search(text) or _total(_SKIPPED, summary)) and classes <= {VERIFIED_PASS, ENVIRONMENT}:
        classes.add(ENVIRONMENT)
        classes.discard(VERIFIED_PASS)
    if not classes:
        return _unknown()
    verified = classes == {VERIFIED_PASS}
    return Verdict(frozenset(classes), verified, tuple(cases))


def _from_summary(text: str, returncode: int) -> Verdict:
    summary = _summary(text)
    passed = _total(_PASSED, summary)
    failed = _total(_FAILED, summary)
    skipped = _total(_SKIPPED, summary)
    errors = _total(_ERRORS, summary)
    timeout = _TIMEOUT_MARK.search(text) is not None
    env = _ENV_MARK.search(text) is not None or skipped > 0
    assertion = _ASSERT_MARK.search(text) is not None
    flaky = _FLAKY_MARK.search(text) is not None
    classes: set[str] = set()
    cases: list[tuple[str, str]] = []
    if flaky:
        classes.add(FLAKY)
        cases.append(("<flaky>", FLAKY))
    if timeout:
        classes.add(TIMEOUT)
        cases.append(("<timeout>", TIMEOUT))
    if env:
        classes.add(ENVIRONMENT)
        cases.append(("<environment>", ENVIRONMENT))
    product = assertion or (errors > 0 and not env) or (failed > 0 and not timeout)
    if product:
        classes.add(PRODUCT_FAIL)
        cases.append(("<product>", PRODUCT_FAIL))
    if returncode == 0 and passed > 0 and not classes:
        classes.add(VERIFIED_PASS)
        cases.append(("<suite>", VERIFIED_PASS))
    if not classes:
        return _unknown()
    return Verdict(frozenset(classes), classes == {VERIFIED_PASS}, tuple(cases))


def classify_log(text: object, returncode: object) -> Verdict:
    """Return the verdict for one report. Never raises."""
    try:
        if not isinstance(text, str) or isinstance(returncode, bool) or not isinstance(returncode, int):
            return _unknown()
        pairs = _case_lines(text)
        if pairs:
            return _from_cases(pairs, text)
        return _from_summary(text, returncode)
    except Exception:
        return _unknown()


def runner_fields(verdict: Verdict) -> dict[str, str]:
    """Map a verdict onto the ci_truth status/classification pair.

    A timeout is not relabeled as a product failure. Only a verified pass
    is status pass / classification clean.
    """
    if verdict.verified is True and verdict.classes == {VERIFIED_PASS}:
        return {"status": "pass", "classification": "clean"}
    classes = verdict.classes
    if TIMEOUT in classes:
        classification = "timeout"
    elif FLAKY in classes:
        classification = "flaky"
    elif ENVIRONMENT in classes and PRODUCT_FAIL not in classes:
        classification = "env"
    elif PRODUCT_FAIL in classes:
        classification = "product"
    elif ENVIRONMENT in classes:
        classification = "env"
    else:
        classification = "unknown"
    return {"status": "fail", "classification": classification}
