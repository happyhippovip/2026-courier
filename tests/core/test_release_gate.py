"""Release gate: candidate fingerprint, required-test skips, PRE_CODEX_READY.

Missing on integration/v1. A shared SHA with a different content hash is not
the same candidate. An exit code of 0 does not excuse a required skip. A
hardcoded human-relay 0 is not proof the gate is ready.
"""

import json
from pathlib import Path

from courier_core.release_gate import (
    ReleaseVerdict,
    assess_required_tests,
    compare_final_candidates,
    prove_pre_codex_ready,
)

SECRET = "sk-live-SUPERSECRETVALUE"
HASH_A = "a" * 64
HASH_B = "b" * 64


def _candidate(sha="abc123", content=HASH_A, **extra):
    value = {"candidate_sha": sha, "content_hash": content}
    value.update(extra)
    return value


def _clear_tests():
    return {
        "exit_code": 0,
        "required": ["tests/core/test_release_gate.py"],
        "results": [{
            "nodeid": "tests/core/test_release_gate.py::test_equal_fingerprints_match",
            "outcome": "passed",
        }],
        "skipped": 0,
    }


def test_module_does_not_read_clock_or_network():
    import courier_core.release_gate as gate

    source = Path(gate.__file__).read_text(encoding="utf-8")
    assert "datetime.now" not in source
    assert "utcnow" not in source
    assert "urlopen" not in source
    assert "socket" not in source


def test_equal_fingerprints_match():
    verdict = compare_final_candidates(_candidate(), _candidate(note="ignored"))
    assert verdict.metric == "final_candidate"
    assert verdict.status == "matched"
    assert verdict.matched is True
    assert verdict.verified is True
    assert verdict.reason == "matched"


def test_same_sha_different_content_is_not_a_match():
    verdict = compare_final_candidates(
        _candidate(note=SECRET),
        _candidate(content=HASH_B),
    )
    assert verdict.status == "mismatched"
    assert verdict.matched is False
    assert verdict.verified is False
    assert verdict.reason == "mismatched"
    assert SECRET not in verdict.to_json()


def test_different_sha_same_content_is_not_a_match():
    verdict = compare_final_candidates(_candidate(sha="left"), _candidate(sha="right"))
    assert verdict.status == "mismatched"
    assert verdict.matched is False


def test_missing_content_hash_is_unmeasured():
    verdict = compare_final_candidates({"candidate_sha": "abc123"}, _candidate())
    assert verdict.status == "unmeasured"
    assert verdict.reason == "content_hash_missing"
    assert verdict.matched is None
    assert verdict.verified is False


def test_prose_fingerprint_is_not_a_receipt():
    verdict = compare_final_candidates("the fingerprints match", _candidate())
    assert verdict.status == "unmeasured"
    assert verdict.reason == "prose_not_receipt"
    assert verdict.matched is None
    assert "fingerprints match" not in verdict.to_json()


def test_fingerprint_reload_and_tamper():
    verdict = compare_final_candidates(_candidate(), _candidate())
    assert ReleaseVerdict.from_json(verdict.to_json()) == verdict
    raw = json.loads(verdict.to_json())
    raw["matched"] = False
    raw["verified"] = True
    again = ReleaseVerdict.from_json(json.dumps(raw))
    assert again.status == "rejected"
    assert again.verified is False
    assert again.matched is None
    assert again.reason == "tampered"


def test_required_skip_blocks_even_when_exit_code_is_zero():
    verdict = assess_required_tests({
        "exit_code": 0,
        "required": ["tests/core/test_release_gate.py"],
        "results": [
            {
                "nodeid": "tests/core/test_release_gate.py::test_equal_fingerprints_match",
                "outcome": "passed",
            },
            {
                "nodeid": "tests/core/test_release_gate.py::test_required_skip_blocks_even_when_exit_code_is_zero",
                "outcome": "skipped",
            },
        ],
        "skipped": 1,
    })
    assert verdict.metric == "required_tests"
    assert verdict.status == "blocked"
    assert verdict.reason == "required_skip"
    assert verdict.skipped == 1
    assert verdict.ready is False
    assert verdict.verified is False


def test_all_required_passed_is_clear():
    verdict = assess_required_tests(_clear_tests())
    assert verdict.status == "clear"
    assert verdict.skipped == 0
    assert verdict.ready is True
    assert verdict.verified is True


def test_missing_required_test_blocks():
    verdict = assess_required_tests({
        "required": ["tests/missing.py"],
        "results": [],
        "skipped": 0,
    })
    assert verdict.status == "blocked"
    assert verdict.reason == "required_missing"
    assert verdict.ready is False
    assert verdict.verified is False


def test_required_failure_blocks():
    verdict = assess_required_tests({
        "required": ["tests/core/test_release_gate.py"],
        "results": [{
            "nodeid": "tests/core/test_release_gate.py::test_equal_fingerprints_match",
            "outcome": "failed",
        }],
    })
    assert verdict.status == "blocked"
    assert verdict.reason == "required_failed"
    assert verdict.ready is False


def test_unknown_outcome_is_unmeasured():
    verdict = assess_required_tests({
        "required": ["tests/core/test_release_gate.py"],
        "results": [{
            "nodeid": "tests/core/test_release_gate.py::test_equal_fingerprints_match",
            "outcome": "xfailed",
        }],
    })
    assert verdict.status == "unmeasured"
    assert verdict.reason == "unknown_outcome"
    assert verdict.ready is None


def test_skip_summary_mismatch_is_unmeasured():
    report = _clear_tests()
    report["results"].append({
        "nodeid": "tests/core/test_release_gate.py::test_missing_required_test_blocks",
        "outcome": "skipped",
    })
    report["skipped"] = 0
    verdict = assess_required_tests(report)
    assert verdict.status == "unmeasured"
    assert verdict.reason == "summary_mismatch"
    assert verdict.verified is False


def test_empty_required_set_is_unmeasured():
    verdict = assess_required_tests({"required": [], "results": []})
    assert verdict.status == "unmeasured"
    assert verdict.reason == "no_required_set"
    assert verdict.ready is None


def test_prose_test_claim_is_not_clear():
    verdict = assess_required_tests("3 passed, 1 skipped")
    assert verdict.status == "unmeasured"
    assert verdict.reason == "prose_not_receipt"
    assert verdict.ready is None
    assert "skipped" not in verdict.to_json()


def test_required_reload_and_tamper():
    verdict = assess_required_tests(_clear_tests())
    assert ReleaseVerdict.from_json(verdict.to_json()) == verdict
    raw = json.loads(assess_required_tests({
        "required": ["tests/core/test_release_gate.py"],
        "results": [{
            "nodeid": "tests/core/test_release_gate.py::test_equal_fingerprints_match",
            "outcome": "skipped",
        }],
        "skipped": 1,
    }).to_json())
    raw["verified"] = True
    raw["ready"] = True
    again = ReleaseVerdict.from_json(json.dumps(raw))
    assert again.status == "rejected"
    assert again.verified is False
    assert again.ready is None


def test_pre_codex_ready_only_when_fingerprint_tests_and_relays_hold():
    verdict = prove_pre_codex_ready({
        "claimed": _candidate(),
        "observed": _candidate(),
        "tests": _clear_tests(),
        "human_relays": [{"kind": "worker"}],
    })
    assert verdict.metric == "pre_codex_ready"
    assert verdict.status == "clear"
    assert verdict.ready is True
    assert verdict.matched is True
    assert verdict.skipped == 0
    assert verdict.verified is True


def test_hardcoded_relay_zero_blocks_pre_codex():
    verdict = prove_pre_codex_ready({
        "claimed": _candidate(),
        "observed": _candidate(),
        "tests": _clear_tests(),
        "human_relays": {"execution_counters": {"human_relay_count": 0}},
    })
    assert verdict.status == "unmeasured"
    assert verdict.reason == "relay_unmeasured"
    assert verdict.ready is None
    assert verdict.verified is False


def test_relay_present_blocks_pre_codex():
    verdict = prove_pre_codex_ready({
        "claimed": _candidate(),
        "observed": _candidate(),
        "tests": _clear_tests(),
        "human_relays": [{"kind": "human_relay", "actor": "human", "text": SECRET}],
    })
    assert verdict.status == "blocked"
    assert verdict.reason == "human_relay_present"
    assert verdict.ready is False
    assert verdict.verified is False
    assert SECRET not in verdict.to_json()


def test_required_skip_blocks_pre_codex():
    tests = _clear_tests()
    tests["results"][0]["outcome"] = "skipped"
    tests["skipped"] = 1
    verdict = prove_pre_codex_ready({
        "claimed": _candidate(),
        "observed": _candidate(),
        "tests": tests,
        "human_relays": [{"kind": "system"}],
    })
    assert verdict.status == "blocked"
    assert verdict.reason == "required_skip"
    assert verdict.ready is False


def test_fingerprint_mismatch_blocks_pre_codex():
    verdict = prove_pre_codex_ready({
        "claimed": _candidate(),
        "observed": _candidate(content=HASH_B),
        "tests": _clear_tests(),
        "human_relays": [{"kind": "worker"}],
    })
    assert verdict.status == "blocked"
    assert verdict.reason == "mismatched"
    assert verdict.ready is False
    assert verdict.matched is False


def test_pre_codex_prose_is_not_ready():
    verdict = prove_pre_codex_ready("PRE_CODEX_READY")
    assert verdict.status == "unmeasured"
    assert verdict.reason == "prose_not_receipt"
    assert verdict.ready is None
    assert "PRE_CODEX_READY" not in verdict.to_json()


def test_pre_codex_reload_and_tamper():
    verdict = prove_pre_codex_ready({
        "claimed": _candidate(),
        "observed": _candidate(),
        "tests": _clear_tests(),
        "human_relays": [{"kind": "effect_confirmed", "actor": "human"}],
    })
    assert verdict.ready is True
    assert ReleaseVerdict.from_json(verdict.to_json()) == verdict
    raw = json.loads(verdict.to_json())
    raw["ready"] = False
    raw["verified"] = True
    again = ReleaseVerdict.from_json(json.dumps(raw))
    assert again.status == "rejected"
    assert again.verified is False
    assert again.ready is None
