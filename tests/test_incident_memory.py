import sys
import pytest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
from incident_memory import IncidentMemoryRecord

def test_windows_freeze_incident_memory():
    # Construct the canonical memory for the notorious Windows Freeze
    incident = IncidentMemoryRecord(
        incident_id="INC-2026-WIN-FREEZE-01",
        symptom="Courier queue stopped processing on Windows without crashing or emitting an error.",
        observation="The runner process was still alive in Task Manager, but CPU usage was 0% and no logs were written for 4 hours.",
        agent_report="Last known log line was 'Waiting for OS permission...' before complete silence.",
        verified_evidence=[
            "logs/courier_host_20261001.log",
            "evidence_id:mem-freeze-trace-1"
        ],
        root_cause_hypothesis="A blocking UI prompt was spawned in the background session where it could not be interacted with.",
        confirmed_root_cause="The underlying installer executable requested UAC elevation synchronously on session 0, deadlocking the parent process waiting for stdout.",
        recovery="Bypassed UAC manually in the test harness by setting bypass_sandbox=True and enforcing non-interactive installation flags.",
        counter_test="test_unrelated_process_survival.ps1 and test_startup_timeout.ps1 now strictly enforce process execution timeouts and UI bypass flags.",
        remaining_uncertainty="Whether nested dependencies invoked by the installer might still secretly attempt a GUI spawn ignoring silent flags."
    )
    
    # Serialize to JSON and back to prove format stability
    json_payload = incident.to_json()
    
    # Ensure it's not compressed into a single line like "freeze fixed"
    assert "freeze fixed" not in json_payload.lower()
    
    # Ensure all separated fields survive serialization
    recovered_incident = IncidentMemoryRecord.from_json(json_payload)
    
    assert recovered_incident.incident_id == "INC-2026-WIN-FREEZE-01"
    assert "UAC elevation synchronously" in recovered_incident.confirmed_root_cause
    assert "nested dependencies" in recovered_incident.remaining_uncertainty
    assert len(recovered_incident.verified_evidence) == 2
