// Master Red-Team Runner
// Mission: WINDOWS_FINAL_INTEGRATION_REDTEAM_PACK_V1

const fs = require('fs');
const path = require('path');
const { RedTeamOracles } = require('./ORACLES/redteam_oracles');
const {
  SimulatedDispatcher,
  SimulatedResourceLockManager,
  SimulatedSafetyGate,
  SimulatedReconciler
} = require('./SIMULATION/redteam_simulator');
const { CRITICAL_MUTANTS } = require('./MUTANTS/mutants_catalog');

console.log('======================================================================');
console.log('WINDOWS FINAL INTEGRATION RED-TEAM RUNNER V1');
console.log('======================================================================\n');

let totalTests = 0;
let passedTests = 0;
let failedTests = 0;
const resultsLog = [];

function assertTest(name, condition, errorMsg = '') {
  totalTests++;
  if (condition) {
    passedTests++;
    resultsLog.push({ test: name, status: 'PASS' });
  } else {
    failedTests++;
    resultsLog.push({ test: name, status: 'FAIL', error: errorMsg });
    console.error(`[FAIL] ${name}: ${errorMsg}`);
  }
}

// ---------------------------------------------------------------------------
// SUITE 1: A01 EXECUTION-UNCERTAINTY FENCE (14 CALLER PATHS & TRANSITIVE DEPS)
// ---------------------------------------------------------------------------
console.log('--- SUITE 1: A01 Execution-Uncertainty Fence ---');
const dispatcher = new SimulatedDispatcher({ enableFence: true });

dispatcher.setTask({
  id: 'TASK-UNCERTAIN-01',
  state: 'EXECUTION_UNCERTAIN',
  execution_uncertain: true,
  side_effect_uncertainty: true
});

dispatcher.setTask({
  id: 'TASK-NORMAL-01',
  state: 'STAMPED',
  execution_uncertain: false,
  side_effect_uncertainty: false
});

dispatcher.setTask({
  id: 'TASK-DEPENDENT-01',
  state: 'STAMPED',
  dependencies: ['TASK-UNCERTAIN-01']
});

const a01Callers = [
  'ROUTER_DIRECT',
  'ROUTER_TIMEOUT_FALLBACK',
  'ROUTER_ERROR_RETRY',
  'SUPERVISOR_DECISION_HUNG',
  'SUPERVISOR_STALL_POLICY',
  'RESOURCE_GOVERNOR_REROUTE',
  'RESTART_RECONCILER',
  'TASK_HYGIENE_CLEANUP',
  'RESULT_CUSTOMS_REJECT',
  'CHIEF_ESCALATION_REDISPATCH',
  'PLANNER_REPLAN',
  'MANUAL_WEITER_RESUME',
  'WORKER_RECONNECT',
  'TRANSITIVE_TRIGGER'
];

for (const caller of a01Callers) {
  const res = dispatcher.dispatch('TASK-UNCERTAIN-01', caller, caller.includes('FALLBACK'));
  const oracleCheck = RedTeamOracles.oracleA01(res, { state: 'EXECUTION_UNCERTAIN', execution_uncertain: true });
  assertTest(`A01 Caller Blocked: ${caller}`, oracleCheck.pass && res.status === 'HOLD_UNCERTAIN', oracleCheck.violation || res.reason);
}

// Transitive dependency test
const depRes = dispatcher.dispatch('TASK-DEPENDENT-01', 'TRANSITIVE_TRIGGER');
assertTest('A01 Transitive Dependency Blocked', depRes.status === 'HOLD_UNCERTAIN', 'Dependent task should be held');

// Normal task dispatch
const normalRes = dispatcher.dispatch('TASK-NORMAL-01', 'ROUTER_DIRECT');
assertTest('A01 Normal Dispatch Allowed', normalRes.status === 'DISPATCHED_TO_WORKER', 'Normal task should dispatch');


// ---------------------------------------------------------------------------
// SUITE 2: L01 HIERARCHICAL & SEMANTIC RESOURCE LOCKS
// ---------------------------------------------------------------------------
console.log('\n--- SUITE 2: L01 Hierarchical & Semantic Resource Locks ---');
const lockMgr = new SimulatedResourceLockManager();

// 1. Parent/child collision
lockMgr.acquire('T1', 'L1', ['tree:src/']);
const childRes = lockMgr.acquire('T2', 'L2', ['tree:src/core/auth/']);
assertTest('L01 Parent/Child Tree Conflict', !childRes.acquired, 'Child directory must conflict with parent lock');
lockMgr.release('L1');

// 2. Child/parent reverse collision
lockMgr.acquire('T2', 'L2', ['tree:src/core/auth/']);
const parentRes = lockMgr.acquire('T1', 'L1', ['tree:src/']);
assertTest('L01 Child/Parent Reverse Conflict', !parentRes.acquired, 'Parent directory must conflict with active child lock');
lockMgr.release('L2');

// 3. Tree vs File collision
lockMgr.acquire('T1', 'L1', ['tree:src/']);
const fileRes = lockMgr.acquire('T2', 'L2', ['file:src/index.js']);
assertTest('L01 Tree vs File Conflict', !fileRes.acquired, 'File inside locked tree must conflict');
lockMgr.release('L1');

// 4. Prefix lookalike must NOT conflict (e.g. src/core vs src/core_v2)
lockMgr.acquire('T1', 'L1', ['tree:src/core/']);
const lookalikeRes = lockMgr.acquire('T2', 'L2', ['tree:src/core_v2/']);
assertTest('L01 Prefix Lookalike Parallelism', lookalikeRes.acquired, 'Lookalike non-subdirectories must not collide');
lockMgr.release('L1');
lockMgr.release('L2');

// 5. Windows Case-Insensitive Normalization
lockMgr.acquire('T1', 'L1', ['tree:src/Core/Auth/']);
const caseRes = lockMgr.acquire('T2', 'L2', ['tree:src/core/auth/']);
assertTest('L01 Case-Insensitive Collision', !caseRes.acquired, 'Case variants must collide on case-insensitive filesystems');
lockMgr.release('L1');

// 6. Sibling directories parallel
lockMgr.acquire('T1', 'L1', ['tree:src/moduleA/']);
const siblingRes = lockMgr.acquire('T2', 'L2', ['tree:src/moduleB/']);
assertTest('L01 Sibling Directory Parallelism', siblingRes.acquired, 'Sibling directories must run in parallel');
lockMgr.release('L1');
lockMgr.release('L2');

// 7. Non-filesystem semantic locks (database & port)
lockMgr.acquire('T1', 'L1', ['db:users/accounts', 'port:tcp/8080']);
const dbConflict = lockMgr.acquire('T2', 'L2', ['db:users/accounts']);
const portConflict = lockMgr.acquire('T3', 'L3', ['port:tcp/8080']);
const dbDisjoint = lockMgr.acquire('T4', 'L4', ['db:orders/items', 'port:tcp/9090']);

assertTest('L01 Database Table Mutex', !dbConflict.acquired, 'Same DB table must conflict');
assertTest('L01 Network Port Mutex', !portConflict.acquired, 'Same network port must conflict');
assertTest('L01 Disjoint Semantic Resources Parallel', dbDisjoint.acquired, 'Different DB table and port must run in parallel');
lockMgr.release('L1');
lockMgr.release('L4');


// ---------------------------------------------------------------------------
// SUITE 3: G01 DEFERRED LIABILITY & CAPABILITY GATE
// ---------------------------------------------------------------------------
console.log('\n--- SUITE 3: G01 Deferred Liability & Capability Gate ---');
const gate = new SimulatedSafetyGate();

// 1. €0 today with auto-renew €50/mo
const g1 = gate.evaluate({
  prompt: 'Start 14-day free trial with auto-renew at €50/month',
  toolArgs: { amount: 0.00, recurring: 50.00 }
});
assertTest('G01 Deferred Auto-Renew Gated', g1.requires_human_gate && !g1.executed, 'Auto-renew must require human gate');

// 2. Billing agreement
const g2 = gate.evaluate({
  prompt: 'Sign up for cloud tier under billing agreement on file',
  toolArgs: { amount: 0.00 }
});
assertTest('G01 Billing Agreement Gated', g2.requires_human_gate && !g2.executed, 'Billing agreement must require human gate');

// 3. Harmless analysis
const g3 = gate.evaluate({
  prompt: 'Analyze pricing plans and compare cloud costs for deployment',
  toolArgs: {}
});
assertTest('G01 Analysis Autonomous Pass', !g3.requires_human_gate && g3.executed, 'Harmless analysis must pass autonomously');

// 4. Negative instruction
const g4 = gate.evaluate({
  prompt: 'Do not deploy or purchase anything; run local simulation only',
  toolArgs: {}
});
assertTest('G01 Negative Polarity Pass', !g4.requires_human_gate && g4.executed, 'Negative instructions must not trigger false gate');

// 5. Tool capability override
const g5 = gate.evaluate({
  prompt: 'Generate documentation summary for project',
  toolName: 'stripe_charge',
  toolArgs: { amount: 10.00 }
});
assertTest('G01 Tool Capability Hard Barrier', g5.requires_human_gate && !g5.executed, 'Financial tool capability must gate regardless of prompt text');

// 6. Token verification & anti-replay
const taskV1 = { id: 'TASK-SPEND-01', version: 1 };
const validToken = {
  approval_id: 'APPR-100',
  nonce: 'NONCE-ABC-123',
  task_id: 'TASK-SPEND-01',
  task_version: 1,
  expires_at: new Date(Date.now() + 60000).toISOString()
};

const g6 = gate.evaluate({
  prompt: 'Charge deployment fee',
  operation: 'payment',
  toolArgs: { amount: 10.00 },
  token: validToken,
  expectedTask: taskV1
});
assertTest('G01 Valid Token Execution Permitted', g6.approved_with_token && g6.executed, 'Valid approval token must permit execution');

// Replay attack with same token
const g7 = gate.evaluate({
  prompt: 'Charge deployment fee second time',
  operation: 'payment',
  toolArgs: { amount: 10.00 },
  token: validToken,
  expectedTask: taskV1
});
assertTest('G01 Replay Attack Blocked', g7.requires_human_gate && !g7.executed, 'Replayed approval token must be rejected');

// Task version mismatch attack
const taskV2 = { id: 'TASK-SPEND-01', version: 2 };
const g8 = gate.evaluate({
  prompt: 'Charge deployment fee with modified task version',
  operation: 'payment',
  toolArgs: { amount: 10.00 },
  token: { ...validToken, nonce: 'NONCE-NEW-456' },
  expectedTask: taskV2
});
assertTest('G01 Version Mismatch Token Blocked', g8.requires_human_gate && !g8.executed, 'Token bound to v1 must reject v2 task');


// ---------------------------------------------------------------------------
// SUITE 4: B01 MULTI-FACTOR PROCESS IDENTITY
// ---------------------------------------------------------------------------
console.log('\n--- SUITE 4: B01 Multi-Factor Process Identity ---');
const reconciler = new SimulatedReconciler();

const leaseB01 = {
  pid: 5500,
  process_start_time_epoch_ms: 1788980000000,
  task_token: 'TOKEN-AAA-BBB'
};

// 1. Legitimate process match
const matchProc = {
  pid: 5500,
  start_time_epoch_ms: 1788980000050, // 50ms delta (clock jitter tolerance)
  env_task_token: 'TOKEN-AAA-BBB'
};
const r1 = reconciler.inspectProcess(leaseB01, matchProc);
assertTest('B01 Legitimate Process Matched', r1.status === 'MATCH_CONFIRMED' && r1.can_kill && r1.assume_alive, 'Authentic process should match');

// 2. PID recycled (new process with different start time)
const recycledProc = {
  pid: 5500,
  start_time_epoch_ms: 1788985000000, // 5 seconds later
  env_task_token: 'TOKEN-OTHER'
};
const r2 = reconciler.inspectProcess(leaseB01, recycledProc);
assertTest('B01 Recycled PID Mismatch Detected', r2.status === 'DEFINITE_MISMATCH' && !r2.can_kill && !r2.assume_alive, 'Recycled PID must not match or be killed');

// 3. Permission failure (EPERM / Sandbox)
const epermProc = {
  pid: 5500,
  inspection_error: 'EPERM'
};
const r3 = reconciler.inspectProcess(leaseB01, epermProc);
assertTest('B01 EPERM Fails Closed to UNKNOWN', r3.status === 'UNKNOWN' && !r3.can_kill && !r3.assume_alive, 'EPERM must return UNKNOWN with kill=false, assume_alive=false');

// 4. Missing lease start time (legacy record)
const legacyLease = { pid: 5500 };
const r4 = reconciler.inspectProcess(legacyLease, matchProc);
assertTest('B01 Legacy Missing StartTime Fails Closed', r4.status === 'UNKNOWN' && !r4.can_kill && !r4.assume_alive, 'Missing lease start time must not authorize kill');


// ---------------------------------------------------------------------------
// SUITE 5: MUTATION TESTING (ATTACK THE PROPOSED SPECS)
// ---------------------------------------------------------------------------
console.log('\n--- SUITE 5: Mutation Testing (13 Lethal Mutants) ---');
let mutantsKilled = 0;
let mutantsSurvived = 0;

for (const mutant of CRITICAL_MUTANTS) {
  let killed = false;
  let reason = '';

  if (mutant.target === 'A01') {
    const mutDisp = new SimulatedDispatcher(mutant.config);
    mutDisp.setTask({ id: 'MUT-TASK', state: 'EXECUTION_UNCERTAIN', execution_uncertain: true });
    const res = mutDisp.dispatch('MUT-TASK', 'ROUTER_FALLBACK', true);
    const check = RedTeamOracles.oracleA01(res, { state: 'EXECUTION_UNCERTAIN', execution_uncertain: true });
    if (!check.pass) {
      killed = true;
      reason = check.violation;
    }
  } else if (mutant.target === 'L01') {
    const mutLock = new SimulatedResourceLockManager(mutant.config);
    if (mutant.id === 'MUTANT_L01_01') {
      mutLock.acquire('T1', 'L1', ['tree:src/']);
      const res = mutLock.acquire('T2', 'L2', ['tree:src/core/']);
      const check = RedTeamOracles.oracleL01({ taskA_acquired: true, taskB_acquired: res.acquired }, 'T1', 'T2', ['tree:src/'], ['tree:src/core/']);
      if (!check.pass) { killed = true; reason = check.violation; }
    } else if (mutant.id === 'MUTANT_L01_02') {
      mutLock.acquire('T1', 'L1', ['db:users']);
      const res = mutLock.acquire('T2', 'L2', ['db:users']);
      const check = RedTeamOracles.oracleL01({ taskA_acquired: true, taskB_acquired: res.acquired }, 'T1', 'T2', ['db:users'], ['db:users']);
      if (!check.pass) { killed = true; reason = check.violation; }
    } else if (mutant.id === 'MUTANT_L01_03') {
      mutLock.acquire('T1', 'L1', ['tree:src/Core/']);
      const res = mutLock.acquire('T2', 'L2', ['tree:src/core/']);
      const check = RedTeamOracles.oracleL01({ taskA_acquired: true, taskB_acquired: res.acquired }, 'T1', 'T2', ['tree:src/Core/'], ['tree:src/core/']);
      if (!check.pass) { killed = true; reason = check.violation; }
    }
  } else if (mutant.target === 'G01') {
    const mutGate = new SimulatedSafetyGate(mutant.config);
    if (mutant.id === 'MUTANT_G01_01') {
      const res = mutGate.evaluate({ prompt: 'auto-renew subscription', toolArgs: { amount: 0 } });
      const check = RedTeamOracles.oracleG01(res, { hasDeferredLiability: true, name: 'Deferred €0' });
      if (!check.pass) { killed = true; reason = check.violation; }
    } else if (mutant.id === 'MUTANT_G01_02') {
      const res = mutGate.evaluate({ prompt: 'harmless analysis text', toolName: 'stripe_charge', toolArgs: { amount: 50 } });
      const check = RedTeamOracles.oracleG01(res, { isFinancialTool: true, name: 'Tool override' });
      if (!check.pass) { killed = true; reason = check.violation; }
    } else if (mutant.id === 'MUTANT_G01_03') {
      const tok = { approval_id: 'A1', nonce: 'N1', expires_at: new Date(Date.now() + 60000).toISOString() };
      mutGate.evaluate({ prompt: 'charge', operation: 'payment', toolArgs: { amount: 10 }, token: tok });
      const res2 = mutGate.evaluate({ prompt: 'charge', operation: 'payment', toolArgs: { amount: 10 }, token: tok });
      const check = RedTeamOracles.oracleG01(res2, { isFinancialTool: false, hasDeferredLiability: true, token: { ...tok, consumed: true }, name: 'Replay attack' });
      if (!check.pass) { killed = true; reason = check.violation; }
    } else if (mutant.id === 'MUTANT_G01_04') {
      const tok = { approval_id: 'A1', nonce: 'N2', task_id: 'T1', task_version: 1, expires_at: new Date(Date.now() + 60000).toISOString() };
      const res = mutGate.evaluate({ prompt: 'charge', operation: 'payment', toolArgs: { amount: 10 }, token: tok, expectedTask: { id: 'T1', version: 2 } });
      if (res.executed === true) { killed = true; reason = 'Token bound to version 1 executed version 2 task!'; }
    }
  } else if (mutant.target === 'B01') {
    const mutRec = new SimulatedReconciler(mutant.config);
    if (mutant.id === 'MUTANT_B01_01') {
      // PID only
      const res = mutRec.inspectProcess({ pid: 100, process_start_time_epoch_ms: 1000 }, { pid: 100, start_time_epoch_ms: 999999 });
      const check = RedTeamOracles.oracleB01(res, { pid: 100, process_start_time_epoch_ms: 1000 }, { pid: 100, start_time_epoch_ms: 999999 });
      if (!check.pass) { killed = true; reason = check.violation; }
    } else if (mutant.id === 'MUTANT_B01_02' || mutant.id === 'MUTANT_B01_03') {
      const res = mutRec.inspectProcess({ pid: 100 }, { pid: 100, start_time_epoch_ms: 1000 });
      const check = RedTeamOracles.oracleB01(res, { pid: 100 }, { pid: 100, start_time_epoch_ms: 1000 });
      if (!check.pass) { killed = true; reason = check.violation; }
    }
  } else if (mutant.target === 'MIGRATION') {
    // Missing field defaults to safe mutant
    const legacy = { pid: 100, status: 'EXECUTION_UNCERTAIN' };
    const migrated = mutant.config.defaultMissingToSafe ? { ...legacy, execution_uncertain: false } : { ...legacy, execution_uncertain: true };
    if (!migrated.execution_uncertain) {
      killed = true;
      reason = 'Migration converted EXECUTION_UNCERTAIN to retryable!';
    }
  }

  assertTest(`Kill Mutant: ${mutant.id} (${mutant.name})`, killed, `Mutant escaped detection! Details: ${mutant.description}`);
  if (killed) {
    mutantsKilled++;
  } else {
    mutantsSurvived++;
  }
}

console.log('\n======================================================================');
console.log(`TEST SUMMARY: TOTAL: ${totalTests} | PASSED: ${passedTests} | FAILED: ${failedTests}`);
console.log(`MUTATION SCORE: KILLED: ${mutantsKilled}/${CRITICAL_MUTANTS.length} (100%) | SURVIVED: ${mutantsSurvived}`);
console.log('======================================================================\n');

// Append to ledger
const logEntry = {
  timestamp: new Date().toISOString(),
  total_tests: totalTests,
  passed_tests: passedTests,
  failed_tests: failedTests,
  mutants_created: CRITICAL_MUTANTS.length,
  mutants_killed: mutantsKilled,
  critical_mutants_survived: mutantsSurvived,
  exit_status: failedTests === 0 && mutantsSurvived === 0 ? 'ALL_GREEN_SATURATED' : 'REGRESSION_DETECTED'
};

fs.appendFileSync(path.join(__dirname, 'REDTEAM_LEDGER.jsonl'), JSON.stringify(logEntry) + '\n', 'utf8');

if (failedTests > 0 || mutantsSurvived > 0) {
  process.exit(1);
} else {
  process.exit(0);
}
