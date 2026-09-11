const assert = require('assert');
const { ZeroPromptExecutor } = require('../lib/zero_prompt_executor');

const executor = new ZeroPromptExecutor({
  maxTimeoutMs: 1000,
  allowedScope: ['C:/Users/lol/2026-workspace/courier/opportunity_warehouse']
});

console.log('--- TEST 1: Unattended Task Execution ---');
const task1 = executor.executeTask({
  taskId: 'TASK-UNATTENDED-001',
  targetPath: 'C:/Users/lol/2026-workspace/courier/opportunity_warehouse/research/test.md',
  action: () => ({ verified: true, count: 42 })
});

assert.strictEqual(task1.status, 'COMPLETED_UNATTENDED');
assert.strictEqual(task1.result.count, 42);
console.log('PASS [Test 1]: Task executes cleanly unattended within budget.');

console.log('--- TEST 2: Out-of-Scope Boundary Violation Fail-Closed ---');
assert.throws(() => {
  executor.executeTask({
    taskId: 'TASK-OUT-OF-SCOPE',
    targetPath: 'C:/Users/lol/2026-workspace/courier/money_factory/first_eur5_fast_path/RELEASE_CANDIDATE_V1/file.js',
    action: () => 'forbidden write'
  });
}, /outside authorized scope/, 'Out of scope path must throw');
console.log('PASS [Test 2]: Unauthorized scope access rejected fail-closed.');

console.log('--- TEST 3: Action Error Propagation ---');
assert.throws(() => {
  executor.executeTask({
    taskId: 'TASK-FAILS',
    action: () => { throw new Error('Simulated internal failure'); }
  });
}, /Simulated internal failure/, 'Internal error must propagate');
console.log('PASS [Test 3]: Action errors fail closed deterministically.');

console.log('\n>>> ALL 3 ZERO-PROMPT EXECUTOR TESTS PASS (100% DETERMINISTIC) <<<');
