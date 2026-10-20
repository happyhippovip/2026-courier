"""Fail-closed pilot artifacts for catalog 3001-3012.

No customer is contacted, no invoice is issued, and no gate is marked passed.
"""

import json
from pathlib import Path

from courier_core.pilot_candidate import (
    PilotArtifact,
    approval_card,
    critical_path,
    demo_storyboard,
    exit_faq,
    feedback_metrics,
    install_precheck,
    invoice_fields,
    issue_invoice,
    pilot_discovery_questions,
    pilot_packages,
    pilot_proof_card,
    redact_demo,
    roi_from_customer,
    unit_economics,
)

ROOT = Path(__file__).resolve().parents[2]
SECRET = "sk-live-SUPERSECRETVALUE"


def test_module_does_not_touch_clock_network_or_files():
    import courier_core.pilot_candidate as pilot

    source = Path(pilot.__file__).read_text(encoding="utf-8")
    for banned in ("datetime.now", "utcnow", "urlopen", "socket", "unlink", "rmtree", "remove("):
        assert banned not in source


def test_critical_path_does_not_pass_open_gates():
    payload = critical_path().payload()
    assert payload["g1"] == "IN_PROGRESS"
    assert payload["g2"] == "IN_PROGRESS"
    assert payload["g3"] == "NOT_PROVEN"
    assert payload["g4"] == "NOT_PROVEN"
    assert "PASS" not in critical_path().payload_json


def test_proof_card_gap_without_sha():
    card = pilot_proof_card(test_ref="tests/core/test_pilot_candidate.py", description="Ein lokaler Vertragstest.")
    assert card.artifact == "PILOT_PROOF_CARD_V1"
    assert card.status == "gap"
    assert card.payload()["autonomy_ab"] is False
    assert card.payload()["unknowns"]


def test_proof_card_blocks_unevidenced_autonomy():
    card = pilot_proof_card(
        source_sha="abc123",
        test_ref="tests/core/test_pilot_candidate.py",
        description="Angeblich autonom von A nach B.",
        unknowns=["keine unabhängige Ausführung"],
        autonomy_ab=True,
        proof_level="P0",
    )
    assert card.status == "blocked"
    assert card.reason == "autonomy_not_evidenced"
    assert card.payload()["autonomy_ab"] is False


def test_proof_card_clear_names_unknowns():
    card = pilot_proof_card(
        source_sha="abc123",
        test_ref="tests/core/test_pilot_candidate.py::test_proof_card_clear_names_unknowns",
        description="Der Vertragstest prüft nur diese Karte, nicht einen Pilotkunden.",
        unknowns=["keine unabhängige A-nach-B-Ausführung"],
        proof_level="P1",
    )
    assert card.status == "clear"
    assert card.payload()["source_sha"] == "abc123"
    assert card.payload()["autonomy_ab"] is False
    assert card.payload()["unknowns"] == ["keine unabhängige A-nach-B-Ausführung"]
    assert PilotArtifact.from_json(card.to_json()) == card


def test_proof_card_blocks_secret_and_tamper():
    card = pilot_proof_card(
        source_sha="abc123",
        test_ref="tests/core/test_pilot_candidate.py",
        description=f"Beleg {SECRET}",
        unknowns=["x"],
        proof_level="P1",
    )
    assert card.status == "blocked"
    assert card.reason == "secret_in_card"
    assert SECRET not in card.to_json()
    clean = pilot_proof_card(
        source_sha="abc123",
        test_ref="tests/core/test_pilot_candidate.py",
        description="Nur ein Vertragstest.",
        unknowns=["keine Pilotausführung"],
        proof_level="P1",
    )
    raw = json.loads(clean.to_json())
    raw["payload"]["autonomy_ab"] = True
    raw["intact"] = True
    forged = PilotArtifact.from_json(json.dumps(raw))
    assert forged.status == "rejected"
    assert forged.intact is False


def test_discovery_has_ten_questions_and_no_answers():
    card = pilot_discovery_questions()
    questions = card.payload()["questions"]
    assert card.artifact == "PILOT_DISCOVERY_10Q"
    assert card.status == "clear"
    assert len(questions) == 10
    assert len({item["question"] for item in questions}) == 10
    assert all(item["answer"] is None and item["purpose"] for item in questions)
    assert card.payload()["contacted"] is False


def test_discovery_rejects_invented_answers():
    card = pilot_discovery_questions(answers={"1": "erfunden"})
    assert card.status == "blocked"
    assert card.reason == "invented_answers"
    assert "erfunden" not in card.to_json()


def test_packages_mark_locked_scope_and_have_no_price():
    card = pilot_packages()
    packages = card.payload()["packages"]
    assert card.artifact == "PILOT_PACKAGE_BOUNDARIES"
    assert card.status == "clear"
    assert len(packages) == 2
    for package in packages:
        assert "price" not in package
        missing = set(package["not_included"])
        assert {"payment", "unattended_ab", "restart_guarantee", "product_shell", "legal_invoice"} <= missing
    assert "€" not in card.payload_json
    assert card.payload()["gates"]["g4"] == "NOT_PROVEN"


def test_packages_reject_a_price():
    card = pilot_packages(price_eur=10)
    assert card.status == "blocked"
    assert card.reason == "invented_price"
    assert "10" not in card.payload_json


def test_invoice_fields_keep_tax_unknown():
    card = invoice_fields()
    payload = card.payload()
    assert card.artifact == "INVOICE_READINESS_FIELDS"
    assert card.status == "clear"
    assert len(payload["fields"]) >= 8
    assert payload["tax_status"] == "UNKNOWN"
    assert payload["legal_approval"] is False
    assert payload["invoice_issued"] is False


def test_issue_invoice_is_blocked():
    card = issue_invoice(gross_cents=100)
    assert card.status == "blocked"
    assert card.reason == "no_invoice"
    assert "100" not in card.payload_json


def test_quota_percent_is_not_money():
    card = unit_economics([{"name": "model", "kind": "quota_percent", "amount": 40}])
    assert card.artifact == "PILOT_UNIT_ECONOMICS_SCHEMA"
    assert card.status == "blocked"
    assert card.reason == "quota_is_not_money"
    assert card.payload()["quoted_price_eur"] is None
    assert "40" not in card.payload_json


def test_unevidenced_euro_is_not_a_price():
    card = unit_economics([{"name": "host", "kind": "eur_cents", "amount": 250}])
    assert card.status == "blocked"
    assert card.reason == "missing_receipt"
    assert card.payload()["evidenced_sum_cents"] is None
    assert "250" not in card.payload_json


def test_evidenced_sum_is_not_a_quoted_price():
    card = unit_economics([
        {"name": "host", "kind": "eur_cents", "amount": 100, "evidence_ref": "receipt-host"},
        {"name": "disk", "kind": "eur_cents", "amount": 50, "evidence_ref": "receipt-disk"},
    ])
    assert card.status == "clear"
    assert card.payload()["evidenced_sum_cents"] == 150
    assert card.payload()["quoted_price_eur"] is None
    assert "price_floor_cents = sum(evidenced cost cents)" in card.payload()["formula"]


def test_storyboard_marks_unproven_steps_planned():
    card = demo_storyboard()
    scenes = card.payload()["scenes"]
    assert card.artifact == "DEMO_90_SECONDS_TRUTHFUL"
    assert card.status == "clear"
    assert 1 <= len(scenes) <= 6
    shown = [scene for scene in scenes if scene["status"] == "SHOWN"]
    planned = [scene for scene in scenes if scene["status"] == "PLANNED"]
    assert shown and planned
    for scene in scenes:
        assert scene["speech"]
        assert scene["claim"]
    for scene in shown:
        evidence = ROOT / scene["evidence_ref"]
        assert evidence.is_file()
    for scene in planned:
        assert scene["evidence_ref"] is None
    assert any("Restart" in scene["claim"] or "Gate 4" in scene["claim"] for scene in planned)


def test_extra_or_unevidenced_scene_is_blocked():
    extra = demo_storyboard(scenes=[{"status": "PLANNED", "claim": "x", "speech": "y"}] * 7)
    assert extra.status == "blocked"
    assert extra.reason == "too_many_scenes"
    bare = demo_storyboard(scenes=[{"status": "SHOWN", "claim": "fertig", "speech": "zeigen", "evidence_ref": None}])
    assert bare.status == "blocked"
    assert bare.reason == "shown_without_evidence"


def test_approval_defaults_fail_closed_and_does_not_grant():
    card = approval_card()
    assert card.artifact == "CUSTOMER_APPROVAL_CARD_SPEC"
    assert card.status == "clear"
    assert card.reason == "fail_closed"
    payload = card.payload()
    assert payload["choice"] is None
    assert payload["granted"] is False
    assert payload["active_grant"] is False
    assert payload["yes_effect"] and payload["no_effect"]
    yes = approval_card(decision="yes", actor="human", cost_cents=0)
    assert yes.payload()["choice"] == "yes"
    assert yes.payload()["granted"] is False
    assert yes.payload()["active_grant"] is False
    unsigned = approval_card(decision="yes")
    assert unsigned.status == "blocked"
    assert unsigned.payload()["granted"] is False


def test_redaction_covers_eight_gates_and_removes_secrets():
    raw = " ".join([
        SECRET,
        "password=hunter2",
        "-----BEGIN PRIVATE KEY-----",
        "/home/ubuntu/secret",
        "happyhippovip/2026-project-memory",
        "Bearer abc.def",
        "AKIA" + "IOSFODNN7EXAMPLE",
        "user@example.com",
    ])
    card = redact_demo(raw)
    assert card.artifact == "DEMO_REDACTION_GATE"
    assert card.status == "redacted"
    assert card.payload()["gates_checked"] >= 8
    text = card.payload()["text"]
    for secret in (SECRET, "hunter2", "BEGIN PRIVATE KEY", "/home/ubuntu", "2026-project-memory", "abc.def", "AKIA" + "IOSFODNN7EXAMPLE", "user@example.com"):
        assert secret not in text
        assert secret not in card.reason


def test_redaction_blocks_non_text():
    card = redact_demo(None)
    assert card.status == "blocked"
    assert card.reason == "not_text"


def test_roi_does_not_promise_savings():
    missing = roi_from_customer(minutes=30, resumes_per_week=None, hourly_cents=100)
    assert missing.artifact == "PILOT_ROI_INPUT_SCHEMA"
    assert missing.status == "gap"
    assert missing.payload()["computed_cents"] is None
    assert missing.payload()["promised"] is False
    negative = roi_from_customer(minutes=-1, resumes_per_week=1, hourly_cents=100)
    assert negative.status == "blocked"
    assert negative.payload()["computed_cents"] is None
    computed = roi_from_customer(minutes=30, resumes_per_week=2, hourly_cents=100)
    assert computed.status == "clear"
    assert computed.payload()["computed_cents"] == 100
    assert computed.payload()["promised"] is False
    promised = roi_from_customer(minutes=30, resumes_per_week=2, hourly_cents=100, promise=True)
    assert promised.status == "blocked"
    assert promised.reason == "promised_savings"
    assert promised.payload()["computed_cents"] is None


def test_feedback_has_seven_scales_and_no_results():
    card = feedback_metrics()
    metrics = card.payload()["metrics"]
    assert card.artifact == "PILOT_FEEDBACK_7_METRICS"
    assert card.status == "clear"
    assert len(metrics) == 7
    assert all(item["scale"] and item["result"] is None for item in metrics)
    assert card.payload()["anonymous"] is True
    assert card.payload()["aggregate"] is None
    invented = feedback_metrics(results=[{"score": 5}])
    assert invented.status == "blocked"
    assert invented.reason == "invented_results"
    assert "5" not in invented.payload_json


def test_install_precheck_stops_without_an_observed_run():
    card = install_precheck(script_present=True, execution_observed=False)
    assert card.artifact == "PILOT_INSTALL_PRECHECK"
    assert card.status == "stop"
    assert card.payload()["product_ready"] is False
    assert card.payload()["installer_executed"] is False
    assert card.reason == "installer_not_executed"
    claimed = install_precheck(script_present=True, execution_observed=True)
    assert claimed.status == "blocked"
    assert claimed.reason == "false_install_claim"
    assert claimed.payload()["installer_executed"] is False


def test_exit_faq_marks_only_checked_facts():
    card = exit_faq()
    items = card.payload()["faqs"]
    assert card.artifact == "PILOT_EXIT_FAQ"
    assert card.status == "clear"
    assert len(items) >= 8
    assert {item["status"] for item in items} <= {"BELEGT", "GEPLANT", "UNKNOWN"}
    assert "GEPLANT" in {item["status"] for item in items}
    assert "UNKNOWN" in {item["status"] for item in items}
    for item in items:
        if item["status"] == "BELEGT":
            evidence = ROOT / item["evidence_ref"]
            assert evidence.is_file()
            assert item["needle"] in evidence.read_text(encoding="utf-8")
        else:
            assert item["evidence_ref"] is None
    assert card.payload()["deleted"] is False
    assert card.payload()["exported"] is False
