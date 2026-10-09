"""P9 hardening: courier_core/config validity, schema conformance and safety pins.

Tests only; no behavior change. Covers the five JSON documents under
courier_core/config: parseability, conformance to the matching schemas in
courier_core/schemas, cross-file consistency, and fail-closed safety
invariants (human-approval publish gates, zero-cost-only, no stored secrets).

No network access. Reads repository data files only; never writes.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = REPO_ROOT / "courier_core" / "config"
SCHEMAS_DIR = REPO_ROOT / "courier_core" / "schemas"

CHANNELS = "social_channels.json"
WORKFLOWS = "content_workflows.json"
LOCAL_TOOLS = "local_tools.json"
STRATEGY = "product_strategy.json"
TEAMWORK = "teamwork_policy.json"

ALL_DOCUMENTS = [CHANNELS, WORKFLOWS, LOCAL_TOOLS, STRATEGY, TEAMWORK]

HUMAN_APPROVAL = "REQUIRE_EXPLICIT_HUMAN_APPROVAL"
ZERO_COST_ONLY = "ZERO_COST_ONLY"

try:
    import jsonschema
except ImportError:  # pragma: no cover - environment without jsonschema
    jsonschema = None

needs_jsonschema = pytest.mark.skipif(
    jsonschema is None, reason="jsonschema package not installed"
)


def load_config(name: str) -> dict:
    path = CONFIG_DIR / name
    assert path.is_file(), f"missing config document: {name}"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        pytest.fail(f"{name} is not valid JSON: {exc}")
    assert isinstance(data, dict), f"{name} top level must be an object"
    return data


def load_schema(name: str) -> dict:
    path = SCHEMAS_DIR / name
    assert path.is_file(), f"missing schema document: {name}"
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.mark.parametrize("name", ALL_DOCUMENTS)
def test_config_documents_parse_as_json_objects(name):
    data = load_config(name)
    assert isinstance(data.get("schema_version"), str)
    assert len(data["schema_version"]) > 0


@needs_jsonschema
def test_social_channels_conform_to_registry_schema():
    jsonschema.validate(load_config(CHANNELS), load_schema("social_channel_registry.schema.json"))


@needs_jsonschema
def test_content_workflows_conform_to_workflow_schema():
    jsonschema.validate(load_config(WORKFLOWS), load_schema("content_workflow.schema.json"))


@needs_jsonschema
def test_local_tools_conform_to_local_tools_schema():
    jsonschema.validate(load_config(LOCAL_TOOLS), load_schema("local_tools.schema.json"))


def test_channels_require_explicit_human_approval_to_publish():
    channels = load_config(CHANNELS).get("channels", [])
    assert len(channels) > 0, "channel registry must not be empty"
    for channel in channels:
        assert channel.get("publishing_policy") == HUMAN_APPROVAL, (
            "channel publishing_policy must require explicit human approval"
        )


def test_channel_ids_are_unique_and_well_formed():
    channels = load_config(CHANNELS).get("channels", [])
    seen = set()
    for channel in channels:
        channel_id = channel.get("channel_id", "")
        assert re.fullmatch(r"chan-[a-z0-9_.-]+", channel_id), (
            "channel_id must match the registry pattern"
        )
        assert channel_id not in seen, "duplicate channel_id in registry"
        seen.add(channel_id)


def test_channel_platforms_are_supported():
    channels = load_config(CHANNELS).get("channels", [])
    for channel in channels:
        assert channel.get("platform") in ("YOUTUBE", "TIKTOK"), (
            "channel platform must be YOUTUBE or TIKTOK"
        )
        assert isinstance(channel.get("channel_label"), str)
        assert len(channel["channel_label"].strip()) >= 2


def test_channel_workflow_bindings_resolve_with_matching_platform():
    channels = load_config(CHANNELS).get("channels", [])
    workflows = {w["workflow_id"]: w for w in load_config(WORKFLOWS).get("workflows", [])}
    assert len(workflows) > 0, "workflow registry must not be empty"
    for channel in channels:
        workflow_id = channel.get("workflow_id")
        assert workflow_id in workflows, "channel workflow_id must resolve to a known workflow"
        assert channel.get("platform") == workflows[workflow_id].get("platform"), (
            "channel platform must match its bound workflow platform"
        )


def test_workflows_require_human_publish_gate_and_zero_cost():
    workflows = load_config(WORKFLOWS).get("workflows", [])
    seen = set()
    for workflow in workflows:
        assert workflow.get("publish_gate") == HUMAN_APPROVAL, (
            "workflow publish_gate must require explicit human approval"
        )
        assert workflow.get("zero_cost_policy") == ZERO_COST_ONLY, (
            "workflow zero_cost_policy must be ZERO_COST_ONLY"
        )
        assert workflow.get("workflow_id") not in seen, "duplicate workflow_id"
        seen.add(workflow["workflow_id"])
        steps = workflow.get("production_steps", [])
        assert len(steps) >= 3, "workflow must define at least 3 production steps"
        assert len(set(steps)) == len(steps), "workflow production steps must be unique"
        assert all(isinstance(step, str) and step for step in steps)


def test_credential_references_are_labels_not_secrets():
    channels = load_config(CHANNELS).get("channels", [])
    for channel in channels:
        ref = channel.get("credential_reference_metadata", "")
        assert re.fullmatch(r"[A-Z0-9_]+", ref), (
            "credential reference must be an uppercase label, never raw secret material"
        )
        assert len(ref) <= 128, "credential reference label must stay short"


def test_strategy_gates_keep_human_approval_and_forbid_autonomous_spend():
    strategy = load_config(STRATEGY)
    gates = strategy.get("gates", {})
    for gate in (
        "TRUST_AND_SAFETY_REQUIRED",
        "GOAL_ALIGNMENT_REQUIRED",
        "EXTERNAL_COMMERCIAL_ACTION_REQUIRES_HUMAN_APPROVAL",
        "PURCHASE_OR_SUBSCRIPTION_UPGRADE_REQUIRES_HUMAN_APPROVAL",
        "PUBLICATION_OR_DEPLOYMENT_REQUIRES_HUMAN_APPROVAL",
        "CUSTOMER_OUTREACH_REQUIRES_HUMAN_APPROVAL",
        "PAYMENT_ACTIVATION_REQUIRES_HUMAN_APPROVAL",
    ):
        assert gates.get(gate) is True, f"strategy gate must stay enabled: {gate}"
    assert gates.get("PAID_OVERAGES_ALLOWED_AUTONOMOUSLY") is False, (
        "autonomous paid overages must stay forbidden"
    )
    order = strategy.get("decision_order", [])
    assert len(order) > 0 and len(set(order)) == len(order)
    scoring = strategy.get("candidate_scoring", {})
    assert len(scoring) > 0
    for dimension, bounds in scoring.items():
        assert 0 <= bounds["min"] <= bounds["max"], (
            f"scoring bounds must be ordered: {dimension}"
        )


def test_teamwork_safety_boundaries_stay_fail_closed():
    policy = load_config(TEAMWORK)
    boundaries = policy.get("safety_boundaries", {})
    assert boundaries.get("cost_policy") == ZERO_COST_ONLY
    assert boundaries.get("secrets_policy") == "NEVER_LOG_OR_STORE_CREDENTIALS"
    rules = policy.get("rules", {})
    modes = {rule.get("mode") for rule in rules.values()}
    assert modes <= {"SINGLE_BOUNDED_AGENT", "MULTI_AGENT_TEAMWORK"}, (
        "teamwork modes must stay within the known set"
    )
    assert len(modes) > 0


def test_local_tools_structure_without_echoing_machine_values():
    """Structural pins only: assertions never embed machine-specific values."""
    data = load_config(LOCAL_TOOLS)
    tools = data.get("tools", {})
    assert {"ffmpeg_binary_path", "godot_binary_path"} <= set(tools), (
        "tools section must declare both binary entries"
    )
    for key in ("ffmpeg_binary_path", "godot_binary_path"):
        value = tools[key]
        ok = value is None or (isinstance(value, str) and len(value) > 0)
        assert ok, f"tool entry must be a non-empty string or null: {key}"
    bindings = data.get("project_bindings", {})
    assert len(bindings) > 0, "at least one project binding must be declared"
    for name, binding in bindings.items():
        assert {"project_path", "project_file", "default_scene", "status"} <= set(binding), (
            f"project binding is missing required keys: {name}"
        )
        ok_file = isinstance(binding["project_file"], str) and binding["project_file"].endswith(
            "project.godot"
        )
        assert ok_file, f"project binding must reference a project file: {name}"
        ok_scene = isinstance(binding["default_scene"], str) and binding["default_scene"].startswith(
            "res://"
        )
        assert ok_scene, f"project binding must reference a scene path: {name}"
        assert binding.get("status") in ("FOUND_READ_ONLY", "NOT_FOUND"), (
            f"project binding status must be a known value: {name}"
        )
