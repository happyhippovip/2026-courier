"""Contract tests for CP-16 / P16: Decoupled Worker Capabilities, Provider Preference, and Physical Platform.

Acceptance Criteria:
1. Generische Arbeit bleibt plattformneutral (Windows, macOS, Linux).
2. Echte macOS-/Windows-Anforderungen bleiben strikt (unpassende Plattformen ausgeschlossen).
3. Antigravity ist ein Provider/Agenten-Laufzeitvertrag und nicht an macOS gekoppelt.
4. Unqualifizierte Worker (fehlende Capabilities) bleiben strikt ausgeschlossen.
5. Providerpräferenz vergibt Prioritätsbonus, ohne plattformneutrale Fallbacks abzuwürgen.
6. End-to-End Server-Claim belegt korrekte Zuweisung über alle Schnittstellen.
"""

import json
import pytest
from pathlib import Path

from courier_core.capability_matcher import (
    CapabilityVocabulary,
    PlatformVocabulary,
    ProviderVocabulary,
    WorkerCapabilities,
    TaskRequirements,
    MatchResult,
    match_capabilities,
    parse_task_routing,
    parse_worker_capabilities,
    CapabilityRegistry,
)
import server.app
from server.app import app, save_state


@pytest.fixture
def test_client(tmp_path, monkeypatch):
    state_file = tmp_path / "test_server_state.json"
    monkeypatch.setattr(server.app, "STATE_FILE", str(state_file))
    initial_state = {
        "tasks": {},
        "goals": {},
        "workers": {},
        "goal_idempotency": {},
        "_startup_reconciled": True,
    }
    state_file.write_text(json.dumps(initial_state), encoding="utf-8")
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


def get_auth_headers():
    return {
        "Authorization": f"Bearer {server.app.API_KEY}",
        "Content-Type": "application/json",
    }


def test_generic_work_is_platform_neutral():
    """CP-16 Acceptance: Generic work without explicit OS requirement runs on any platform."""
    req_generic = TaskRequirements(
        work_item_id="task-generic-01",
        required_os=None,  # platform-neutral
        required_capabilities=[CapabilityVocabulary.PYTHON],
    )

    win_worker = WorkerCapabilities(
        worker_id="win-node",
        os=PlatformVocabulary.WINDOWS,
        capabilities=[CapabilityVocabulary.PYTHON, CapabilityVocabulary.POWERSHELL],
    )
    mac_worker = WorkerCapabilities(
        worker_id="mac-node",
        os=PlatformVocabulary.MACOS,
        capabilities=[CapabilityVocabulary.PYTHON, CapabilityVocabulary.BASH],
    )
    linux_worker = WorkerCapabilities(
        worker_id="linux-node",
        os=PlatformVocabulary.LINUX,
        capabilities=[CapabilityVocabulary.PYTHON, CapabilityVocabulary.BASH],
    )

    res_win = match_capabilities(win_worker, req_generic)
    res_mac = match_capabilities(mac_worker, req_generic)
    res_lin = match_capabilities(linux_worker, req_generic)

    assert res_win.matched is True
    assert res_mac.matched is True
    assert res_lin.matched is True


def test_strict_os_requirements_exclude_other_platforms():
    """CP-16 Acceptance: Echte macOS-/Windows-Anforderungen bleiben strikt."""
    req_mac = TaskRequirements(
        work_item_id="task-mac-build",
        required_os=PlatformVocabulary.MACOS,
    )
    req_win = TaskRequirements(
        work_item_id="task-win-build",
        required_os=PlatformVocabulary.WINDOWS,
    )

    win_worker = WorkerCapabilities(worker_id="win-1", os="windows", capabilities=["windows"])
    mac_worker = WorkerCapabilities(worker_id="mac-1", os="macos", capabilities=["macos"])
    linux_worker = WorkerCapabilities(worker_id="linux-1", os="linux", capabilities=["linux"])

    # macOS requirement: only mac matches, windows and linux fail closed
    res_mac_on_mac = match_capabilities(mac_worker, req_mac)
    res_mac_on_win = match_capabilities(win_worker, req_mac)
    res_mac_on_lin = match_capabilities(linux_worker, req_mac)

    assert res_mac_on_mac.matched is True
    assert res_mac_on_win.matched is False
    assert any("OS mismatch" in r for r in res_mac_on_win.reasons)
    assert res_mac_on_lin.matched is False
    assert any("OS mismatch" in r for r in res_mac_on_lin.reasons)

    # Windows requirement: only win matches, mac and linux fail closed
    res_win_on_win = match_capabilities(win_worker, req_win)
    res_win_on_mac = match_capabilities(mac_worker, req_win)
    res_win_on_lin = match_capabilities(linux_worker, req_win)

    assert res_win_on_win.matched is True
    assert res_win_on_mac.matched is False
    assert any("OS mismatch" in r for r in res_win_on_mac.reasons)
    assert res_win_on_lin.matched is False
    assert any("OS mismatch" in r for r in res_win_on_lin.reasons)


def test_antigravity_provider_is_decoupled_from_macos():
    """CP-16 Acceptance: Antigravity is a provider runtime, NOT coupled to macOS.
    
    A Windows worker running Antigravity MUST be eligible for Antigravity tasks.
    """
    req_agy = TaskRequirements(
        work_item_id="task-agy-01",
        required_provider=ProviderVocabulary.ANTIGRAVITY,
        required_os=None,  # platform-neutral provider task
    )

    # Windows worker with Antigravity
    win_agy = WorkerCapabilities(
        worker_id="win-grokbot",
        os="windows",
        supported_providers=[ProviderVocabulary.ANTIGRAVITY],
        capabilities=["windows", CapabilityVocabulary.PYTHON],
    )
    # Mac worker with Antigravity
    mac_agy = WorkerCapabilities(
        worker_id="mac-courier",
        os="macos",
        supported_providers=[ProviderVocabulary.ANTIGRAVITY],
        capabilities=["macos", CapabilityVocabulary.PYTHON],
    )
    # Generic worker without Antigravity
    plain_worker = WorkerCapabilities(
        worker_id="plain-node",
        os="windows",
        supported_providers=["local"],
        capabilities=["windows"],
    )

    res_win = match_capabilities(win_agy, req_agy)
    res_mac = match_capabilities(mac_agy, req_agy)
    res_plain = match_capabilities(plain_worker, req_agy)

    assert res_win.matched is True, "Windows Antigravity worker must match Antigravity task"
    assert res_mac.matched is True, "Mac Antigravity worker must match Antigravity task"
    assert res_plain.matched is False, "Worker without Antigravity must fail closed"
    assert any("Provider 'antigravity' not supported" in r for r in res_plain.reasons)


def test_strict_provider_and_os_combination():
    """CP-16 Acceptance: When both provider and OS are required, both must be satisfied."""
    req_mac_agy = TaskRequirements(
        work_item_id="task-mac-agy-only",
        required_os=PlatformVocabulary.MACOS,
        required_provider=ProviderVocabulary.ANTIGRAVITY,
    )

    win_agy = WorkerCapabilities(worker_id="win-agy", os="windows", supported_providers=["antigravity"])
    mac_agy = WorkerCapabilities(worker_id="mac-agy", os="macos", supported_providers=["antigravity"])
    mac_plain = WorkerCapabilities(worker_id="mac-plain", os="macos", supported_providers=["local"])

    assert match_capabilities(mac_agy, req_mac_agy).matched is True
    assert match_capabilities(win_agy, req_mac_agy).matched is False  # OS mismatch
    assert match_capabilities(mac_plain, req_mac_agy).matched is False  # Provider mismatch


def test_unqualified_worker_missing_capability_is_excluded():
    """CP-16 Acceptance: Unqualifizierte Worker bleiben ausgeschlossen."""
    req_powershell = TaskRequirements(
        work_item_id="task-ps-01",
        required_capabilities=[CapabilityVocabulary.POWERSHELL],
    )

    worker_with_ps = WorkerCapabilities(
        worker_id="win-worker",
        os="windows",
        capabilities=[CapabilityVocabulary.POWERSHELL, CapabilityVocabulary.PYTHON],
    )
    worker_without_ps = WorkerCapabilities(
        worker_id="linux-worker",
        os="linux",
        capabilities=[CapabilityVocabulary.BASH, CapabilityVocabulary.PYTHON],
    )

    assert match_capabilities(worker_with_ps, req_powershell).matched is True
    res_fail = match_capabilities(worker_without_ps, req_powershell)
    assert res_fail.matched is False
    assert any("Missing required capability 'powershell'" in r for r in res_fail.reasons)


def test_provider_preference_boosts_affinity_without_disqualifying():
    """CP-16 Acceptance: Soft provider preference awards bonus score without hard disqualification."""
    req_pref = TaskRequirements(
        work_item_id="task-pref-01",
        required_os=None,
        provider_preference=ProviderVocabulary.ANTIGRAVITY,
    )

    worker_with_pref = WorkerCapabilities(
        worker_id="node-agy",
        os="windows",
        supported_providers=[ProviderVocabulary.ANTIGRAVITY],
    )
    worker_without_pref = WorkerCapabilities(
        worker_id="node-standard",
        os="windows",
        supported_providers=["local"],
    )

    res_with = match_capabilities(worker_with_pref, req_pref)
    res_without = match_capabilities(worker_without_pref, req_pref)

    assert res_with.matched is True
    assert res_without.matched is True
    assert res_with.score > res_without.score
    assert res_with.score - res_without.score == 50.0


def test_parse_task_routing_decouples_antigravity_from_macos():
    """CP-16 Acceptance: parse_task_routing maps target_agent='antigravity' to provider, not macos."""
    legacy_task = {
        "task_id": "t-legacy",
        "target_agent": "antigravity",
    }
    req = parse_task_routing(legacy_task)
    assert req.required_provider == ProviderVocabulary.ANTIGRAVITY
    assert req.required_os is None, "antigravity target must remain platform-neutral"

    mac_task = {"task_id": "t-mac", "target_agent": "mac"}
    req_mac = parse_task_routing(mac_task)
    assert req_mac.required_os == PlatformVocabulary.MACOS

    generic_task = {"task_id": "t-gen", "target_agent": "generic"}
    req_gen = parse_task_routing(generic_task)
    assert req_gen.required_os is None


def test_server_app_claim_routes_generic_task_to_windows_worker(test_client):
    """CP-16 Acceptance: Server /tasks/claim allows Windows worker to claim generic work."""
    auth_headers = get_auth_headers()

    # Register Windows worker
    reg_res = test_client.post(
        "/workers/register",
        headers=auth_headers,
        data=json.dumps({"worker_id": "win-node-01", "platform": "windows", "capabilities": ["windows"]}),
    )
    assert reg_res.status_code == 200

    # Submit Goal with a generic task
    goal_res = test_client.post(
        "/goals",
        headers=auth_headers,
        data=json.dumps({
            "goal_text": "Generic work test",
            "workflow_plan": [{"instruction": "Process dataset", "target_agent": "generic"}],
        }),
    )
    assert goal_res.status_code == 200

    # Windows worker claims task: MUST SUCCEED (platform-neutral)
    claim_res = test_client.post(
        "/tasks/claim",
        headers=auth_headers,
        data=json.dumps({"worker_id": "win-node-01"}),
    )
    assert claim_res.status_code == 200
    claim_data = claim_res.get_json()
    assert claim_data["task"] is not None
    assert claim_data["task"]["instruction"] == "Process dataset"


def test_server_app_claim_routes_antigravity_to_windows_antigravity_worker(test_client):
    """CP-16 Acceptance: Server /tasks/claim allows Windows Antigravity worker to claim Antigravity work."""
    auth_headers = get_auth_headers()

    # Register Windows worker with Antigravity capability
    reg_res = test_client.post(
        "/workers/register",
        headers=auth_headers,
        data=json.dumps({
            "worker_id": "win-grokbot-01",
            "platform": "windows",
            "capabilities": ["windows", "antigravity"],
        }),
    )
    assert reg_res.status_code == 200

    # Submit Goal targeting Antigravity
    goal_res = test_client.post(
        "/goals",
        headers=auth_headers,
        data=json.dumps({
            "goal_text": "Code writing with Antigravity",
            "workflow_plan": [{"instruction": "Write decoupled router", "target_agent": "antigravity"}],
        }),
    )
    assert goal_res.status_code == 200

    # Windows Antigravity worker claims task: MUST SUCCEED
    claim_res = test_client.post(
        "/tasks/claim",
        headers=auth_headers,
        data=json.dumps({"worker_id": "win-grokbot-01"}),
    )
    assert claim_res.status_code == 200
    claim_data = claim_res.get_json()
    assert claim_data["task"] is not None
    assert claim_data["task"]["instruction"] == "Write decoupled router"
