import test from 'node:test';
import assert from 'node:assert/strict';

import {
  EVIDENCE_STATES,
  REQUIRED_TUPLE,
  evaluateEvidence,
  renderEvidenceBadge,
  escapeHtml
} from '../../courier_hub/static/evidence_badge.mjs';

test('evaluateEvidence: complete 6-tuple resolves to BYTE_LEVEL_GOLD_VERIFIED', () => {
  // V151: the green path now also needs the contract resolution and the journal proof.
  const item = {
    journal_entry_id: 'journal:7:RESULT_ACCEPTED',
    task_id: 'task-a',
    attempt: 1,
    dispatch_id: 'disp-01',
    accepted_result_id: 'res-99',
    artifact_sha256: 'a1b2c3d4e5f60718293a4b5c6d7e8f90a1b2c3d4e5f60718293a4b5c6d7e8f90',
    resolution: 'BYTE_LEVEL_GOLD_VERIFIED',
    proof: { event: 'RESULT_ACCEPTED', seq: 7, result_id: 'res-99' },
  };
  const res = evaluateEvidence(item);
  assert.equal(res.state, EVIDENCE_STATES.VERIFIED);
  assert.equal(res.resolution, 'BYTE_LEVEL_GOLD_VERIFIED');
  assert.equal(res.valid, true);
});

test('evaluateEvidence: rejects synthetic event IDs', () => {
  const item = {
    event_id: 'evt:unknown:0',
    journal_entry_id: 'j-1001',
    task_id: 'task-a',
    attempt: 1,
    dispatch_id: 'disp-01',
    accepted_result_id: 'res-99',
    artifact_sha256: 'a1b2c3d4e5f60718293a4b5c6d7e8f90a1b2c3d4e5f60718293a4b5c6d7e8f90',
  };
  const res = evaluateEvidence(item);
  assert.equal(res.state, EVIDENCE_STATES.UNKNOWN);
  assert.equal(res.resolution, 'SYNTHETIC_ID_REJECTED');
  assert.equal(res.valid, false);
});

test('evaluateEvidence: active block maps to BLOCKED', () => {
  const item = {
    blocker: 'HUMAN_APPROVAL_PENDING',
    journal_entry_id: 'j-1001',
    task_id: 'task-a',
  };
  const res = evaluateEvidence(item);
  assert.equal(res.state, EVIDENCE_STATES.BLOCKED);
  assert.equal(res.resolution, 'ACTIVE_BLOCK');
});

test('evaluateEvidence: unconfirmed claim maps to REPORTED', () => {
  const item = {
    state: 'CLAIMED',
    task_id: 'task-b',
  };
  const res = evaluateEvidence(item);
  assert.equal(res.state, EVIDENCE_STATES.REPORTED);
  assert.equal(res.resolution, 'UNCONFIRMED_CLAIM');
});

test('evaluateEvidence: missing or contradictory maps to UNKNOWN', () => {
  assert.equal(evaluateEvidence(null).state, EVIDENCE_STATES.UNKNOWN);
  assert.equal(evaluateEvidence({}).state, EVIDENCE_STATES.UNKNOWN);
  assert.equal(evaluateEvidence({ journal_entry_id: 'j-1' }).state, EVIDENCE_STATES.UNKNOWN);
});

test('renderEvidenceBadge: produces accessible HTML with escaped attributes', () => {
  const item = {
    journal_entry_id: 'journal:7:RESULT_ACCEPTED',
    task_id: 'task-a',
    attempt: 1,
    dispatch_id: 'disp-01',
    accepted_result_id: 'res-99',
    artifact_sha256: 'a1b2c3d4e5f60718293a4b5c6d7e8f90a1b2c3d4e5f60718293a4b5c6d7e8f90',
    resolution: 'BYTE_LEVEL_GOLD_VERIFIED',
    proof: { event: 'RESULT_ACCEPTED', seq: 7, result_id: 'res-99' },
  };
  const html = renderEvidenceBadge(item);
  assert.ok(html.includes('class="evidence-badge"'));
  assert.ok(html.includes('data-state="VERIFIED"'));
  assert.ok(html.includes('BYTE_LEVEL_GOLD_VERIFIED'));
  assert.ok(html.includes('aria-label='));
});

// V151 fail-closed contract: only the contract resolution plus a journal-bound proof is ever green.
const TUPLE = Object.freeze({
  journal_entry_id: 'journal:7:RESULT_ACCEPTED',
  task_id: 'task-a',
  attempt: 1,
  dispatch_id: 'disp-01',
  accepted_result_id: 'res-99',
  artifact_sha256: 'a1b2c3d4e5f60718293a4b5c6d7e8f90a1b2c3d4e5f60718293a4b5c6d7e8f90',
});
const PROOF = Object.freeze({ event: 'RESULT_ACCEPTED', seq: 7, result_id: 'res-99' });
const GOLD = Object.freeze({ ...TUPLE, resolution: 'BYTE_LEVEL_GOLD_VERIFIED', proof: PROOF });

test('V151: complete tuple without a resolution is UNKNOWN, never VERIFIED', () => {
  const res = evaluateEvidence({ ...TUPLE, proof: PROOF });
  assert.equal(res.state, EVIDENCE_STATES.UNKNOWN);
  assert.equal(res.resolution, 'RESOLUTION_MISSING');
  assert.equal(res.valid, false);
});

test('V151: rejected resolution is UNKNOWN, never VERIFIED', () => {
  for (const resolution of ['rejected', 'REJECTED', { value: 'REJECTED' }]) {
    const res = evaluateEvidence({ ...GOLD, resolution });
    assert.equal(res.state, EVIDENCE_STATES.UNKNOWN);
    assert.equal(res.resolution, 'RESOLUTION_REJECTED');
    assert.equal(res.valid, false);
  }
  assert.equal(evaluateEvidence({ ...GOLD, resolution: 'REJECTED', state: 'REPORTED' }).state, EVIDENCE_STATES.UNKNOWN);
});

test('V151: BLOCKED without a documented reason is UNKNOWN, not BLOCKED', () => {
  for (const item of [
    { ...TUPLE, status: 'BLOCKED' },
    { ...GOLD, state: 'blocked' },
    { ...TUPLE, state: { value: 'BLOCKED' } },
    { ...TUPLE, status: 'BLOCKED', blocker: '   ' },
    { ...TUPLE, status: 'BLOCKED', blocker: {} },
  ]) {
    const res = evaluateEvidence(item);
    assert.equal(res.state, EVIDENCE_STATES.UNKNOWN);
    assert.equal(res.resolution, 'BLOCKED_WITHOUT_REASON');
    assert.equal(res.valid, false);
  }
});

test('V151: generic or human resolutions are not translated into VERIFIED', () => {
  for (const resolution of ['verified', 'VERIFIED', 'byte_level_gold_verified', 'effect_confirmed', 'accepted', true, 1]) {
    const res = evaluateEvidence({ ...GOLD, resolution });
    assert.equal(res.state, EVIDENCE_STATES.UNKNOWN, String(resolution));
    assert.ok(['RESOLUTION_NOT_VERIFIED', 'RESOLUTION_MISSING'].includes(res.resolution), String(resolution));
    assert.equal(res.valid, false);
  }
});

test('V151: agreeing but unproven data is never green', () => {
  const unproven = [
    { ...GOLD, proof: undefined },
    { ...GOLD, proof: { ...PROOF, event: 'RESULT_REPORTED' } },
    { ...GOLD, proof: { ...PROOF, seq: 0 } },
    { ...GOLD, proof: { ...PROOF, seq: '7' } },
    { ...GOLD, proof: { ...PROOF, result_id: 'res-other' } },
    { ...GOLD, journal_entry_id: 'j-1001' },
    { ...GOLD, proof: { ...PROOF, seq: 8 } },
    { ...GOLD, proof: 'journal:7:RESULT_ACCEPTED' },
  ];
  for (const item of unproven) {
    const res = evaluateEvidence(item);
    assert.equal(res.state, EVIDENCE_STATES.UNKNOWN);
    assert.equal(res.resolution, 'JOURNAL_PROOF_MISSING');
    assert.equal(res.valid, false);
  }
});

test('V151: evidence bound to another task is UNKNOWN', () => {
  const res = evaluateEvidence({ task_id: 'task-other', evidence: { ...GOLD } });
  assert.equal(res.state, EVIDENCE_STATES.UNKNOWN);
  assert.equal(res.resolution, 'CONTRADICTORY_BINDING');
  assert.deepEqual(res.details.conflicts, ['task_id']);
});

test('V151: a cleared or foreign blocker never takes precedence', () => {
  for (const blocker of [
    { value: 'LEASE_LOST', active: false },
    { value: 'LEASE_LOST', resolved_at: '2026-10-21T00:00:00Z' },
    { value: 'LEASE_LOST', cleared_at: '2026-10-21T00:00:00Z' },
    { value: 'LEASE_LOST', resolved: true },
  ]) {
    const res = evaluateEvidence({ ...GOLD, blocker });
    assert.equal(res.state, EVIDENCE_STATES.VERIFIED, JSON.stringify(blocker));
  }
  const cleared = evaluateEvidence({ ...TUPLE, status: 'BLOCKED', blocker: { value: 'X', active: false } });
  assert.equal(cleared.resolution, 'BLOCKED_WITHOUT_REASON');
  const foreign = evaluateEvidence({ ...GOLD, blocker: { value: 'LEASE_LOST', task_id: 'task-other' } });
  assert.equal(foreign.state, EVIDENCE_STATES.UNKNOWN);
  assert.equal(foreign.resolution, 'BLOCKER_NOT_BOUND');
});

test('V151 control: contract resolution with journal proof is VERIFIED', () => {
  for (const item of [
    { ...GOLD },
    { task_id: 'task-a', evidence: { ...GOLD } },
    { evidence: { ...TUPLE }, resolution: 'BYTE_LEVEL_GOLD_VERIFIED', proof: PROOF },
  ]) {
    const res = evaluateEvidence(item);
    assert.equal(res.state, EVIDENCE_STATES.VERIFIED);
    assert.equal(res.resolution, 'BYTE_LEVEL_GOLD_VERIFIED');
    assert.equal(res.valid, true);
  }
});

test('V151 control: bad hash with proof stays UNKNOWN', () => {
  assert.equal(evaluateEvidence({ ...GOLD, artifact_sha256: 'xyz' }).state, EVIDENCE_STATES.UNKNOWN);
});

test('V151 control: current, task-bound blocker stays BLOCKED', () => {
  for (const item of [
    { status: 'BLOCKED', blocker: 'HUMAN_APPROVAL_PENDING' },
    { task_id: 'task-a', blocker: { value: 'effect_uncertain', task_id: 'task-a', active: true } },
    { ...GOLD, blocker: 'LEASE_LOST' },
  ]) {
    const res = evaluateEvidence(item);
    assert.equal(res.state, EVIDENCE_STATES.BLOCKED);
    assert.equal(res.resolution, 'ACTIVE_BLOCK');
  }
});

test('V151 control: badge colours use the Kolibri neon tokens', () => {
  assert.ok(renderEvidenceBadge({ ...GOLD }).includes('background-color:var(--neon-green, #10b981)'));
  assert.ok(renderEvidenceBadge({ state: 'CLAIMED', task_id: 't' }).includes('var(--neon-blue, #3b82f6)'));
  assert.ok(renderEvidenceBadge({ blocker: 'X' }).includes('var(--neon-red, #ef4444)'));
  const gray = renderEvidenceBadge({ ...TUPLE });
  assert.ok(gray.includes('data-state="UNKNOWN"'));
  assert.ok(gray.includes('var(--neon-gray, #6b7280)'));
});
