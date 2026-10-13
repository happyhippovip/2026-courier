"""Fail-closed pilot artifacts. No contact, no invoice, no gate pass.

The twelve catalog candidates are Gate-5 preparation. This module does not
mark Gate 1, Gate 2, or Gate 4 as passed.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any, Mapping

SCHEMA = "courier.pilot_candidate.v1"
STATUSES = frozenset({"clear", "gap", "blocked", "redacted", "stop", "rejected"})

_GATES = (
    ("token", re.compile(r"sk-[A-Za-z0-9_-]{8,}")),
    ("assignment", re.compile(r"(?i)(?:api[_-]?key|token|password|secret)\s*[:=]\s*\S+")),
    ("private_key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("local_path", re.compile(r"(?:/Users/|/home/|[A-Za-z]:\\Users\\)\S+")),
    ("private_repo", re.compile(r"happyhippovip/2026-project-memory")),
    ("bearer", re.compile(r"Bearer\s+\S+")),
    ("aws_key", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("email", re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")),
)

_NOT_INCLUDED = (
    "payment",
    "unattended_ab",
    "restart_guarantee",
    "product_shell",
    "installer_as_product",
    "legal_invoice",
)

_QUESTIONS = (
    ("Woran erkennst du, dass eine Arbeit unterbrochen wurde?", "Ein genanntes letztes Artefakt oder der Satz, es gebe keins."),
    ("Was ist der letzte Stand, den du wiederfinden musst?", "Ein konkreter Datei- oder Aufgabenname aus der letzten Sitzung."),
    ("Wie viele Minuten brauchst du heute, um nach einer Pause wieder anzufangen?", "Eine Zahl vom Kunden, nicht von Courier geschätzt."),
    ("Welche Information fehlt dir nach der Pause als erstes?", "Eine fehlende Angabe, vom Kunden benannt."),
    ("Wie oft ist in den letzten sieben Tagen Arbeit zwischen zwei Werkzeugen per Kopieren verloren gegangen?", "Eine Anzahl aus der letzten Woche, vom Kunden genannt."),
    ("Wer muss etwas von Hand weitergeben, damit es weitergeht?", "Eine Rolle oder die Antwort niemand."),
    ("Welches Ergebnis würdest du als wiederaufgenommen akzeptieren?", "Ein prüfbares Ergebnis, das der Kunde vorher beschreibt."),
    ("Welche Daten dürfen dabei nicht an Dritte gehen?", "Eine Datenklasse oder die Antwort keine."),
    ("Wann würdest du abbrechen, weil der nächste Schritt unklar ist?", "Eine Stopp-Bedingung in den Worten des Kunden."),
    ("Woran würdest du am nächsten Tag erkennen, dass genau dort weitergemacht wurde?", "Ein Vergleichspunkt zum letzten belegten Stand."),
)

_SCENES = (
    {
        "claim": "Ein Goal-Contract kann lokal auf Pflichtfelder geprüft werden.",
        "status": "SHOWN",
        "evidence_ref": "courier_core/goal_contract.py",
        "speech": "Nur den lokalen Vertrag zeigen, keinen Kundenlauf.",
    },
    {
        "claim": "Das Journal hängt Events nur an.",
        "status": "SHOWN",
        "evidence_ref": "courier_core/journal.py",
        "speech": "Append-only zeigen. Keinen Löschvorgang behaupten.",
    },
    {
        "claim": "Eine menschliche Bestätigung ist keine Verifikation.",
        "status": "SHOWN",
        "evidence_ref": "courier_core/state_machine.py",
        "speech": "effect_confirmed nicht als verified bezeichnen.",
    },
    {
        "claim": "Gate 4 Restart ohne Replay ist nicht bewiesen.",
        "status": "PLANNED",
        "evidence_ref": None,
        "speech": "Nicht als funktionierenden Neustart zeigen.",
    },
    {
        "claim": "Autonome Ausführung von A nach B ist nicht bewiesen.",
        "status": "PLANNED",
        "evidence_ref": None,
        "speech": "Nicht als Autonomie zeigen.",
    },
    {
        "claim": "Bezahlter Pilot und Rechnung sind nicht freigegeben.",
        "status": "PLANNED",
        "evidence_ref": None,
        "speech": "Keine Preise und keine Rechnung nennen.",
    },
)

_METRICS = (
    ("Konnte die unterbrochene Arbeit wieder aufgenommen werden?", "ja/nein"),
    ("Wie nah am letzten Stand war der Wiedereinstieg?", "0-4"),
    ("Musste etwas von Hand übertragen werden?", "ja/nein"),
    ("War der nächste Schritt ohne Erklärung klar?", "ja/nein"),
    ("Würdest du denselben Ablauf noch einmal zulassen?", "ja/nein"),
    ("Wie viele Minuten hat die Wiederaufnahme gedauert?", "ganze Minuten oder leer"),
    ("Fehlte eine Information, die vor der Pause schon da war?", "ja/nein"),
)

_FAQS = (
    {
        "question": "Löscht das Event-Journal seine eigene Historie?",
        "status": "BELEGT",
        "evidence_ref": "courier_core/journal.py",
        "needle": "DELETE",
        "answer": "UPDATE und DELETE auf events werden von der Journal-Schicht abgewiesen. Das ist kein Kunden-Löschdialog.",
    },
    {
        "question": "Kann eine lokale Pause weitere Home-Agent-Arbeit stoppen?",
        "status": "BELEGT",
        "evidence_ref": "courier_runtime/home_agent.py",
        "needle": "paused",
        "answer": "Ein lokales paused-Grant stoppt die erlaubte Arbeit. Es gibt dafür keine Kundenoberfläche in diesem Paket.",
    },
    {
        "question": "Gibt es eine lokale Zusammenfassung akzeptierter Results?",
        "status": "BELEGT",
        "evidence_ref": "courier_core/result_digest.py",
        "needle": "Read-only",
        "answer": "Der Result-Digest liest akzeptierte Results und schreibt sie nicht um. Das ist kein Pilotbeweis.",
    },
    {
        "question": "Kann ich einen Kundenexport meiner Pilotdaten anfordern?",
        "status": "UNKNOWN",
        "evidence_ref": None,
        "answer": "Ein Kundenexport ist hier nicht belegt und wird nicht ausgeführt.",
    },
    {
        "question": "Kann Courier auf Wunsch meine Dateien löschen?",
        "status": "UNKNOWN",
        "evidence_ref": None,
        "answer": "Eine Kundenlöschung ist hier nicht belegt und wird nicht ausgeführt.",
    },
    {
        "question": "Ist die Windows-Pilotinstallation auf einer sauberen Maschine gelaufen?",
        "status": "UNKNOWN",
        "evidence_ref": None,
        "answer": "Ein Skript kann vorhanden sein. Eine beobachtete Installation ist das nicht.",
    },
    {
        "question": "Macht Courier am nächsten Tag unbeaufsichtigt weiter?",
        "status": "GEPLANT",
        "evidence_ref": None,
        "answer": "Das ist das Pilotversprechen, nicht ein belegter Ablauf.",
    },
    {
        "question": "Gibt es eine freigegebene Rechnung für den Pilot?",
        "status": "GEPLANT",
        "evidence_ref": None,
        "answer": "Steuerstatus und Rechtsfreigabe sind unbekannt. Es wird keine Rechnung ausgestellt.",
    },
)


@dataclass(frozen=True)
class PilotArtifact:
    artifact: str
    status: str
    reason: str
    payload_json: str
    intact: bool
    digest: str

    def payload(self) -> dict[str, Any]:
        return json.loads(self.payload_json)

    def to_json(self) -> str:
        body = {
            "schema": SCHEMA,
            "artifact": self.artifact,
            "status": self.status,
            "reason": self.reason,
            "payload": self.payload(),
            "intact": self.intact,
            "digest": self.digest,
        }
        return json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False)

    @staticmethod
    def from_json(text: str) -> "PilotArtifact":
        return _from_json(text)


def critical_path() -> PilotArtifact:
    """Plan statuses. None of the open gates is marked passed."""
    return _emit("CRITICAL_PATH", "clear", "not_claimed", {
        "g1": "IN_PROGRESS",
        "g2": "IN_PROGRESS",
        "g3": "NOT_PROVEN",
        "g4": "NOT_PROVEN",
        "g5": "NOT_STARTED",
        "g6": "LOCKED",
        "g7": "LOCKED",
    })


def pilot_proof_card(
    *,
    source_sha: str | None = None,
    test_ref: str | None = None,
    description: str | None = None,
    unknowns: list[str] | None = None,
    autonomy_ab: bool = False,
    proof_level: str | None = None,
    evidence_ids: list[str] | None = None,
) -> PilotArtifact:
    if isinstance(description, str) and _hits(description):
        return _emit("PILOT_PROOF_CARD_V1", "blocked", "secret_in_card", {
            "autonomy_ab": False,
            "unknowns": ["Beschreibung enthält gesperrtes Material"],
        })
    if autonomy_ab and (proof_level not in {"P2", "P3"} or not evidence_ids):
        return _emit("PILOT_PROOF_CARD_V1", "blocked", "autonomy_not_evidenced", {
            "autonomy_ab": False,
            "proof_level": "UNKNOWN",
            "unknowns": list(unknowns or ["Autonomie ist nicht belegt"]),
        })
    if proof_level in {"P2", "P3"} and not evidence_ids:
        return _emit("PILOT_PROOF_CARD_V1", "blocked", "proof_level_not_evidenced", {
            "autonomy_ab": False,
            "proof_level": "UNKNOWN",
            "unknowns": list(unknowns or ["Prüfstufe ist nicht belegt"]),
        })
    missing = [name for name, value in (
        ("source_sha", source_sha),
        ("test_ref", test_ref),
        ("description", description),
    ) if not isinstance(value, str) or not value]
    if missing or not unknowns:
        named = list(unknowns or [])
        named.extend(missing or ["unknowns"])
        return _emit("PILOT_PROOF_CARD_V1", "gap", "missing_evidence", {
            "source_sha": source_sha if isinstance(source_sha, str) else None,
            "test_ref": test_ref if isinstance(test_ref, str) else None,
            "autonomy_ab": False,
            "proof_level": proof_level if proof_level in {"P0", "P1"} else "UNKNOWN",
            "unknowns": named,
        })
    return _emit("PILOT_PROOF_CARD_V1", "clear", "clear", {
        "source_sha": source_sha,
        "test_ref": test_ref,
        "description": description,
        "unknowns": list(unknowns),
        "autonomy_ab": False,
        "proof_level": proof_level if proof_level in {"P0", "P1"} else "UNKNOWN",
    })


def pilot_discovery_questions(*, answers: Mapping[str, str] | None = None) -> PilotArtifact:
    if answers is not None:
        return _emit("PILOT_DISCOVERY_10Q", "blocked", "invented_answers", {
            "contacted": False,
            "questions": [],
        })
    return _emit("PILOT_DISCOVERY_10Q", "clear", "clear", {
        "contacted": False,
        "questions": [
            {"question": text, "purpose": purpose, "answer": None}
            for text, purpose in _QUESTIONS
        ],
    })


def pilot_packages(*, price_eur: int | None = None) -> PilotArtifact:
    if price_eur is not None:
        return _emit("PILOT_PACKAGE_BOUNDARIES", "blocked", "invented_price", {"packages": []})
    shared = {
        "not_included": list(_NOT_INCLUDED),
        "acceptance_signal": "Der Kunde erkennt den letzten belegten Stand wieder.",
        "support_need": "Begleitet. Kein unbeaufsichtigter Lauf.",
        "open_evidence": ["keine unabhängige A-nach-B-Ausführung", "Gate 4 nicht bewiesen"],
    }
    return _emit("PILOT_PACKAGE_BOUNDARIES", "clear", "clear", {
        "gates": critical_path().payload(),
        "packages": [
            {"id": "accompanied_resume", "scope": "Eine begleitete Wiederaufnahme eines genannten Stands.", **shared},
            {"id": "next_session_note", "scope": "Eine Notiz, wo die nächste Sitzung beginnen würde.", **shared},
        ],
    })


def invoice_fields() -> PilotArtifact:
    return _emit("INVOICE_READINESS_FIELDS", "clear", "clear", {
        "fields": [
            "seller_name",
            "seller_address",
            "tax_number",
            "invoice_number",
            "invoice_date",
            "service_description",
            "net_amount",
            "vat_rate",
            "vat_amount",
            "gross_amount",
            "customer_name",
        ],
        "tax_status": "UNKNOWN",
        "legal_approval": False,
        "invoice_issued": False,
    })


def issue_invoice(**_ignored: Any) -> PilotArtifact:
    return _emit("INVOICE_READINESS_FIELDS", "blocked", "no_invoice", {
        "invoice_issued": False,
        "legal_approval": False,
        "tax_status": "UNKNOWN",
    })


def unit_economics(rows: list[Mapping[str, Any]] | None) -> PilotArtifact:
    formula = "price_floor_cents = sum(evidenced cost cents); quoted_price_eur stays unset"
    empty = {"quoted_price_eur": None, "evidenced_sum_cents": None, "formula": formula, "missing": []}
    if not rows:
        empty["missing"] = ["cost_receipts"]
        return _emit("PILOT_UNIT_ECONOMICS_SCHEMA", "gap", "no_cost_receipts", empty)
    for row in rows:
        if not isinstance(row, Mapping) or row.get("kind") == "quota_percent":
            return _emit("PILOT_UNIT_ECONOMICS_SCHEMA", "blocked", "quota_is_not_money", empty)
        if row.get("kind") != "eur_cents":
            return _emit("PILOT_UNIT_ECONOMICS_SCHEMA", "blocked", "invalid_input", empty)
        if not isinstance(row.get("evidence_ref"), str) or not row.get("evidence_ref"):
            return _emit("PILOT_UNIT_ECONOMICS_SCHEMA", "blocked", "missing_receipt", empty)
        amount = row.get("amount")
        if isinstance(amount, bool) or not isinstance(amount, int) or amount < 0:
            return _emit("PILOT_UNIT_ECONOMICS_SCHEMA", "blocked", "invalid_input", empty)
    total = sum(int(row["amount"]) for row in rows)
    return _emit("PILOT_UNIT_ECONOMICS_SCHEMA", "clear", "clear", {
        "quoted_price_eur": None,
        "evidenced_sum_cents": total,
        "formula": formula,
        "missing": [],
    })


def demo_storyboard(scenes: list[Mapping[str, Any]] | None = None) -> PilotArtifact:
    chosen = list(_SCENES if scenes is None else scenes)
    if len(chosen) > 6:
        return _emit("DEMO_90_SECONDS_TRUTHFUL", "blocked", "too_many_scenes", {"scenes": []})
    cleaned = []
    for scene in chosen:
        if not isinstance(scene, Mapping):
            return _emit("DEMO_90_SECONDS_TRUTHFUL", "blocked", "invalid_input", {"scenes": []})
        status = scene.get("status")
        if status not in {"SHOWN", "PLANNED"} or not scene.get("claim") or not scene.get("speech"):
            return _emit("DEMO_90_SECONDS_TRUTHFUL", "blocked", "invalid_input", {"scenes": []})
        evidence = scene.get("evidence_ref")
        if status == "SHOWN" and (not isinstance(evidence, str) or not evidence):
            return _emit("DEMO_90_SECONDS_TRUTHFUL", "blocked", "shown_without_evidence", {"scenes": []})
        if status == "PLANNED":
            evidence = None
        cleaned.append({
            "claim": scene["claim"],
            "status": status,
            "evidence_ref": evidence,
            "speech": scene["speech"],
        })
    return _emit("DEMO_90_SECONDS_TRUTHFUL", "clear", "clear", {"scenes": cleaned})


def approval_card(
    *,
    decision: str | None = None,
    actor: str | None = None,
    cost_cents: int | None = None,
) -> PilotArtifact:
    payload = {
        "choice": None,
        "granted": False,
        "active_grant": False,
        "cost_display": "UNKNOWN" if cost_cents is None else cost_cents,
        "limit_display": "UNKNOWN",
        "yes_effect": "Eine Zusage wird nur vorgemerkt. Es entsteht keine aktive Freigabe.",
        "no_effect": "Es wird nichts freigegeben.",
    }
    if decision is None:
        return _emit("CUSTOMER_APPROVAL_CARD_SPEC", "clear", "fail_closed", payload)
    if decision not in {"yes", "no"} or (decision == "yes" and actor != "human"):
        return _emit("CUSTOMER_APPROVAL_CARD_SPEC", "blocked", "unsigned", payload)
    if isinstance(cost_cents, bool) or (cost_cents is not None and (not isinstance(cost_cents, int) or cost_cents < 0)):
        return _emit("CUSTOMER_APPROVAL_CARD_SPEC", "blocked", "invalid_input", payload)
    payload["choice"] = decision
    return _emit("CUSTOMER_APPROVAL_CARD_SPEC", "clear", "recorded", payload)


def redact_demo(text: Any) -> PilotArtifact:
    if not isinstance(text, str):
        return _emit("DEMO_REDACTION_GATE", "blocked", "not_text", {"gates_checked": len(_GATES), "text": ""})
    redacted = text
    hits = 0
    for _name, pattern in _GATES:
        redacted, count = pattern.subn("[REDACTED]", redacted)
        hits += count
    if hits and any(pattern.search(redacted) for _name, pattern in _GATES):
        return _emit("DEMO_REDACTION_GATE", "blocked", "redaction_incomplete", {
            "gates_checked": len(_GATES),
            "text": "",
        })
    status = "redacted" if hits else "clear"
    return _emit("DEMO_REDACTION_GATE", status, status, {
        "gates_checked": len(_GATES),
        "redactions": hits,
        "text": redacted,
    })


def roi_from_customer(
    *,
    minutes: int | None = None,
    resumes_per_week: int | None = None,
    hourly_cents: int | None = None,
    promise: bool = False,
) -> PilotArtifact:
    payload = {
        "computed_cents": None,
        "promised": False,
        "missing": [],
        "formula": "minutes * hourly_cents * resumes_per_week // 60",
    }
    if promise:
        return _emit("PILOT_ROI_INPUT_SCHEMA", "blocked", "promised_savings", payload)
    values = {"minutes": minutes, "resumes_per_week": resumes_per_week, "hourly_cents": hourly_cents}
    missing = [name for name, value in values.items() if value is None]
    if missing:
        payload["missing"] = missing
        return _emit("PILOT_ROI_INPUT_SCHEMA", "gap", "missing_input", payload)
    if any(isinstance(value, bool) or not isinstance(value, int) or value < 0 for value in values.values()):
        return _emit("PILOT_ROI_INPUT_SCHEMA", "blocked", "invalid_input", payload)
    payload["computed_cents"] = minutes * hourly_cents * resumes_per_week // 60
    return _emit("PILOT_ROI_INPUT_SCHEMA", "clear", "customer_input_only", payload)


def feedback_metrics(*, results: list[Any] | None = None) -> PilotArtifact:
    if results is not None:
        return _emit("PILOT_FEEDBACK_7_METRICS", "blocked", "invented_results", {
            "anonymous": True,
            "aggregate": None,
            "metrics": [],
        })
    return _emit("PILOT_FEEDBACK_7_METRICS", "clear", "clear", {
        "anonymous": True,
        "aggregate": None,
        "metrics": [
            {"question": question, "scale": scale, "result": None}
            for question, scale in _METRICS
        ],
    })


def install_precheck(
    *,
    script_present: bool,
    execution_observed: bool,
    log_ref: str | None = None,
) -> PilotArtifact:
    payload = {
        "product_ready": False,
        "installer_executed": False,
        "script_present": bool(script_present),
        "prerequisites": ["Windows-Host", "begleitete Einrichtung", "kein Anspruch auf einen fertigen Installer"],
        "blocker": "Eine saubere Installation wurde nicht beobachtet.",
    }
    if execution_observed and not log_ref:
        return _emit("PILOT_INSTALL_PRECHECK", "blocked", "false_install_claim", payload)
    if not execution_observed:
        return _emit("PILOT_INSTALL_PRECHECK", "stop", "installer_not_executed", payload)
    return _emit("PILOT_INSTALL_PRECHECK", "gap", "log_not_reviewed", payload)


def exit_faq() -> PilotArtifact:
    return _emit("PILOT_EXIT_FAQ", "clear", "clear", {
        "deleted": False,
        "exported": False,
        "faqs": [dict(item) for item in _FAQS],
    })


def _hits(text: str) -> bool:
    return any(pattern.search(text) for _name, pattern in _GATES)


def _emit(artifact: str, status: str, reason: str, payload: dict[str, Any]) -> PilotArtifact:
    payload_json = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    digest = _digest(artifact, status, reason, json.loads(payload_json))
    return PilotArtifact(artifact, status, reason, payload_json, True, digest)


def _digest(artifact: str, status: str, reason: str, payload: Any) -> str:
    body = {
        "schema": SCHEMA,
        "artifact": artifact,
        "status": status,
        "reason": reason,
        "payload": payload,
    }
    raw = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _from_json(text: str) -> PilotArtifact:
    try:
        raw = json.loads(text)
    except json.JSONDecodeError:
        return _rejected()
    if not isinstance(raw, dict) or raw.get("schema") != SCHEMA:
        return _rejected()
    artifact = raw.get("artifact")
    status = raw.get("status")
    reason = raw.get("reason")
    payload = raw.get("payload")
    if not isinstance(artifact, str) or status not in STATUSES or not isinstance(reason, str):
        return _rejected()
    if not isinstance(payload, dict) or raw.get("digest") != _digest(artifact, status, reason, payload):
        return _rejected()
    if raw.get("intact") is not True:
        return _rejected()
    payload_json = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return PilotArtifact(artifact, status, reason, payload_json, True, raw["digest"])


def _rejected() -> PilotArtifact:
    payload_json = "{}"
    digest = _digest("unknown", "rejected", "tampered", {})
    return PilotArtifact("unknown", "rejected", "tampered", payload_json, False, digest)
