// The badge against the exact item shape courier_hub/kolibri_data.read_ledger emits for a
// journal-proven completion (captured from a real controller run, see
// tests/hub/test_kolibri_evidence_anchor.py). Green only for that bound tuple.
import { test } from "node:test";
import assert from "node:assert/strict";
import { EVIDENCE_STATES, evaluateEvidence } from "../../courier_hub/static/evidence_badge.mjs";

const ITEM = Object.freeze({"id": "task-baa28665b16f41169c2b6799a46557f1", "title": "Synthetic test task", "pile": "done", "source": "courier journal (courier.db)", "at": "2026-10-21T16:07:40.085226Z", "verified": true, "event_id": "journal:6:RESULT_ACCEPTED", "evidence": {"journal_entry_id": "journal:6:RESULT_ACCEPTED", "task_id": "task-baa28665b16f41169c2b6799a46557f1", "dispatch_id": "dsp-e09a4aed7e234d49a74f7ec1283c74fa", "accepted_result_id": "r1", "attempt": 1, "artifact_sha256": "511cfcf227e13ab2e1e91abacb93048ff7455a308ed1a6b0217ddf8f74396d3e", "resolution": "BYTE_LEVEL_GOLD_VERIFIED", "proof": {"event": "RESULT_ACCEPTED", "seq": 6, "result_id": "r1"}}});

test("anchor: a read_ledger item with the hub evidence tuple is VERIFIED", () => {
  const res = evaluateEvidence(ITEM);
  assert.equal(res.state, EVIDENCE_STATES.VERIFIED);
  assert.equal(res.resolution, "BYTE_LEVEL_GOLD_VERIFIED");
});

test("anchor: the same item without the hub tuple stays UNKNOWN", () => {
  const { evidence, ...bare } = ITEM;
  assert.equal(evaluateEvidence(bare).state, EVIDENCE_STATES.UNKNOWN);
});

test("anchor: a tampered tuple never turns green", () => {
  const ev = ITEM.evidence;
  for (const evidence of [
    { ...ev, proof: { ...ev.proof, seq: ev.proof.seq + 1 } },
    { ...ev, accepted_result_id: "r-other" },
    { ...ev, resolution: "verified" },
    { ...ev, artifact_sha256: "abc" },
  ]) {
    assert.notEqual(evaluateEvidence({ ...ITEM, evidence }).state, EVIDENCE_STATES.VERIFIED);
  }
});
