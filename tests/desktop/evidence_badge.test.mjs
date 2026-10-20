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
  const item = {
    journal_entry_id: 'j-1001',
    task_id: 'task-a',
    attempt: 1,
    dispatch_id: 'disp-01',
    accepted_result_id: 'res-99',
    artifact_sha256: 'a1b2c3d4e5f60718293a4b5c6d7e8f90a1b2c3d4e5f60718293a4b5c6d7e8f90',
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
    journal_entry_id: 'j-1001',
    task_id: 'task-a',
    attempt: 1,
    dispatch_id: 'disp-01',
    accepted_result_id: 'res-99',
    artifact_sha256: 'a1b2c3d4e5f60718293a4b5c6d7e8f90a1b2c3d4e5f60718293a4b5c6d7e8f90',
  };
  const html = renderEvidenceBadge(item);
  assert.ok(html.includes('class="evidence-badge"'));
  assert.ok(html.includes('data-state="VERIFIED"'));
  assert.ok(html.includes('BYTE_LEVEL_GOLD_VERIFIED'));
  assert.ok(html.includes('aria-label='));
});
