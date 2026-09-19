import test from 'node:test';
import assert from 'node:assert/strict';
import {triage, nextReady} from './triage.mjs';

// Synthetic night: 50 results with fixed seed pattern (deterministic, no RNG).
function night50() {
  const out = [];
  const push = (id, outcome, cause, need, repeat) => out.push({id, outcome, cause, need, repeat});
  for (let i = 0; i < 28; i++) push(`done-${i}`, 'DONE');
  for (let i = 0; i < 6; i++) push(`ok2-${i}`, 'DONE');
  for (let i = 0; i < 4; i++) push(`fail-${i}`, 'FAILED', 'exit-3', null, i > 1);
  push('auth-0', 'BLOCKED', 'auth-expired', 'AUTH_REQUIRED');
  push('pay-0', 'BLOCKED', 'quota-empty', 'PAYMENT_REQUIRED');
  push('gate-0', 'HUMAN_GATE', 'delete-archive', 'HUMAN_DECISION');
  push('gate-1', 'HUMAN_GATE', 'delete-archive', 'HUMAN_DECISION');
  push('unk-0', 'UNKNOWN_OUTCOME', 'timeout-ambiguous', 'UNKNOWN_EFFECT');
  push('sec-0', 'BLOCKED', 'secret-request', 'SECURITY');
  for (let i = 0; i < 3; i++) push(`reuse-${i}`, 'REUSED');
  push('rev-0', 'NEEDS_REVIEW');
  push('rev-1', 'NEEDS_REVIEW');
  push('rev-2', 'NEEDS_REVIEW');
  assert.equal(out.length, 50);
  return out;
}

test('K14: 50 results group compactly with one alert per cause', () => {
  const t = triage(night50());
  assert.equal(t.groups.DONE.length, 34);
  assert.deepEqual(t.groups.HUMAN_GATE, ['gate-0', 'gate-1']);
  assert.ok(t.rootCauseGroups.includes('delete-archive'));
  // 2 same-cause gates -> 1; 4 same-cause fails -> 3; 3 causeless reviews -> 2
  assert.equal(t.duplicateAlertsSuppressed, 1 + 3 + 2);
  const order = t.needsHuman.map(n => n.cause);
  assert.deepEqual(order.slice(0, 4), ['auth-expired', 'quota-empty', 'secret-request', 'timeout-ambiguous']);
});

test('K14: needs-human priority AUTH first, causeless review last', () => {
  const t = triage(night50());
  const ranks = t.needsHuman.map(n => n.rank);
  assert.deepEqual(ranks, [...ranks].sort((a, b) => a - b));
  assert.equal(t.needsHuman[0].cause, 'auth-expired');
  assert.equal(t.needsHuman[t.needsHuman.length - 1].cause, 'unknown-cause');
});

test('K14: next READY work lists only admitted candidates', () => {
  assert.deepEqual(nextReady([{id: 'a', verdict: 'READY_CANDIDATE'}, {id: 'b', verdict: 'WAIT_DEPENDENCY'}]), ['a']);
});
