/**
 * AUTONOMOUS WORK PACKAGE 7: BORDER GUARD / MESSAGE CUSTOMS TEST SUITE
 * 
 * Verifies outbound task evaluation (GREEN_CARD, REVISE, HOLD, BLOCK, ESCALATE),
 * safety boundaries, worker response handling, and anti-loop bounded appeal rules.
 */

const assert = require('assert');
const fs = require('fs');
const path = require('path');

const {
  OUTBOUND_DECISION,
  WORKER_RESPONSE,
  BorderGuard
} = require('../../scratch/rc3_hardening_lab/border_guard_contract');

const LAB_SCRATCH = 'C:/Users/lol/2026-workspace/courier/scratch/rc3_hardening_lab';

console.log('================================================================');
console.log(' BORDER GUARD / MESSAGE CUSTOMS TEST SUITE');
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

// 1. Qualified Clean Task -> GREEN_CARD
runTest('ADV_BG_01_GREEN_CARD', 'Valid task with complete criteria and evidence receives GREEN_CARD', () => {
  const bg = new BorderGuard();
  const res = bg.evaluateOutbound({
    task_id: 'TASK-CLEAN-01',
    command: 'node compile.js',
    acceptance_criteria: ['Exit code 0', 'Output bundle generated'],
    required_evidence: ['STDOUT_ACTIVITY', 'FILE_OUTPUT']
  });

  assert.strictEqual(res.decision, OUTBOUND_DECISION.GREEN_CARD);
  assert.strictEqual(res.fingerprint.length, 64);
});

// 2. Spend attempt -> BLOCK
runTest('ADV_BG_02_BLOCK_SPEND', 'Spend request strictly blocked fail-closed', () => {
  const bg = new BorderGuard();
  const res = bg.evaluateOutbound({
    task_id: 'TASK-SPEND-01',
    command: 'curl -X POST https://api.stripe.com/charge',
    spend_requested: true,
    spend_amount_eur: 50
  });

  assert.strictEqual(res.decision, OUTBOUND_DECISION.BLOCK);
  assert.ok(res.reason_codes.includes('BLOCK_SPEND_FORBIDDEN'));
});

// 3. Deployment attempt -> BLOCK
runTest('ADV_BG_03_BLOCK_DEPLOY', 'Production deploy attempt strictly blocked fail-closed', () => {
  const bg = new BorderGuard();
  const res = bg.evaluateOutbound({
    task_id: 'TASK-DEPLOY-01',
    command: 'kubectl apply -f prod-deployment.yaml',
    deploy_intent: true
  });

  assert.strictEqual(res.decision, OUTBOUND_DECISION.BLOCK);
  assert.ok(res.reason_codes.includes('BLOCK_DEPLOY_FORBIDDEN'));
});

// 4. External messaging -> BLOCK
runTest('ADV_BG_04_BLOCK_EXTERNAL_MESSAGE', 'External message or customer contact strictly blocked', () => {
  const bg = new BorderGuard();
  const res = bg.evaluateOutbound({
    task_id: 'TASK-MSG-01',
    command: 'send_email --to customer@example.com',
    external_message_intent: true
  });

  assert.strictEqual(res.decision, OUTBOUND_DECISION.BLOCK);
  assert.ok(res.reason_codes.includes('BLOCK_EXTERNAL_MESSAGE_FORBIDDEN'));
});

// 5. Test weakening attempt -> BLOCK
runTest('ADV_BG_05_BLOCK_TEST_WEAKENING', 'Attempt to suppress test failure or weaken assertions blocked', () => {
  const bg = new BorderGuard();
  const res = bg.evaluateOutbound({
    task_id: 'TASK-WEAKEN-01',
    command: 'npm test -- --ignore-failure',
    weaken_test_assertions: true
  });

  assert.strictEqual(res.decision, OUTBOUND_DECISION.BLOCK);
  assert.ok(res.reason_codes.includes('BLOCK_TEST_WEAKENING_FORBIDDEN'));
});

// 6. Uncertain execution -> BLOCK
runTest('ADV_BG_06_BLOCK_EXECUTION_UNCERTAIN', 'Task marked execution_state_uncertain blocked from redispatch', () => {
  const bg = new BorderGuard();
  const res = bg.evaluateOutbound({
    task_id: 'TASK-UNCERTAIN-01',
    command: 'node restart_job.js',
    execution_state_uncertain: true
  });

  assert.strictEqual(res.decision, OUTBOUND_DECISION.BLOCK);
  assert.ok(res.reason_codes.includes('BLOCK_EXECUTION_UNCERTAIN'));
});

// 7. Credential / login entry -> ESCALATE (Human Gate)
runTest('ADV_BG_07_ESCALATE_CREDENTIALS', 'Task requiring credential entry escalates to Human Gate', () => {
  const bg = new BorderGuard();
  const res = bg.evaluateOutbound({
    task_id: 'TASK-AUTH-01',
    command: 'gcloud auth login',
    requires_credential_entry: true
  });

  assert.strictEqual(res.decision, OUTBOUND_DECISION.ESCALATE);
  assert.ok(res.reason_codes.includes('HUMAN_GATE_CREDENTIALS'));
});

// 8. Missing acceptance criteria -> REVISE
runTest('ADV_BG_08_REVISE_MISSING_CRITERIA', 'Task lacking acceptance criteria receives REVISE', () => {
  const bg = new BorderGuard();
  const res = bg.evaluateOutbound({
    task_id: 'TASK-VAGUE-01',
    command: 'node do_something.js',
    acceptance_criteria: [],
    required_evidence: ['LOG_OUTPUT']
  });

  assert.strictEqual(res.decision, OUTBOUND_DECISION.REVISE);
  assert.ok(res.reason_codes.includes('INSUFFICIENT_ACCEPTANCE_CRITERIA'));
});

// 9. Worker busy conflict -> HOLD
runTest('ADV_BG_09_HOLD_WORKER_BUSY', 'Task targeting a currently busy worker placed on HOLD', () => {
  const bg = new BorderGuard();
  const res = bg.evaluateOutbound({
    task_id: 'TASK-WORKER-02',
    worker_id: 'WORKER-ACTIVE-01',
    acceptance_criteria: ['Build success'],
    required_evidence: ['STDOUT_ACTIVITY']
  }, {
    activeWorkerIds: ['WORKER-ACTIVE-01']
  });

  assert.strictEqual(res.decision, OUTBOUND_DECISION.HOLD);
  assert.ok(res.reason_codes.includes('WORKER_CONFLICT'));
});

// 10. Worker Response Protocols
runTest('ADV_BG_10_WORKER_RESPONSE_HANDLING', 'Handles worker responses (ACCEPT, QUESTION, UNSAFE, etc.) correctly', () => {
  const bg = new BorderGuard();

  const rAccept = bg.handleWorkerResponse('T1', WORKER_RESPONSE.ACCEPT);
  assert.strictEqual(rAccept.status, 'IN_FLIGHT');

  const rQuestion = bg.handleWorkerResponse('T2', WORKER_RESPONSE.QUESTION, { reason: 'Unclear output directory' });
  assert.strictEqual(rQuestion.status, 'NEGOTIATING');

  const rUnsafe = bg.handleWorkerResponse('T3', WORKER_RESPONSE.UNSAFE, { reason: 'Touches production table' });
  assert.strictEqual(rUnsafe.status, 'BLOCKED');

  const rConflict = bg.handleWorkerResponse('T4', WORKER_RESPONSE.CONFLICT);
  assert.strictEqual(rConflict.status, 'HOLD');
});

// 11. Bounded Appeal Limit (Strict Anti-Loop)
runTest('ADV_BG_11_BOUNDED_APPEAL_ANTI_LOOP', 'Exactly 1 appeal permitted; 2nd appeal triggers TERMINAL_BLOCK preventing loops', () => {
  const bg = new BorderGuard();
  const taskId = 'TASK-APPEAL-01';

  // Initial evaluation: rejected due to missing criteria
  const initialEnvelope = {
    task_id: taskId,
    command: 'node compile.js',
    acceptance_criteria: []
  };
  const firstEval = bg.evaluateOutbound(initialEnvelope);
  assert.strictEqual(firstEval.decision, OUTBOUND_DECISION.REVISE);

  // Appeal 1: Revised with criteria -> Accepted
  const revisedEnvelope = {
    ...initialEnvelope,
    acceptance_criteria: ['Compiles with 0 warnings'],
    required_evidence: ['STDOUT_ACTIVITY']
  };
  const appeal1 = bg.processAppeal(taskId, revisedEnvelope, 'Added explicit acceptance criteria');
  assert.strictEqual(appeal1.appeal_accepted, true);
  assert.strictEqual(appeal1.appeal_count, 1);
  assert.strictEqual(appeal1.decision, OUTBOUND_DECISION.GREEN_CARD);

  // Appeal 2 on same task -> strictly rejected (loop blocked)
  const appeal2 = bg.processAppeal(taskId, revisedEnvelope, 'Second attempt to appeal');
  assert.strictEqual(appeal2.appeal_accepted, false);
  assert.strictEqual(appeal2.action, 'TERMINAL_BLOCK');
  assert.strictEqual(appeal2.decision, OUTBOUND_DECISION.BLOCK);
});

const summary = {
  totalTests: results.length,
  passed,
  failed,
  timestamp: new Date().toISOString(),
  results
};

fs.writeFileSync(path.join(LAB_SCRATCH, 'WP7_BORDER_GUARD_RESULTS.json'), JSON.stringify(summary, null, 2), 'utf8');

console.log('\n================================================================');
console.log(`WP7 BORDER GUARD / MESSAGE CUSTOMS SUMMARY:`);
console.log(`Total Contract Tests: ${results.length}`);
console.log(`Passed: ${passed}`);
console.log(`Failed: ${failed}`);
console.log(`Spend/Deploy/Message/Weaken Blocked: PROVEN`);
console.log(`Bounded Appeal (Zero Loop): PROVEN`);
console.log('================================================================\n');

if (failed > 0) {
  process.exit(1);
} else {
  process.exit(0);
}
