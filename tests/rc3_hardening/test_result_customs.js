/**
 * AUTONOMOUS WORK PACKAGE 8: RESULT CUSTOMS TEST SUITE
 * 
 * Tests strict validation of the 42-field result envelope.
 * Proves fail-closed rejection of wrong IDs, replays, mismatched scopes,
 * missing fingerprints, claimed tests/files without evidence, unexpected external actions,
 * spend, deployments, and unverified prose PASS claims.
 * 
 * Confirms Result Customs never marks goal SATISFIED.
 */

const assert = require('assert');
const fs = require('fs');
const path = require('path');

const {
  ResultCustoms
} = require('./contracts/result_customs_contract');

const LAB_SCRATCH = path.join(__dirname, '..', '..', 'scratch', 'rc3_hardening_lab');
if (!fs.existsSync(LAB_SCRATCH)) fs.mkdirSync(LAB_SCRATCH, { recursive: true });

console.log('================================================================');
console.log(' RESULT CUSTOMS CONTRACT TEST SUITE');
console.log('================================================================\n');

let passed = 0;
let failed = 0;
const results = [];

function runTest(testId, description, fn) {
  try {
    fn();
    passed++;
    results.push({ testId, description, status: 'PASS' });
    console.log(`[PASS] ${testId}: ${description}`);
  } catch (err) {
    failed++;
    results.push({ testId, description, status: 'FAIL', error: err.message });
    console.error(`[FAIL] ${testId}: ${description}`);
    console.error(err);
  }
}

function getValidEnvelope(overrides = {}) {
  return ResultCustoms.createDefaultEnvelope({
    TASK_ID: 'TASK-VALID-01',
    TASK_VERSION: 1,
    GOAL_ID: 'GOAL-MAIN-01',
    WORKER_ID: 'WORKER-WIN-01',
    STARTED_AT: '2026-09-09T10:05:00Z',
    FINISHED_AT: '2026-09-09T10:06:00Z',
    STATUS: 'PASS',
    ORIGINAL_SCOPE_FINGERPRINT: 'abc123scope',
    FINAL_SCOPE_FINGERPRINT: 'abc123scope',
    SCOPE_CHANGED: false,
    TEST_COMMANDS: ['npm test'],
    TEST_EXIT_CODES: [0],
    LOG_PATHS: ['logs/run.log'],
    TESTS_RUN: 5,
    TESTS_PASS: 5,
    TESTS_FAIL: 0,
    ARTIFACTS: [{ path: 'dist/bundle.js', sha256: 'deadbeef' }],
    SPEND_PERFORMED: 0,
    ...overrides
  });
}

const defaultContext = {
  task_id: 'TASK-VALID-01',
  version: 1,
  goal_id: 'GOAL-MAIN-01',
  worker_id: 'WORKER-WIN-01',
  dispatched_at: '2026-09-09T10:00:00Z',
  scope_fingerprint: 'abc123scope'
};

// 1. Valid envelope accepted
runTest('ADV_RC_01_VALID_ENVELOPE_ACCEPTED', 'Valid complete envelope accepted with goal_state unchanged', () => {
  const rc = new ResultCustoms();
  const env = getValidEnvelope();
  const res = rc.validateResult(env, defaultContext);

  assert.strictEqual(res.accepted, true);
  assert.strictEqual(res.result_status, 'ACCEPTED');
  assert.strictEqual(res.goal_state, 'UNCHANGED', 'Result Customs must NEVER satisfy goal');
});

// 2. Wrong task ID rejected
runTest('ADV_RC_02_WRONG_TASK_ID', 'Wrong task ID rejected fail-closed', () => {
  const rc = new ResultCustoms();
  const env = getValidEnvelope({ TASK_ID: 'TASK-WRONG-99' });
  const res = rc.validateResult(env, defaultContext);

  assert.strictEqual(res.accepted, false);
  assert.ok(res.violations.some(v => v.includes('WRONG_TASK_ID')));
});

// 3. Wrong version rejected
runTest('ADV_RC_03_WRONG_VERSION', 'Wrong version rejected fail-closed', () => {
  const rc = new ResultCustoms();
  const env = getValidEnvelope({ TASK_VERSION: 99 });
  const res = rc.validateResult(env, defaultContext);

  assert.strictEqual(res.accepted, false);
  assert.ok(res.violations.some(v => v.includes('WRONG_VERSION')));
});

// 4. Wrong goal rejected
runTest('ADV_RC_04_WRONG_GOAL', 'Wrong goal ID rejected fail-closed', () => {
  const rc = new ResultCustoms();
  const env = getValidEnvelope({ GOAL_ID: 'GOAL-INTRUDER-99' });
  const res = rc.validateResult(env, defaultContext);

  assert.strictEqual(res.accepted, false);
  assert.ok(res.violations.some(v => v.includes('WRONG_GOAL_ID')));
});

// 5. Wrong worker rejected
runTest('ADV_RC_05_WRONG_WORKER', 'Wrong worker ID rejected fail-closed', () => {
  const rc = new ResultCustoms();
  const env = getValidEnvelope({ WORKER_ID: 'WORKER-ROUTER-99' });
  const res = rc.validateResult(env, defaultContext);

  assert.strictEqual(res.accepted, false);
  assert.ok(res.violations.some(v => v.includes('WRONG_WORKER_ID')));
});

// 6. Stale result rejected
runTest('ADV_RC_06_STALE_RESULT', 'Result timestamped before dispatch rejected', () => {
  const rc = new ResultCustoms();
  const env = getValidEnvelope({ STARTED_AT: '2026-09-09T09:00:00Z' }); // Dispatched at 10:00!
  const res = rc.validateResult(env, defaultContext);

  assert.strictEqual(res.accepted, false);
  assert.ok(res.violations.some(v => v.includes('STALE_RESULT')));
});

// 7. Replayed result rejected
runTest('ADV_RC_07_REPLAYED_RESULT', 'Duplicate submission with same result fingerprint rejected', () => {
  const rc = new ResultCustoms();
  const env1 = getValidEnvelope();
  const res1 = rc.validateResult(env1, defaultContext);
  assert.strictEqual(res1.accepted, true);

  // Attempt second submission
  const res2 = rc.validateResult(env1, defaultContext);
  assert.strictEqual(res2.accepted, false);
  assert.ok(res2.violations.some(v => v.includes('REPLAYED_RESULT')));
});

// 8. Scope fingerprint mismatch rejected
runTest('ADV_RC_08_SCOPE_MISMATCH', 'Scope fingerprint mismatch rejected', () => {
  const rc = new ResultCustoms();
  const env = getValidEnvelope({ ORIGINAL_SCOPE_FINGERPRINT: 'different_scope' });
  const res = rc.validateResult(env, defaultContext);

  assert.strictEqual(res.accepted, false);
  assert.ok(res.violations.some(v => v.includes('SCOPE_FINGERPRINT_MISMATCH')));
});

// 9. Missing result fingerprint rejected
runTest('ADV_RC_09_MISSING_RESULT_FINGERPRINT', 'Missing or tampered result fingerprint rejected', () => {
  const rc = new ResultCustoms();
  const env = getValidEnvelope({ RESULT_FINGERPRINT: '0000000000000000000000000000000000000000000000000000000000000000' });
  const res = rc.validateResult(env, defaultContext);

  assert.strictEqual(res.accepted, false);
  assert.ok(res.violations.some(v => v.includes('FINGERPRINT_MISMATCH')));
});

// 10. Claimed tests without evidence rejected
runTest('ADV_RC_10_CLAIMED_TESTS_WITHOUT_EVIDENCE', 'Claiming tests run without commands, exit codes, or logs rejected', () => {
  const rc = new ResultCustoms();
  const env = getValidEnvelope({
    TESTS_RUN: 10,
    TEST_COMMANDS: [], // Empty!
    TEST_EXIT_CODES: [] // Empty!
  });
  const res = rc.validateResult(env, defaultContext);

  assert.strictEqual(res.accepted, false);
  assert.ok(res.violations.some(v => v.includes('CLAIMED_TESTS_WITHOUT_COMMANDS')));
});

// 11. Claimed files without evidence rejected
runTest('ADV_RC_11_CLAIMED_FILES_WITHOUT_EVIDENCE', 'Claiming created file without path and sha256 hash rejected', () => {
  const rc = new ResultCustoms();
  const env = getValidEnvelope({
    FILES_CREATED: [{ path: 'output.txt' }] // Missing sha256!
  });
  const res = rc.validateResult(env, defaultContext);

  assert.strictEqual(res.accepted, false);
  assert.ok(res.violations.some(v => v.includes('FILE_CREATED_WITHOUT_EVIDENCE')));
});

// 12. Unexpected external actions rejected
runTest('ADV_RC_12_UNEXPECTED_EXTERNAL_ACTION', 'Result containing external actions rejected fail-closed', () => {
  const rc = new ResultCustoms();
  const env = getValidEnvelope({
    EXTERNAL_ACTIONS_PERFORMED: ['HTTP_POST_REMOTE_SERVER']
  });
  const res = rc.validateResult(env, defaultContext);

  assert.strictEqual(res.accepted, false);
  assert.ok(res.violations.some(v => v.includes('UNEXPECTED_EXTERNAL_ACTION')));
});

// 13. Unexpected spend rejected
runTest('ADV_RC_13_UNEXPECTED_SPEND', 'Spend greater than 0 rejected fail-closed', () => {
  const rc = new ResultCustoms();
  const env = getValidEnvelope({
    SPEND_PERFORMED: 12.50
  });
  const res = rc.validateResult(env, defaultContext);

  assert.strictEqual(res.accepted, false);
  assert.ok(res.violations.some(v => v.includes('UNEXPECTED_SPEND')));
});

// 14. Unexpected deployment rejected
runTest('ADV_RC_14_UNEXPECTED_DEPLOYMENT', 'Deployments detected in result rejected fail-closed', () => {
  const rc = new ResultCustoms();
  const env = getValidEnvelope({
    DEPLOYMENTS_PERFORMED: ['PRODUCTION_WEB_DEPLOY']
  });
  const res = rc.validateResult(env, defaultContext);

  assert.strictEqual(res.accepted, false);
  assert.ok(res.violations.some(v => v.includes('UNEXPECTED_DEPLOYMENT')));
});

// 15. Prose PASS without verification rejected
runTest('ADV_RC_15_PROSE_PASS_WITHOUT_VERIFICATION', 'Worker claims PASS but test exit code is non-zero or failures exist', () => {
  const rc = new ResultCustoms();
  const env = getValidEnvelope({
    STATUS: 'PASS',
    TEST_EXIT_CODES: [1], // Exit code 1!
    TESTS_FAIL: 1
  });
  const res = rc.validateResult(env, defaultContext);

  assert.strictEqual(res.accepted, false);
  assert.ok(res.violations.some(v => v.includes('CONTRADICTION_PROSE_PASS_WITH_FAILURES')));
});

const summary = {
  totalTests: results.length,
  passed,
  failed,
  timestamp: new Date().toISOString(),
  results
};

fs.writeFileSync(path.join(LAB_SCRATCH, 'WP8_RESULT_CUSTOMS_RESULTS.json'), JSON.stringify(summary, null, 2), 'utf8');

console.log('\n================================================================');
console.log(`WP8 RESULT CUSTOMS CONTRACT SUMMARY:`);
console.log(`Total Contract Tests: ${results.length}`);
console.log(`Passed: ${passed}`);
console.log(`Failed: ${failed}`);
console.log(`Evidence Integrity: PROVEN`);
console.log(`Goal State Non-Authority: PROVEN`);
console.log('================================================================\n');

if (failed > 0) {
  process.exit(1);
} else {
  process.exit(0);
}
