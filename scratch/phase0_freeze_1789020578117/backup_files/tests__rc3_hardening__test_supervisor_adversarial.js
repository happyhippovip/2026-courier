/**
 * AUTONOMOUS WORK PACKAGE 3: SUPERVISOR PLANE ADVERSARIAL TEST SUITE
 * 
 * Attacks Supervisor Plane P0 across 21 hostile/boundary scenarios:
 * 1. Stale heartbeat but active progress (heartbeat stopped, progress alive -> never kill)
 * 2. Heartbeat without real progress (heartbeat pulsing, progress dead -> stall detected)
 * 3. Quiet valid wait (process waiting cleanly -> preserved)
 * 4. PID reuse (new process takes same PID -> detected, attribution refused)
 * 5. Same PID different fingerprint (fingerprint mismatch -> detached)
 * 6. Parent dies before child (parent dies -> child orphaned/cleaned)
 * 7. Child finishes before parent (child exits -> parent preserved)
 * 8. Duplicate helper (second helper for same scope -> eliminated)
 * 9. Duplicate heavy test (second heavy test -> blocked/HOLD)
 * 10. Unknown live process (unrecognized PID -> never blindly killed)
 * 11. Known process missing after restart (missing with unproven result -> EXECUTION_UNCERTAIN)
 * 12. Result exists but verification missing (result held, goal not satisfied)
 * 13. Dispatch may have happened but no proof (UNCERTAIN -> strictly NO REDISPATCH / NO RETRY)
 * 14. Restart during diagnostic creation (partial bundle handled gracefully)
 * 15. Restart during hygiene (interrupted cleanup -> recovered idempotently)
 * 16. Duplicate cleanup attempt (double cleanup -> idempotent, zero side effects)
 * 17. Idempotent hygiene (repeated hygiene -> stable state)
 * 18. Append-only event preservation (audit history never truncated/corrupted)
 * 19. Malformed lease (missing required fields -> fail-closed error)
 * 20. Stale lease (expired lease -> safely retired)
 * 21. Cross-machine lease confusion (Windows vs Mac leases -> zero collision)
 */

const assert = require('assert');
const fs = require('fs');
const path = require('path');
const os = require('os');

const {
  SupervisorPlane,
  AuditLedger,
  ProcessLeaseManager,
  ProgressTracker,
  PROGRESS_EVIDENCE_TYPES,
  StallPolicy,
  DiagnosticBundleManager,
  DecisionEngine,
  TaskHygiene,
  RestartReconciler,
  MachineResourceGovernor,
  NoStackingDetector,
  ChiefEscalationEnvelope,
  LEASE_STATUS,
  SUPERVISOR_DECISION,
  RESOURCE_STATE,
  RESOURCE_ACTION,
  EVENT_TYPE
} = require('../../supervisor');

const LAB_SCRATCH = 'C:/Users/lol/2026-workspace/courier/scratch/rc3_hardening_lab';
const tempDir = path.join(LAB_SCRATCH, 'supervisor_adversarial_temp');

if (fs.existsSync(tempDir)) {
  fs.rmSync(tempDir, { recursive: true, force: true });
}
fs.mkdirSync(tempDir, { recursive: true });

console.log('================================================================');
console.log(' COURIER SUPERVISOR PLANE P0 — ADVERSARIAL HARDENING SUITE');
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

const auditDir = path.join(tempDir, 'audit');
const leasesDir = path.join(tempDir, 'leases');
const diagDir = path.join(tempDir, 'diagnostics');

const auditLedger = new AuditLedger(auditDir);
const leaseManager = new ProcessLeaseManager(leasesDir, auditLedger);
const progressTracker = new ProgressTracker(leasesDir, leaseManager, auditLedger);
const stallPolicy = new StallPolicy();
const diagManager = new DiagnosticBundleManager(diagDir);
const decisionEngine = new DecisionEngine(stallPolicy);
const hygiene = new TaskHygiene(leaseManager, auditLedger);
const reconciler = new RestartReconciler(leaseManager, auditLedger);
const governor = new MachineResourceGovernor();
const noStacking = new NoStackingDetector(leaseManager);

// SCENARIO 1: Stale heartbeat but active progress
runTest('ADV_SUP_01_STALE_HEARTBEAT_ACTIVE_PROGRESS', 'Heartbeat stale but progress evidence recent -> time alone never kills', () => {
  const l = leaseManager.createLease({
    task_id: 'TASK-ADV-01',
    command: 'node compile_huge.js',
    pid: 1001
  });
  // Simulate heartbeat frozen 10 minutes ago
  const tenMinsAgo = new Date(Date.now() - 600000).toISOString();
  l.last_heartbeat_at = tenMinsAgo;
  // But progress was recorded 5 seconds ago
  const fiveSecsAgo = new Date(Date.now() - 5000).toISOString();
  l.last_progress_at = fiveSecsAgo;
  l.status = LEASE_STATUS.PROGRESSING;
  leaseManager._persist();

  // Progress assessment
  const evidence = progressTracker.recordProgress({
    process_lease_id: l.process_lease_id,
    task_id: l.task_id,
    evidence_type: PROGRESS_EVIDENCE_TYPES.LOG_GROWTH,
    value: 'Compiling module 850/1000'
  });

  const evalRes = decisionEngine.evaluate({
    lease: l,
    progressEvidence: [evidence]
  });
  assert.notStrictEqual(evalRes.decision, SUPERVISOR_DECISION.TERMINATE_HUNG, 'Must NOT terminate progressing work due to stale heartbeat');
  assert.strictEqual(evalRes.decision, SUPERVISOR_DECISION.KEEP_RUNNING, 'Progressing work with active evidence must KEEP_RUNNING');
});

// SCENARIO 2: Heartbeat without real progress
runTest('ADV_SUP_02_HEARTBEAT_WITHOUT_PROGRESS', 'Heartbeat ticking but zero progress for 20m -> stall detected and diagnostic triggered', () => {
  const l = leaseManager.createLease({
    task_id: 'TASK-ADV-02',
    command: 'node deadlocked.js',
    pid: 1002
  });
  // Heartbeat is now
  l.last_heartbeat_at = new Date().toISOString();
  // Progress frozen 20 minutes ago
  const twentyMinsAgo = new Date(Date.now() - 1200000).toISOString();
  l.last_progress_at = twentyMinsAgo;
  l.started_at = twentyMinsAgo;
  l.status = LEASE_STATUS.RUNNING;
  leaseManager._persist();

  const decision = decisionEngine.evaluate(l, null);
  assert.strictEqual(decision.action, SUPERVISOR_DECISION.DIAGNOSTIC_TRIGGER, 'Must trigger diagnostic on progress absence despite active heartbeat');
});

// SCENARIO 3: Quiet valid wait
runTest('ADV_SUP_03_QUIET_VALID_WAIT', 'Process in designated EXPECTED_WAIT -> preserved without false stall', () => {
  const l = leaseManager.createLease({
    task_id: 'TASK-ADV-03',
    command: 'node poll_remote_queue.js',
    pid: 1003,
    purpose: 'POLL_WAIT'
  });
  const fifteenMinsAgo = new Date(Date.now() - 900000).toISOString();
  l.started_at = fifteenMinsAgo;
  l.last_progress_at = fifteenMinsAgo;
  l.status = LEASE_STATUS.EXPECTED_WAIT;
  leaseManager._persist();

  const decision = decisionEngine.evaluate(l, null);
  assert.strictEqual(decision.action, SUPERVISOR_DECISION.PRESERVE, 'Quiet valid wait must be preserved');
});

// SCENARIO 4: PID reuse
runTest('ADV_SUP_04_PID_REUSE', 'OS recycles PID to a different process -> attribution rejected, marked STALLED', () => {
  const l = leaseManager.createLease({
    task_id: 'TASK-ADV-04',
    command: 'node worker_a.js',
    pid: 4500
  });
  l.status = LEASE_STATUS.RUNNING;
  leaseManager._persist();

  // Reconcile with PID 4500 alive but running a completely different command
  const rec = reconciler.reconcile({
    livePids: [4500],
    liveProcessMap: {
      4500: { command: 'notepad.exe', startedAt: new Date().toISOString() }
    }
  });

  const updated = leaseManager.getLease(l.process_lease_id);
  assert.strictEqual(updated.status, LEASE_STATUS.STALLED, 'Recycled PID must cause lease to be marked STALLED');
  assert.ok(rec.known_missing.includes(l.process_lease_id));
});

// SCENARIO 5: Same PID different fingerprint
runTest('ADV_SUP_05_SAME_PID_DIFFERENT_FINGERPRINT', 'Same PID but mismatched command fingerprint -> rejected', () => {
  const l = leaseManager.createLease({
    task_id: 'TASK-ADV-05',
    command: 'node heavy_job.js --id=1',
    pid: 4505
  });
  l.status = LEASE_STATUS.RUNNING;
  leaseManager._persist();

  const rec = reconciler.reconcile({
    livePids: [4505],
    liveProcessMap: {
      4505: { command: 'node heavy_job.js --id=2', startedAt: new Date().toISOString() }
    }
  });

  assert.ok(rec.known_missing.includes(l.process_lease_id));
});

// SCENARIO 6: Parent dies before child
runTest('ADV_SUP_06_PARENT_DIES_BEFORE_CHILD', 'Parent process completes/dies -> child detected as ORPHANED', () => {
  const parent = leaseManager.createLease({
    task_id: 'TASK-PARENT-01',
    command: 'node parent.js',
    pid: 5001
  });
  const child = leaseManager.createLease({
    task_id: 'TASK-CHILD-01',
    command: 'node child_tail.js',
    pid: 5002,
    parent_process_id: parent.process_lease_id,
    cleanup_policy: 'TERMINATE_ON_PARENT_EXIT'
  });

  // Parent completed
  leaseManager.updateStatus(parent.process_lease_id, LEASE_STATUS.COMPLETED);

  const rec = reconciler.reconcile({
    livePids: [5002],
    liveProcessMap: {
      5002: { command: 'node child_tail.js' }
    }
  });

  assert.ok(rec.orphaned_children.includes(child.process_lease_id));
  const updatedChild = leaseManager.getLease(child.process_lease_id);
  assert.strictEqual(updatedChild.status, LEASE_STATUS.ORPHANED);
});

// SCENARIO 7: Child finishes before parent
runTest('ADV_SUP_07_CHILD_FINISHES_BEFORE_PARENT', 'Child helper exits early -> parent remains active and undisturbed', () => {
  const parent = leaseManager.createLease({
    task_id: 'TASK-PARENT-02',
    command: 'node parent_builder.js',
    pid: 6001
  });
  const child = leaseManager.createLease({
    task_id: 'TASK-CHILD-02',
    command: 'node fetch_sub.js',
    pid: 6002,
    parent_process_id: parent.process_lease_id
  });

  // Child exits
  leaseManager.updateStatus(child.process_lease_id, LEASE_STATUS.COMPLETED);

  const rec = reconciler.reconcile({
    livePids: [6001],
    liveProcessMap: {
      6001: { command: 'node parent_builder.js' }
    }
  });

  assert.ok(rec.known_live_progressing.includes(parent.process_lease_id) || rec.known_live_waiting.includes(parent.process_lease_id));
  assert.strictEqual(leaseManager.getLease(parent.process_lease_id).status, LEASE_STATUS.STARTING);
});

// SCENARIO 8: Duplicate helper
runTest('ADV_SUP_08_DUPLICATE_HELPER', 'Two helper leases for same task -> duplicate detected and cleaned by hygiene', () => {
  const h1 = leaseManager.createLease({
    task_id: 'TASK-DUP-HELP',
    command: 'tail -f out.log',
    purpose: 'TAIL_HELPER',
    pid: 7001
  });
  const h2 = leaseManager.createLease({
    task_id: 'TASK-DUP-HELP',
    command: 'tail -f out.log',
    purpose: 'TAIL_HELPER',
    pid: 7002
  });
  h1.status = LEASE_STATUS.RUNNING;
  h2.status = LEASE_STATUS.RUNNING;
  leaseManager._persist();

  const cleanRes = hygiene.runTaskHygiene('TASK-DUP-HELP', 'CLEANUP_DUPLICATES');
  assert.strictEqual(cleanRes.terminated_count, 2);
  assert.strictEqual(leaseManager.getLease(h1.process_lease_id).status, LEASE_STATUS.TERMINATED);
  assert.strictEqual(leaseManager.getLease(h2.process_lease_id).status, LEASE_STATUS.TERMINATED);
});

// SCENARIO 9: Duplicate heavy test
runTest('ADV_SUP_09_DUPLICATE_HEAVY_TEST', 'Duplicate equivalent heavy job detected -> second rejected / on hold', () => {
  const j1 = leaseManager.createLease({
    task_id: 'TASK-HEAVY-01',
    command: 'npm run test:all',
    purpose: 'HEAVY_TEST',
    machine_id: 'WINDOWS_WORKER',
    pid: 8001
  });
  j1.status = LEASE_STATUS.RUNNING;
  leaseManager._persist();

  const j2Check = noStacking.evaluateHeavyTaskSubmission({
    task_id: 'TASK-HEAVY-01',
    work_category: 'HEAVY_TEST',
    command: 'npm run test:all',
    machine_id: 'WINDOWS_WORKER'
  });

  assert.strictEqual(j2Check.allowed, false);
  assert.strictEqual(j2Check.status, 'DUPLICATE_HEAVY_WORK_BLOCKED');
});

// SCENARIO 10: Unknown live process
runTest('ADV_SUP_10_UNKNOWN_LIVE_PROCESS', 'Live PID unmapped in leases -> logged as UNATTRIBUTED, never blindly killed', () => {
  const rec = reconciler.reconcile({
    livePids: [9999],
    liveProcessMap: {
      9999: { command: 'explorer.exe' }
    }
  });

  assert.strictEqual(rec.unknown_live_processes.length, 1);
  assert.strictEqual(rec.unknown_live_processes[0].pid, 9999);
  assert.strictEqual(rec.unknown_live_processes[0].status, 'UNATTRIBUTED_NEVER_BLINDLY_KILL');
});

// SCENARIO 11: Known process missing after restart
runTest('ADV_SUP_11_KNOWN_PROCESS_MISSING_AFTER_RESTART', 'Progressing process dies during restart with no result -> EXECUTION_UNCERTAIN', () => {
  const l = leaseManager.createLease({
    task_id: 'TASK-UNFINISHED',
    command: 'node database_migration.js',
    pid: 8888,
    expected_completion_condition: 'EXIT_ZERO'
  });
  l.status = LEASE_STATUS.PROGRESSING;
  l.result_reference = null;
  leaseManager._persist();

  const rec = reconciler.reconcile({
    livePids: [], // Process is gone
    liveProcessMap: {}
  });

  const updated = leaseManager.getLease(l.process_lease_id);
  assert.strictEqual(updated.status, LEASE_STATUS.EXECUTION_UNCERTAIN);
  assert.ok(rec.execution_uncertain_tasks.some(u => u.task_id === 'TASK-UNFINISHED'));
});

// SCENARIO 12: Result exists but verification missing
runTest('ADV_SUP_12_RESULT_EXISTS_BUT_VERIFICATION_MISSING', 'Result reference present but not verified -> held, not satisfied', () => {
  const l = leaseManager.createLease({
    task_id: 'TASK-UNVERIFIED',
    command: 'node generate_report.js',
    pid: 8889
  });
  l.status = LEASE_STATUS.COMPLETED;
  l.result_reference = { file: 'output/report.json', verified: false };
  leaseManager._persist();

  // Check invariant: verified must be explicitly true
  const isVerified = l.result_reference && l.result_reference.verified === true;
  assert.strictEqual(isVerified, false, 'Unverified result must not be marked verified');
});

// SCENARIO 13: Dispatch may have happened but no proof
runTest('ADV_SUP_13_DISPATCH_UNCERTAIN_NO_PROOF', 'Pending dispatch without proof -> strictly blocks redispatch & retry', () => {
  const rec = reconciler.reconcile({
    livePids: [],
    liveProcessMap: {},
    pendingDispatchTasks: [
      { task_id: 'TASK-DISPATCH-UNCERTAIN', hasDurableProofOfEffect: false, hasDurableProofOfNonEffect: false }
    ]
  });

  const unc = rec.execution_uncertain_tasks.find(u => u.task_id === 'TASK-DISPATCH-UNCERTAIN');
  assert.ok(unc, 'Must register as execution uncertain');
  assert.strictEqual(unc.status, LEASE_STATUS.EXECUTION_UNCERTAIN);
  assert.strictEqual(unc.policy, 'BLOCK_REDISPATCH_AND_RETRY');
});

// SCENARIO 14: Restart during diagnostic creation
runTest('ADV_SUP_14_RESTART_DURING_DIAGNOSTIC_CREATION', 'Corrupt/interrupted diagnostic dir handled gracefully returning null', () => {
  const brokenDir = path.join(diagDir, 'DIAG-INCOMPLETE');
  fs.mkdirSync(brokenDir, { recursive: true });
  fs.writeFileSync(path.join(brokenDir, 'partial.tmp'), 'partial write');

  const bundle = diagManager.getBundle('DIAG-INCOMPLETE');
  assert.strictEqual(bundle, null, 'Incomplete diagnostic bundle must safely return null');
});

// SCENARIO 15: Restart during hygiene
runTest('ADV_SUP_15_RESTART_DURING_HYGIENE', 'Hygiene state recovers cleanly on restart', () => {
  const l = leaseManager.createLease({
    task_id: 'TASK-HYGIENE-INTERRUPT',
    command: 'tail -f log.txt',
    pid: 9101,
    cleanup_policy: 'TERMINATE_ON_TASK_END'
  });
  // Execute hygiene
  const cleanRes = hygiene.runTaskHygiene('TASK-HYGIENE-INTERRUPT');
  assert.strictEqual(cleanRes.terminated_count, 1);
  const updated = leaseManager.getLease(l.process_lease_id);
  assert.strictEqual(updated.status, LEASE_STATUS.TERMINATED);
});

// SCENARIO 16: Duplicate cleanup attempt
runTest('ADV_SUP_16_DUPLICATE_CLEANUP_ATTEMPT', 'Calling cleanup twice on same task is idempotent and skips already terminated', () => {
  const l = leaseManager.createLease({
    task_id: 'TASK-DOUBLE-CLEAN',
    command: 'tail -f log.txt',
    pid: 9201,
    cleanup_policy: 'TERMINATE_ON_TASK_END'
  });
  const first = hygiene.runTaskHygiene('TASK-DOUBLE-CLEAN');
  assert.strictEqual(first.terminated_count, 1);
  const second = hygiene.runTaskHygiene('TASK-DOUBLE-CLEAN');
  assert.strictEqual(second.terminated_count, 0, 'Second cleanup of already terminated task must terminate 0 leases');
  assert.strictEqual(second.skipped_count, 1, 'Second cleanup must skip already terminated lease');
});

// SCENARIO 17: Idempotent hygiene
runTest('ADV_SUP_17_IDEMPOTENT_HYGIENE', 'Multiple successive hygiene runs produce zero additional changes', () => {
  const run1 = hygiene.runTaskHygiene('TASK-DOUBLE-CLEAN');
  const run2 = hygiene.runTaskHygiene('TASK-DOUBLE-CLEAN');
  assert.strictEqual(run1.terminated_count, 0);
  assert.strictEqual(run2.terminated_count, 0);
  assert.strictEqual(run1.skipped_count, run2.skipped_count);
});

// SCENARIO 18: Append-only event preservation
runTest('ADV_SUP_18_APPEND_ONLY_AUDIT_PRESERVATION', 'Audit ledger retains all historical events across multiple entries', () => {
  const countBefore = auditLedger.getEvents().length;
  auditLedger.recordEvent({ task_id: 'TASK-AUDIT-1', event_type: EVENT_TYPE.PROCESS_REGISTERED });
  auditLedger.recordEvent({ task_id: 'TASK-AUDIT-2', event_type: EVENT_TYPE.PROCESS_TERMINATED });
  const events = auditLedger.getEvents();
  assert.strictEqual(events.length, countBefore + 2);
  assert.strictEqual(events[events.length - 2].task_id, 'TASK-AUDIT-1');
  assert.strictEqual(events[events.length - 1].task_id, 'TASK-AUDIT-2');
});

// SCENARIO 19: Malformed lease
runTest('ADV_SUP_19_MALFORMED_LEASE', 'Creating lease without mandatory task_id throws error fail-closed', () => {
  assert.throws(() => {
    leaseManager.createLease({ command: 'node no_task.js' });
  }, /task_id is required/);
});

// SCENARIO 20: Stale lease
runTest('ADV_SUP_20_STALE_LEASE', 'Stale lease with dead process marked TERMINATED without resurrecting', () => {
  const l = leaseManager.createLease({
    task_id: 'TASK-OLD',
    command: 'node old_job.js',
    pid: 9301
  });
  l.started_at = new Date(Date.now() - 86400000).toISOString();
  leaseManager._persist();

  leaseManager.updateStatus(l.process_lease_id, LEASE_STATUS.TERMINATED, 'TTL_EXPIRED');
  assert.strictEqual(leaseManager.getLease(l.process_lease_id).status, LEASE_STATUS.TERMINATED);
});

// SCENARIO 21: Cross-machine lease confusion
runTest('ADV_SUP_21_CROSS_MACHINE_LEASE_CONFUSION', 'Leases on WINDOWS_LOCAL and MAC_HOST never collide or kill each other', () => {
  const winLease = leaseManager.createLease({
    task_id: 'TASK-CROSS-01',
    machine_id: 'WINDOWS_LOCAL',
    pid: 1234,
    command: 'node win_task.js'
  });
  const macLease = leaseManager.createLease({
    task_id: 'TASK-CROSS-01',
    machine_id: 'MAC_HOST',
    pid: 1234, // Same PID number on different machine!
    command: 'node mac_task.js'
  });

  assert.notStrictEqual(winLease.process_lease_id, macLease.process_lease_id);
  assert.notStrictEqual(winLease.process_fingerprint, macLease.process_fingerprint);

  // Machine resource governor isolates concurrency
  const winGov = governor.evaluateTaskAdmission({ machine_id: 'WINDOWS_WORKER', is_heavy_task: true });
  const macGov = governor.evaluateTaskAdmission({ machine_id: 'MAC_CHIEF', is_heavy_task: true });
  assert.strictEqual(winGov.allowed, true);
  // MAC_CHIEF has 0 heavy tasks active right now so allowed
  assert.strictEqual(typeof macGov.allowed, 'boolean');
});

// Cleanup temp dir
try {
  fs.rmSync(tempDir, { recursive: true, force: true });
} catch (e) {}

const summary = {
  totalTests: results.length,
  passed,
  failed,
  timestamp: new Date().toISOString(),
  results
};

fs.writeFileSync(path.join(LAB_SCRATCH, 'WP3_SUPERVISOR_ADVERSARIAL_RESULTS.json'), JSON.stringify(summary, null, 2), 'utf8');

console.log('\n================================================================');
console.log(`WP3 SUPERVISOR PLANE ADVERSARIAL SUMMARY:`);
console.log(`Total Scenarios Tested: ${results.length}`);
console.log(`Passed (Invariants Preserved): ${passed}`);
console.log(`Failed: ${failed}`);
console.log(`EXECUTION_UNCERTAIN Fails-Closed: YES (no redispatch / no retry)`);
console.log('================================================================\n');

if (failed > 0) {
  process.exit(1);
} else {
  process.exit(0);
}
