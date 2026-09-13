const assert = require('assert');
const fs = require('fs');
const path = require('path');
const { CourierRuntime } = require('../bin/courier_runtime');
const { TaskPassport } = require('../supervisor/index');

console.log('=== TEST SUITE: COURIER RUNTIME REAL WORKER DISPATCH ===');

const testSandbox = path.resolve(__dirname, '..', 'scratch', 'test_real_dispatch');
if (fs.existsSync(testSandbox)) {
  fs.rmSync(testSandbox, { recursive: true, force: true });
}
fs.mkdirSync(testSandbox, { recursive: true });

const runtime = new CourierRuntime({
  allowedRoot: testSandbox,
  stateDir: path.join(testSandbox, '.courier_state')
});

const passport = TaskPassport.createPassport({
  task_id: 'TEST-TASK-001',
  goal_id: 'GOAL-TEST-REAL',
  scope_paths: [testSandbox],
  max_capability: 'WORKSPACE_WRITE'
});

// Test 1: Real command execution capturing stdout
console.log('\n[TEST 1] Executing real command with stdout capture...');
const task1 = {
  task_id: 'TASK-REAL-001',
  goal_id: 'GOAL-TEST-REAL',
  worker_id: 'WORKER-LOCAL-DETERMINISTIC',
  target_file: 'sample.txt',
  executable_command: 'node -e "console.log(\'COURIER_EXECUTION_VERIFIED_BIT_FOR_BIT\');"',
  working_dir: testSandbox,
  scope_paths: [testSandbox.toLowerCase().replace(/\\/g, '/')]
};

const res1 = runtime.executeLocalWorker(task1, passport);
assert.strictEqual(res1.exit_code, 0, 'Exit code must be 0');
assert.strictEqual(res1.worker_claimed_status, 'WORK_UNIT_COMPLETE');
assert.strictEqual(res1.artifacts.length, 1);
assert.ok(fs.existsSync(res1.artifacts[0]), 'Evidence artifact must exist on disk');

const evidenceData = JSON.parse(fs.readFileSync(res1.artifacts[0], 'utf8'));
assert.ok(evidenceData.stdout.includes('COURIER_EXECUTION_VERIFIED_BIT_FOR_BIT'), 'Stdout must contain expected verification text');
assert.strictEqual(evidenceData.exit_code, 0);
console.log('  [PASS] Real command execution and evidence verification passed.');

// Test 2: Failing command handling (fail-closed)
console.log('\n[TEST 2] Testing non-zero exit command handling...');
const task2 = {
  task_id: 'TASK-REAL-002-FAIL',
  goal_id: 'GOAL-TEST-REAL',
  worker_id: 'WORKER-LOCAL-DETERMINISTIC',
  executable_command: 'node -e "process.exit(42);"',
  working_dir: testSandbox,
  scope_paths: [testSandbox.toLowerCase().replace(/\\/g, '/')]
};

const res2 = runtime.executeLocalWorker(task2, passport);
assert.strictEqual(res2.exit_code, 42, 'Exit code must capture 42');
assert.strictEqual(res2.worker_claimed_status, 'WORK_UNIT_FAILED');
const failEvidence = JSON.parse(fs.readFileSync(res2.artifacts[0], 'utf8'));
assert.strictEqual(failEvidence.result_status, 'FAILED');
console.log('  [PASS] Failing command handled cleanly with exit code 42.');

// Clean up
fs.rmSync(testSandbox, { recursive: true, force: true });
console.log('\n=======================================================');
console.log('ALL COURIER REAL DISPATCH TESTS PASSED (100% GREEN)');
console.log('=======================================================');
