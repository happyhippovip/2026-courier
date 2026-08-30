import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import {
  resolveCorrelationTruth,
  resolveDecisionTruth,
  resolveExecutionTruth,
} from '../studio/execution_truth.js';

// Missing machine evidence must never inherit a class from an agent identity.
assert.equal(resolveExecutionTruth({ id: 'agent-codex-bridge', state: 'RUNNING' }), 'UNKNOWN');

assert.equal(
  resolveExecutionTruth({ execution_class: 'REAL_CODEX_CLI' }),
  'REAL_CODEX_CLI',
);
assert.equal(
  resolveExecutionTruth({ execution_class: 'DETERMINISTIC_ANTIGRAVITY' }),
  'DETERMINISTIC_ANTIGRAVITY',
);
assert.equal(resolveExecutionTruth({ execution_class: 'FALLBACK' }), 'FALLBACK');
assert.equal(resolveExecutionTruth({ execution_class: 'SIMULATED_VISUAL' }), 'SIMULATED_VISUAL');
assert.equal(resolveExecutionTruth({ execution_class: 'untrusted-label' }), 'UNKNOWN');

// The display layer must not turn no decision into an approval.
assert.equal(resolveDecisionTruth({}), 'NO_DECISION');
assert.equal(resolveDecisionTruth({ last_decision: 'REJECTED' }), 'REJECTED');

// A missing correlation remains absent; it is never generated in the browser.
assert.equal(resolveCorrelationTruth({}), null);
assert.equal(resolveCorrelationTruth({ correlation_id: 'UNKNOWN' }), null);
assert.equal(resolveCorrelationTruth({ correlation_id: 'corr-from-courier-001' }), 'corr-from-courier-001');

const studioSource = readFileSync(new URL('../studio/studio.js', import.meta.url), 'utf8');
assert.doesNotMatch(studioSource, /corr-live-|crypto\.randomUUID|Math\.random\(/);
assert.doesNotMatch(studioSource, /last_decision\s*\|\|\s*['\"]ACCEPTED['\"]/);

console.log('execution truth tests: PASS');
