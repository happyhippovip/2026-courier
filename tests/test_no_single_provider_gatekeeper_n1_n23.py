"""Negativtests N1–N23 for the Phase A gate.

Policy stays draft. AUTH_PROOF_STATUS is PARTIAL. N15 is BLOCKED: two local
SQLite files are not a cross-host lock. A passing test for N15 asserts that
blocked result; it does not claim a global fence.
"""
import inspect
from dataclasses import replace
from pathlib import Path

import pytest

from courier_runtime.grants import (
    ACTIVE, AUTH_PROOF_EXTRA_SCOPE, AUTH_PROOF_STATUS, CHECKED, CONTINUITY_OK,
    HOLD, PENDING, REJECT, RECORDED, AuthAttestation, Broker, Gate, Grant, ResumeView,
    equate_status, grant_content_hash, parse_workkey, resume_from_package,
)
from courier_runtime.lease import (
    CROSS_HOST_EXTRA_SCOPE, CROSS_HOST_PROOF, LeaseConflict, LeaseStore, StaleLease,
    assess_cross_host,
)

OWNER = "human-owner"
ISSUER = "issuer-1"
VERIFIER = "verifier-1"
WRITER = "writer-1"
PEER = "peer-9"
REPL = "repl-1"
SCOPE = "files:phase-a"
PROVEN = {OWNER, ISSUER, VERIFIER, WRITER, PEER, "writer-2", REPL, "label-only"}


class Clock:
    def __init__(self, t=1000.0):
        self.t = t

    def __call__(self):
        return self.t


def verifier_for(accepted):
    accepted = set(accepted)

    def _verify(principal_id, proof):
        ok = principal_id in accepted and proof == "external-proof"
        return AuthAttestation(
            principal_id, ok, "external-verifier", "accepted" if ok else "rejected",
        )

    return _verify


def make_gate(tmp_path, clock=None, *, accepted=None, stop="CLEAR", name="lease.db"):
    clock = clock or Clock()
    store = LeaseStore(str(tmp_path / name), clock=clock)
    gate = Gate(
        Broker(clock), store, clock, owner_principal=OWNER,
        auth_verifier=verifier_for(PROVEN if accepted is None else accepted),
        stop_status=stop,
    )
    for pid, caps in (
        (OWNER, ["COORDINATE"]),
        (ISSUER, ["ISSUE_PREAPPROVED_LEASE", "COORDINATE"]),
        (VERIFIER, ["VERIFY_LEASE", "REVIEW_INDEPENDENTLY"]),
        (WRITER, ["WRITE_SCOPED_CODE", "RESUME_WORKKEY"]),
        (PEER, ["RESUME_WORKKEY"]),
    ):
        gate.register(pid, caps, proof="external-proof", host="host-a", spend_limit=0, cost=0)
    return gate, clock, store


def issue(gate, scope=SCOPE, writer=WRITER, host="host-a", grant_id=None):
    grant_id = grant_id or f"g-{scope}-{writer}"
    request = gate.activation_request(writer=writer, scope=scope, host=host, request_id=grant_id)
    gate.broker.authorize(request)
    return gate.broker.grant(
        request, grant_id, expires_at=10_000, granted_by=OWNER, owner_principal=OWNER,
    )


_MISSING = object()


def activate(gate, *, grant=_MISSING, **kw):
    params = dict(
        issuer=ISSUER, verifier=VERIFIER, writer=WRITER, ack_principal=WRITER, scope=SCOPE,
        workkey="wk-1", ttl_s=100, host="host-a", spend_limit=0, requested_by=ISSUER,
        owner_authorizes=False,
    )
    params.update(kw)
    if grant is _MISSING:
        params["grant"] = issue(
            gate, scope=params["scope"], writer=params["writer"], host=params["host"],
        )
    else:
        params["grant"] = grant
    return gate.activate(**params)


def workkey(**overrides):
    data = dict(
        workkey_id="wk-1", goal="phase A gate", expected_effect="n1-n23 fail closed",
        priority="p0", owner_role="HUMAN_OWNER", current_writer=WRITER, reviewer=VERIFIER,
        repo="happyhippovip/2026-courier", base_sha="abc123", head_sha="def456",
        host="host-a", worktree="/tmp/wt",
        file_scope=["courier_runtime/grants.py", "courier_runtime/lease.py"],
        lease_id="lease-1", lease_expiry=2000.0, fence=1, human_grant_ref="g1",
        stop_and_spend_gates={"stop": "CLEAR", "spend_limit": 0}, dependencies=[],
        verified_tests={"exit": None, "time": None, "hash": ""}, known_blocker="",
        safe_next_action="run the phase A pytest", last_checkpoint_sha="chk1",
        resume_instruction="continue from checkpoint chk1", state_version=3,
        source_refs=["lease:t1708u"],
    )
    data.update(overrides)
    return data


@pytest.fixture
def opened(tmp_path):
    gate, clock, store = make_gate(tmp_path)
    yield gate, clock, store
    store.close()


def test_n1_coordinator_down_keeps_lease_until_ttl_and_blocks_new(opened):
    gate, clock, store = opened
    first = activate(gate, scope="scope-keep")
    assert first.status == ACTIVE
    expiry = store.current("scope-keep").expires_at
    gate.set_coordinator_reachable(False)
    assert store.current("scope-keep") is not None
    assert store.current("scope-keep").expires_at == expiry
    blocked = activate(gate, scope="scope-new")
    assert blocked.status == HOLD and "coordinator unreachable" in blocked.reason
    assert store.current("scope-new") is None
    spoof = activate(gate, scope="scope-spoof", owner_authorizes=True, requested_by=WRITER)
    assert spoof.status == REJECT and store.current("scope-spoof") is None
    owner = activate(gate, scope="scope-owner", owner_authorizes=True, requested_by=OWNER)
    assert owner.status == ACTIVE
    gate.register(
        REPL, ["ISSUE_PREAPPROVED_LEASE", "COORDINATE"], proof="external-proof",
        host="host-b", spend_limit=0, cost=0,
    )
    recorded = gate.preauthorize_replacement(
        requested_by=OWNER, principal_id=REPL, writer_principal=WRITER, writer_scopes=["scope-keep"],
    )
    assert recorded.status == RECORDED
    replaced = activate(gate, issuer=REPL, scope="scope-repl")
    assert replaced.status == ACTIVE
    clock.t = expiry
    assert store.current("scope-keep") is None


def test_n2_wrong_ack_identity_stays_pending(opened):
    gate, _, store = opened
    decision = activate(gate, ack_principal=PEER, scope="scope-n2")
    assert decision.status == PENDING
    assert decision.status != ACTIVE
    assert store.current("scope-n2") is None


def test_n3_two_writers_one_scope_second_rejected(tmp_path):
    gate, _, store = make_gate(tmp_path, name="n3.db")
    try:
        gate.register(
            "writer-2", ["WRITE_SCOPED_CODE"], proof="external-proof",
            host="host-a", spend_limit=0, cost=0,
        )
        first = activate(gate, scope="scope-n3")
        second = activate(gate, scope="scope-n3", writer="writer-2", ack_principal="writer-2")
        assert first.status == ACTIVE
        assert second.status == REJECT and "conflict" in second.reason
        assert store.current("scope-n3").holder == WRITER
    finally:
        store.close()


def test_n4_expired_lease_is_checkpoint_only(opened):
    gate, clock, store = opened
    decision = activate(gate, scope="scope-n4", ttl_s=30)
    lease = decision.evidence["lease"]
    clock.t = 1029
    assert store.access_mode("scope-n4", lease.token) == "WRITE"
    clock.t = 1030
    assert store.current("scope-n4") is None
    assert store.access_mode("scope-n4", lease.token) == "CHECKPOINT_RO"
    with pytest.raises(StaleLease):
        store.check_write("scope-n4", lease.token)
    refused = gate.write("scope-n4", lease.token)
    assert refused.status == HOLD and refused.evidence["mode"] == "CHECKPOINT_RO"


def test_n5_revoke_is_immediate_hold(opened):
    gate, _, store = opened
    decision = activate(gate, scope="scope-n5")
    lease = decision.evidence["lease"]
    with pytest.raises(StaleLease):
        store.revoke("scope-n5", lease.token + 1)
    assert store.current("scope-n5") is not None
    revoked = gate.revoke("scope-n5", lease.token, by_principal=OWNER)
    assert revoked.status == HOLD
    assert store.current("scope-n5") is None
    assert store.access_mode("scope-n5", lease.token) == "CHECKPOINT_RO"
    with pytest.raises(StaleLease):
        store.renew(lease, ttl_s=30)


def test_n6_unknown_spend_does_not_activate(opened):
    gate, _, store = opened
    decision = activate(gate, scope="scope-n6", spend_limit=None)
    assert decision.status == HOLD and "spend" in decision.reason
    assert decision.status != ACTIVE
    assert store.current("scope-n6") is None
    gate.register(WRITER, ["WRITE_SCOPED_CODE", "RESUME_WORKKEY"], proof="external-proof",
                  host="host-a", spend_limit=None, cost=0)
    decision = activate(gate, scope="scope-n6b", spend_limit=0)
    assert decision.status == HOLD and "spend" in decision.reason
    assert store.current("scope-n6b") is None


def test_n7_uncheckable_stop_holds_and_keeps_existing(opened):
    gate, _, store = opened
    kept = activate(gate, scope="scope-keep")
    assert kept.status == ACTIVE
    token = kept.evidence["lease"].token

    def github_down():
        raise ConnectionError("github down")

    gate.set_stop(github_down)
    fresh = activate(gate, scope="scope-new")
    assert fresh.status == HOLD and "stop not checkable" in fresh.reason
    assert store.current("scope-new") is None
    assert store.current("scope-keep") is not None
    assert store.check_write("scope-keep", token).holder == WRITER
    gate.set_stop("MAYBE")
    unknown = activate(gate, scope="scope-maybe")
    assert unknown.status == HOLD and store.current("scope-maybe") is None


def test_n8_writer_cannot_self_extend_or_self_approve(opened):
    gate, _, store = opened
    decision = activate(gate, scope="scope-n8")
    lease = decision.evidence["lease"]
    expiry = lease.expires_at
    for approver, verifier in ((WRITER, VERIFIER), (ISSUER, WRITER), (ISSUER, ISSUER)):
        refused = gate.extend(lease, 250, approver=approver, verifier=verifier)
        assert refused.status == REJECT
        assert store.current("scope-n8").expires_at == expiry
    with pytest.raises(LeaseConflict):
        store.renew(lease, 250)
    with pytest.raises(LeaseConflict):
        store.renew(lease, 250, approver=WRITER)
    with pytest.raises(LeaseConflict):
        store.renew(lease, 250, approver="stranger", verifier="other-stranger")
    assert store.current("scope-n8").expires_at == expiry
    extended = gate.extend(lease, 250, approver=ISSUER, verifier=VERIFIER)
    assert extended.status == RECORDED
    assert store.current("scope-n8").expires_at > expiry
    assert store.current("scope-n8").token == lease.token


def test_n9_replacement_inside_writer_scope_rejected(opened):
    gate, _, store = opened
    assert gate.preauthorize_replacement(
        requested_by=WRITER, principal_id=REPL, writer_principal=WRITER, writer_scopes=[SCOPE],
    ).status == REJECT
    assert gate.preauthorize_replacement(
        requested_by=OWNER, principal_id=WRITER, writer_principal=WRITER, writer_scopes=[SCOPE],
    ).status == REJECT
    assert WRITER not in gate.replacements
    gate.register(
        REPL, ["COORDINATE", "ISSUE_PREAPPROVED_LEASE"], proof="external-proof",
        host="host-b", spend_limit=0, cost=0,
    )
    assert gate.preauthorize_replacement(
        requested_by=OWNER, principal_id=REPL, writer_principal=WRITER, writer_scopes=[SCOPE],
    ).status == RECORDED
    inside = activate(gate, issuer=REPL, scope=SCOPE)
    assert inside.status == REJECT and "writer scope" in inside.reason
    assert store.current(SCOPE) is None
    outside = activate(gate, issuer=REPL, scope="scope-outside")
    assert outside.status == ACTIVE
    assert store.current("scope-outside").holder == WRITER


def test_n10_push_without_human_go_rejected(opened):
    gate, _, _ = opened
    activate(gate, scope="scope-n10")
    for effect in ("push", "merge"):
        decision = gate.authorize_side_effect(effect, human_go=False, lease_active=True)
        assert decision.status == REJECT and "human go" in decision.reason
    held = gate.authorize_side_effect("push", human_go=True, lease_active=True)
    assert held.status == PENDING and held.status != ACTIVE
    assert held.evidence["production_locked"] is True


def test_n11_resume_reads_workkey_without_old_provider(opened):
    gate, _, _ = opened
    previous_provider = "retired-provider-account"
    stored = gate.submit_workkey(workkey())
    parsed, _ = parse_workkey(workkey())
    assert package_sha_of(stored) == package_sha_of_package(parsed)
    decision = gate.resume("wk-1")
    view = decision.evidence["resume"]
    assert decision.status == CONTINUITY_OK
    assert view.resume_instruction == "continue from checkpoint chk1"
    assert view.last_checkpoint_sha == "chk1"
    assert view.base_sha == "abc123" and view.state_version == 3
    assert view.package_sha == stored.evidence["package_sha"]
    assert previous_provider not in inspect.signature(resume_from_package).parameters
    assert "chat" not in inspect.signature(resume_from_package).parameters
    assert "provider" not in ResumeView.__dataclass_fields__
    assert inspect.signature(resume_from_package).parameters.keys() == {"package"}


def package_sha_of(decision):
    return decision.evidence["package_sha"]


def package_sha_of_package(package):
    from courier_runtime.grants import package_sha
    return package_sha(package)


def test_n12_unknown_writer_rejected(opened):
    gate, _, store = opened
    decision = activate(gate, writer="ghost", ack_principal="ghost", scope="scope-n12")
    assert decision.status == REJECT and "unknown writer" in decision.reason
    assert store.current("scope-n12") is None


def test_n13_provider_switch_without_auth_match_is_not_a_write(opened):
    gate, _, _ = opened
    _verify_package(gate, "wk-13")
    attestation = gate.register(
        "other", ["WRITE_SCOPED_CODE"], proof="external-proof", host="host-b", spend_limit=0, cost=0,
    )
    assert attestation.accepted is False
    readonly = gate.write_as("wk-13", "other")
    named = gate.write_as("wk-13", "grok")
    assert readonly.status == "RO" and named.status == "RO"
    assert readonly.status != ACTIVE and named.status != ACTIVE
    gate.submit_workkey(workkey(workkey_id="wk-13b"))
    unverified = gate.write_as("wk-13b", "other")
    assert unverified.status == HOLD and unverified.status != ACTIVE


def _verify_package(gate, workkey_id):
    assert gate.submit_workkey(workkey(workkey_id=workkey_id)).status == "CANDIDATE"
    assert gate.mark_ready(workkey_id).status == "READY"
    claimed = gate.claim(workkey_id, live_base_sha="abc123", live_state_version=3)
    assert claimed.status == "CLAIMED"
    assert gate.transition(workkey_id, "IN_PROGRESS").status == "IN_PROGRESS"
    assert gate.transition(workkey_id, "VERIFYING").status == "VERIFYING"
    assert gate.verify_independent(workkey_id, verifier=VERIFIER).status == "VERIFIED"


def test_n14_name_without_capability_cannot_coordinate_or_issue(opened):
    gate, _, _ = opened
    gate.register("label-only", [], proof="external-proof", host="host-a", spend_limit=0, cost=0)
    assert gate.authorize_role("label-only", "COORDINATE").status == REJECT
    assert gate.authorize_role("label-only", "ISSUE_PREAPPROVED_LEASE").status == REJECT
    assert gate.authorize_role("label-only", "grok").status == REJECT
    with pytest.raises(ValueError):
        gate.register("brand", ["grok"], proof="external-proof")
    chosen, _ = gate.rank_candidates("grok", target_host="host-a")
    assert chosen == ()


def test_n15_cross_host_is_blocked_not_a_global_lock(tmp_path):
    mac = LeaseStore(str(tmp_path / "mac.db"), clock=Clock())
    win = LeaseStore(str(tmp_path / "win.db"), clock=Clock())
    local_a = LeaseStore(str(tmp_path / "local.db"), clock=Clock())
    local_b = LeaseStore(str(tmp_path / "local.db"), clock=Clock())
    try:
        split = assess_cross_host(
            mac, win, "files:same", "writer-mac", "writer-win", "wk-15", 100,
            principal_a="writer-mac", principal_b="writer-win", host_a="mac", host_b="win",
        )
        assert split.status == "BLOCKED" and split.code == "NEED_SCOPE"
        assert split.concurrent_holders is True and split.same_store is False
        assert mac.current("files:same").holder == "writer-mac"
        assert win.current("files:same").holder == "writer-win"
        assert "not a global lock" in split.does_not_guarantee
        assert "compare-and-swap" in split.minimal_extra_scope
        assert CROSS_HOST_PROOF == "BLOCKED"
        assert CROSS_HOST_EXTRA_SCOPE == split.minimal_extra_scope
        local = assess_cross_host(
            local_a, local_b, "files:same", "holder-a", "holder-b", "wk-local", 100,
        )
        assert local.same_store is True and local.local_conflict is True
        assert local.code == "LEASE_CONFLICT" and local.concurrent_holders is False
        assert local.status != ACTIVE
        assert "not a global lock" in local.does_not_guarantee
    finally:
        mac.close()
        win.close()
        local_a.close()
        local_b.close()


def test_n16_stale_checkpoint_is_not_proven_and_not_claimed(opened):
    gate, _, _ = opened
    assert gate.submit_workkey(workkey(workkey_id="wk-fresh")).status == "CANDIDATE"
    assert gate.mark_ready("wk-fresh").status == "READY"
    fresh = gate.claim("wk-fresh", live_base_sha="abc123", live_state_version=3)
    assert fresh.status == "CLAIMED"
    assert gate.submit_workkey(workkey(workkey_id="wk-sha")).status == "CANDIDATE"
    assert gate.mark_ready("wk-sha").status == "READY"
    stale_sha = gate.claim("wk-sha", live_base_sha="older", live_state_version=3)
    assert stale_sha.status == "NOT_PROVEN"
    assert gate.workkeys["wk-sha"].state == "READY"
    assert gate.submit_workkey(workkey(workkey_id="wk-ver")).status == "CANDIDATE"
    assert gate.mark_ready("wk-ver").status == "READY"
    stale_ver = gate.claim("wk-ver", live_base_sha="abc123", live_state_version=2)
    assert stale_ver.status == "NOT_PROVEN"
    assert gate.workkeys["wk-ver"].state == "READY"


def test_n17_missing_capability_is_skipped_deterministically(tmp_path):
    accepted = {"c-same", "m-same", "b-far", "a-costly", "no-cap", "spend-unknown"}
    gate, _, store = make_gate(tmp_path, accepted=accepted, name="n17.db")
    try:
        gate.registry._rows.clear()
        specs = [
            ("spend-unknown", ["COORDINATE"], "mac", None, 0),
            ("no-cap", [], "mac", 0, 0),
            ("a-costly", ["COORDINATE"], "mac", 9, 5),
            ("b-far", ["COORDINATE"], "win", 0, 0),
            ("m-same", ["COORDINATE"], "mac", 0, 0),
            ("c-same", ["COORDINATE"], "mac", 0, 0),
        ]
        for pid, caps, host, spend, cost in reversed(specs):
            gate.register(pid, caps, proof="external-proof", host=host, spend_limit=spend, cost=cost)
        chosen, skipped = gate.rank_candidates("COORDINATE", target_host="mac")
        assert chosen == ("c-same", "m-same", "b-far", "a-costly")
        assert "no-cap" in skipped and "spend-unknown" in skipped
        again, _ = gate.rank_candidates("COORDINATE", target_host="mac")
        assert again == chosen
    finally:
        store.close()


def test_n18_flow_through_stops_after_one_ready_check(opened):
    gate, _, _ = opened
    assert gate.submit_workkey(workkey(workkey_id="wk-18")).status == "CANDIDATE"
    assert gate.flow_through("wk-18").status == HOLD
    assert gate.flow_checks.get("wk-18", 0) == 0
    assert gate.mark_ready("wk-18").status == "READY"
    first = gate.flow_through("wk-18")
    second = gate.flow_through("wk-18")
    assert first.status == CHECKED and first.evidence["checks"] == 1
    assert second.status == HOLD and "exactly one" in second.reason
    assert gate.flow_checks["wk-18"] == 1
    assert gate.workkeys["wk-18"].state == "READY"
    assert second.status != ACTIVE


def test_n19_global_stop_blocks_ready_workkey(opened):
    gate, _, _ = opened
    assert gate.submit_workkey(workkey(workkey_id="wk-19")).status == "CANDIDATE"
    assert gate.mark_ready("wk-19").status == "READY"
    gate.set_stop("STOP")
    decision = gate.start("wk-19")
    assert decision.status == HOLD and "STOP" in decision.reason
    assert gate.workkeys["wk-19"].state == "READY"
    assert decision.status != ACTIVE


def test_n20_no_independent_verifier_emits_owner_card(opened):
    gate, _, store = opened
    gate.auth_verifier = verifier_for(PROVEN | {"clerk"})
    gate.register("clerk", ["RESUME_WORKKEY"], proof="external-proof", host="host-a", spend_limit=0, cost=0)
    decision = activate(gate, verifier="clerk", scope="scope-n20", workkey="wk-20")
    assert decision.status == HOLD and "verifier" in decision.reason
    card = decision.evidence["card"]
    assert card["type"] == "DENNIS_RESUME_CARD"
    assert card["does_not_grant"] == ACTIVE
    assert card["missing_gate"] == "independent verifier"
    assert card["owner_principal"] == OWNER
    assert store.current("scope-n20") is None


def test_n21_ready_without_spend_limit_fails_closed(opened):
    gate, _, _ = opened
    gates = {"stop": "CLEAR"}
    assert "spend_limit" not in gates
    stored = gate.submit_workkey(workkey(workkey_id="wk-21", stop_and_spend_gates=gates))
    assert stored.status == "CANDIDATE"
    decision = gate.mark_ready("wk-21")
    assert decision.status == HOLD and "spend" in decision.reason
    assert gate.workkeys["wk-21"].state == "CANDIDATE"


def test_n22_delegated_is_not_done(opened):
    gate, _, _ = opened
    gate.submit_workkey(workkey(workkey_id="wk-22"))
    assert equate_status("DELEGATED", "DONE").status == REJECT
    assert equate_status("DONE", "DELEGATED").status == REJECT
    assert equate_status("LEASE_ACTIVE", "AGENT_RUNNING").status == REJECT
    assert gate.transition("wk-22", "DONE").status == REJECT
    assert gate.workkeys["wk-22"].state == "CANDIDATE"


def test_n23_local_pass_is_not_ci_pass():
    assert equate_status("LOCAL_PASS", "CI_PASS").status == REJECT
    assert equate_status("CI_PASS", "LOCAL_PASS").status == REJECT


def test_missing_grant_holds(opened):
    gate, _, store = opened
    decision = activate(gate, grant=None, scope="scope-miss")
    assert decision.status == HOLD and "missing grant" in decision.reason
    assert store.current("scope-miss") is None


def test_host_workkey_and_principal_fence(opened):
    gate, _, store = opened
    grant = issue(gate, scope="scope-fence", writer=WRITER, host="host-a", grant_id="g-fence")
    decision = activate(gate, scope="scope-fence", grant=grant)
    lease = decision.evidence["lease"]
    other_host = issue(gate, scope="scope-fence", writer=WRITER, host="host-b", grant_id="g-fence-b")
    refused_host = activate(gate, scope="scope-fence", host="host-b", grant=other_host)
    refused_key = activate(gate, scope="scope-fence", workkey="wk-other", grant=grant)
    assert refused_host.status == REJECT and "host" in refused_host.reason
    assert refused_key.status == REJECT and "workkey" in refused_key.reason
    with pytest.raises(StaleLease):
        store.check_write("scope-fence", lease.token, host="host-b")
    with pytest.raises(StaleLease):
        store.check_write("scope-fence", lease.token, workkey="wk-other")
    with pytest.raises(StaleLease):
        store.check_write("scope-fence", lease.token, principal="not-the-writer")
    with pytest.raises(LeaseConflict):
        store.acquire("scope-fence", WRITER, "wk-other", 30, principal=WRITER, host="host-a")
    allowed = gate.write("scope-fence", lease.token, host="host-a", workkey="wk-1", principal=WRITER)
    assert allowed.status == "FENCED" and allowed.evidence["mode"] == "WRITE"


def test_auth_proof_partial_refuses_unverified_blob(tmp_path):
    clock = Clock()
    store = LeaseStore(str(tmp_path / "auth.db"), clock=clock)
    gate = Gate(Broker(clock), store, clock, owner_principal=OWNER, auth_verifier=None, stop_status="CLEAR")
    try:
        blob = {"alg": "ed25519", "sig": "aa"}
        attestation = gate.register(
            WRITER, ["WRITE_SCOPED_CODE"], proof=blob, host="host-a", spend_limit=0, cost=0,
        )
        gate.register(ISSUER, ["ISSUE_PREAPPROVED_LEASE"], proof=blob, host="host-a", spend_limit=0, cost=0)
        gate.register(VERIFIER, ["VERIFY_LEASE"], proof=blob, host="host-a", spend_limit=0, cost=0)
        assert attestation.accepted is False
        assert AUTH_PROOF_STATUS == "PARTIAL"
        assert "AuthAttestation" in AUTH_PROOF_EXTRA_SCOPE
        decision = activate(gate, scope="scope-auth")
        assert decision.status == HOLD and "auth" in decision.reason
        assert store.current("scope-auth") is None
    finally:
        store.close()


def test_g1_caller_built_grant_is_not_active(opened):
    gate, _, store = opened
    scope = "scope-g1"
    forged = Grant(
        grant_id="forged", project="courier", capability="WRITE_SCOPED_CODE",
        resources=frozenset({scope}), host="host-a", provider_account="", data_class="project",
        access="write", effect_class="idempotent", expires_at=None, granted_by="nobody",
        bound_principal=WRITER, scope_key=scope, content_hash="",
    )
    decision = activate(gate, grant=forged, scope=scope)
    assert decision.status == HOLD and "not in the broker" in decision.reason
    assert decision.status != ACTIVE
    assert store.current(scope) is None
    real = issue(gate, scope=scope, grant_id="g-real")
    widened = replace(real, access="control", resources=frozenset({scope, "extra"}))
    decision = activate(gate, grant=widened, scope=scope)
    assert decision.status == ACTIVE
    stored = gate.broker.grants["g-real"]
    assert stored.resources == real.resources and stored.access == "write"
    assert "extra" not in stored.resources


def test_g2_revoked_grant_reference_is_not_active(opened):
    gate, _, store = opened
    grant = issue(gate, scope="scope-g2", grant_id="g-revoke")
    assert grant.state == "GRANTED"
    gate.broker.revoke(grant.grant_id)
    assert grant.state == "GRANTED"
    assert gate.broker.grants[grant.grant_id].state == "REVOKED"
    decision = activate(gate, grant=grant, scope="scope-g2")
    assert decision.status == HOLD and "REVOKED" in decision.reason
    assert decision.status != ACTIVE
    assert store.current("scope-g2") is None


def test_g3_once_grant_is_consumed_on_activate(opened):
    gate, _, store = opened
    request = gate.activation_request(writer=WRITER, scope="scope-g3", host="host-a", request_id="g-once")
    gate.broker.authorize(request)
    grant = gate.broker.grant(
        request, "g-once", expires_at=10_000, once=True, granted_by=OWNER, owner_principal=OWNER,
    )
    first = activate(gate, grant=grant, scope="scope-g3")
    assert first.status == ACTIVE
    assert gate.broker.grants["g-once"].uses == 1
    second = activate(gate, grant=grant, scope="scope-g3")
    assert second.status == HOLD and "used" in second.reason
    assert second.status != ACTIVE
    assert store.current("scope-g3").holder == WRITER


def test_g4_writer_without_write_capability_is_not_active(opened):
    gate, _, store = opened
    decision = activate(gate, writer=PEER, ack_principal=PEER, scope="scope-g4")
    assert decision.status == REJECT and "WRITE_SCOPED_CODE" in decision.reason
    assert decision.status != ACTIVE
    assert store.current("scope-g4") is None


def test_g5_recomputed_or_empty_hash_is_not_active(opened):
    gate, _, store = opened
    grant = issue(gate, scope="scope-g5", grant_id="g-seal")
    widened = replace(grant, expires_at=None, content_hash="")
    widened = replace(widened, content_hash=grant_content_hash(widened))
    gate.broker.grants[grant.grant_id] = widened
    decision = activate(gate, grant=widened, scope="scope-g5")
    assert decision.status == HOLD and "seal" in decision.reason
    assert store.current("scope-g5") is None
    gate.broker.grants[grant.grant_id] = replace(grant, content_hash="")
    decision = activate(gate, grant=grant, scope="scope-g5")
    assert decision.status == HOLD and decision.status != ACTIVE
    assert store.current("scope-g5") is None


def test_g6_renew_rejects_arbitrary_approver(opened):
    gate, _, store = opened
    decision = activate(gate, scope="scope-g6")
    lease = decision.evidence["lease"]
    expiry = store.current("scope-g6").expires_at
    with pytest.raises(LeaseConflict):
        store.renew(lease, 50, approver="not-a-principal", verifier="also-not")
    with pytest.raises(LeaseConflict):
        store.renew(lease, 50, approver=ISSUER)
    assert store.current("scope-g6").expires_at == expiry
    renewed = store.renew(lease, 250, approver=ISSUER, verifier=VERIFIER)
    assert renewed.expires_at > expiry and renewed.token == lease.token


def test_r1_unknown_spend_blocks_extend_and_principal_bound_renew(opened):
    gate, _, store = opened
    decision = activate(gate, scope="scope-r1")
    lease = decision.evidence["lease"]
    expiry = store.current("scope-r1").expires_at
    gate.register(
        WRITER, ["WRITE_SCOPED_CODE", "RESUME_WORKKEY"], proof="external-proof",
        host="host-a", spend_limit=None, cost=0,
    )
    held = gate.extend(lease, 250, approver=ISSUER, verifier=VERIFIER)
    assert held.status == HOLD and "spend" in held.reason
    assert held.status != ACTIVE
    with pytest.raises(LeaseConflict):
        store.renew(lease, 250, approver=ISSUER, verifier=VERIFIER)
    assert store.current("scope-r1").expires_at == expiry


def test_r4_stop_blocks_extend_and_principal_bound_renew(opened):
    gate, _, store = opened
    decision = activate(gate, scope="scope-r4")
    lease = decision.evidence["lease"]
    expiry = store.current("scope-r4").expires_at
    for status in ("STOP", "HOLD"):
        gate.set_stop(status)
        held = gate.extend(lease, 250, approver=ISSUER, verifier=VERIFIER)
        assert held.status == HOLD and status in held.reason
        assert held.status != ACTIVE
        with pytest.raises(LeaseConflict):
            store.renew(lease, 250, approver=ISSUER, verifier=VERIFIER)
        assert store.current("scope-r4").expires_at == expiry
    gate.set_stop(lambda: (_ for _ in ()).throw(ConnectionError("stop unreachable")))
    unreachable = gate.extend(lease, 250, approver=ISSUER, verifier=VERIFIER)
    assert unreachable.status == HOLD and "not checkable" in unreachable.reason
    with pytest.raises(LeaseConflict):
        store.renew(lease, 250, approver=ISSUER, verifier=VERIFIER)
    assert store.current("scope-r4").expires_at == expiry
    gate.set_stop("CLEAR")
    extended = gate.extend(lease, 250, approver=ISSUER, verifier=VERIFIER)
    assert extended.status == RECORDED
    assert store.current("scope-r4").expires_at > expiry


def test_authority_roles_do_not_hardcode_provider_names():
    root = Path(__file__).resolve().parents[1]
    source = (root / "courier_runtime" / "grants.py").read_text(encoding="utf-8")
    source += (root / "courier_runtime" / "lease.py").read_text(encoding="utf-8")
    lowered = source.lower()
    for brand in ("grok", "antigravity", "codex", "claude", "muse"):
        assert brand not in lowered
