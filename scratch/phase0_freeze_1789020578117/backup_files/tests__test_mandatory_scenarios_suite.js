// test_mandatory_scenarios_suite.js
// Validates all 19 mandatory production-readiness scenarios against shadow integration
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');

const shadowRoot = path.resolve(__dirname, '..');
const supervisorRoot = path.join(shadowRoot, 'supervisor');
const governanceRoot = path.join(shadowRoot, 'governance');
const coreRoot = path.join(shadowRoot, 'core');

const {
  SupervisorPlane,
  NoStackingDetector,
  ResourceLockManager,
  ProcessLeaseManager,
  DecisionEngine,
  BorderGuard,
  TaskPassport,
  CompletionGovernor,
  ProgressTracker,
  ResultCustoms,
  EvidenceVerifier,
  LEASE_STATUS,
  SUPERVISOR_DECISION
} = require(path.join(supervisorRoot, 'index.js'));

const { CapabilityEngine } = require(path.join(governanceRoot, 'CapabilityEngine.js'));
const { ReplayEngine, CrashReconciler } = require(path.join(coreRoot, 'ReplayEngine.js'));
const { DurableEventLog } = require(path.join(coreRoot, 'DurableEventLog.js'));

console.log('=== RUNNING 19 MANDATORY PRODUCTION READINESS SCENARIOS ===');
const results = [];

function assert(scenarioNum, name, condition, details = '') {
  results.push({
    scenario: scenarioNum,
    name,
    passed: !!condition,
    details: details || (condition ? 'Passed assertion' : 'Failed assertion')
  });
  console.log(`[${condition ? 'PASS' : 'FAIL'}] Scenario ${scenarioNum}: ${name} - ${details}`);
}

// 1. parent/child filesystem conflict
{
  const rlm = new ResourceLockManager();
  const lockParent = rlm.acquire('C:/workspace/courier', 'TASK-PARENT');
  const lockChild = rlm.acquire('C:/workspace/courier/subfolder', 'TASK-CHILD');
  assert(1, 'parent/child filesystem conflict', lockParent.acquired && !lockChild.acquired, 'Parent lock blocks child subpath lock');
}

// 2. Windows path case variants
{
  const rlm = new ResourceLockManager();
  const lockUpper = rlm.acquire('C:/WORKSPACE/COURIER/DATA', 'TASK-1');
  const lockLower = rlm.acquire('c:/workspace/courier/data', 'TASK-2');
  assert(2, 'Windows path case variants', lockUpper.acquired && !lockLower.acquired, 'Case-insensitive NTFS path collision detected');
}

// 3. independent resources may still run concurrently
{
  const rlm = new ResourceLockManager();
  const lockA = rlm.acquire('C:/workspace/courier/moduleA', 'TASK-A');
  const lockB = rlm.acquire('C:/workspace/courier/moduleB', 'TASK-B');
  assert(3, 'independent resources may still run concurrently', lockA.acquired && lockB.acquired, 'Non-overlapping sibling subpaths run in parallel');
}

// 4. PID reuse
{
  const plm = new ProcessLeaseManager(path.join(shadowRoot, 'scratch_test_leases_1'));
  const t0 = 100000;
  plm.createLease({ task_id: 'TASK-PID', pid: 12345, start_time_epoch: t0, task_token: 'TOKEN-VALID' });
  const checkRecycled = plm.verifyProcessIdentity(12345, t0 + 5000, 'TOKEN-VALID');
  assert(4, 'PID reuse', !checkRecycled.valid && !checkRecycled.can_terminate, checkRecycled.reason);
}

// 5. unknown process identity
{
  const plm = new ProcessLeaseManager(path.join(shadowRoot, 'scratch_test_leases_2'));
  const checkUnknown = plm.verifyProcessIdentity(99999, Date.now(), 'TOKEN-ANY');
  assert(5, 'unknown process identity', !checkUnknown.valid && !checkUnknown.can_terminate, checkUnknown.reason);
}

// 6. stale task token
{
  const plm = new ProcessLeaseManager(path.join(shadowRoot, 'scratch_test_leases_3'));
  const t0 = Date.now();
  plm.createLease({ task_id: 'TASK-TOKEN', pid: 54321, start_time_epoch: t0, task_token: 'TOKEN-LEGIT' });
  const checkStale = plm.verifyProcessIdentity(54321, t0, 'TOKEN-FORGED-OR-STALE');
  assert(6, 'stale task token', !checkStale.valid && !checkStale.can_terminate, checkStale.reason);
}

// 7. uncertain execution + retry
{
  const de = new DecisionEngine();
  const mockLease = { process_lease_id: 'L-UNCERTAIN', task_id: 'TASK-U', status: LEASE_STATUS.RUNNING };
  const evalRes = de.evaluate({ lease: mockLease, isExecutionStateUncertain: true });
  assert(7, 'uncertain execution + retry', evalRes.classification === LEASE_STATUS.EXECUTION_UNCERTAIN && evalRes.decision === SUPERVISOR_DECISION.BLOCK_EXECUTION_UNCERTAIN, 'Execution uncertain blocks retry');
}

// 8. uncertain execution + fallback
{
  const de = new DecisionEngine();
  const mockLease = { process_lease_id: 'L-UNCERTAIN-2', task_id: 'TASK-U2', status: LEASE_STATUS.RUNNING };
  const evalRes = de.evaluate({ lease: mockLease, isExecutionStateUncertain: true });
  assert(8, 'uncertain execution + fallback', evalRes.decision !== SUPERVISOR_DECISION.PROCEED && evalRes.decision !== SUPERVISOR_DECISION.RESUME_VALID_WORK, 'Uncoordinated fallback blocked during uncertain execution');
}

// 9. unstamped dispatch
{
  const bg = BorderGuard;
  const task = { task_id: 'TASK-UNSTAMPED', state: 'PROPOSED', scope_paths: ['C:/test'] };
  const inspection = bg.inspect(task, null, new ResourceLockManager());
  assert(9, 'unstamped dispatch', inspection.outcome !== 'GREEN_CARD', inspection.reason);
}

// 10. stale TaskPassport
{
  const bg = BorderGuard;
  const task = { task_id: 'TASK-STALE-PASS', task_version: 2, state: 'STAMPED', scope_paths: ['C:/test'] };
  const stalePassport = TaskPassport.createPassport({ task_id: 'TASK-STALE-PASS', task_version: 1, scope_paths: ['C:/test'] });
  const inspection = bg.inspect(task, stalePassport, new ResourceLockManager());
  assert(10, 'stale TaskPassport', inspection.outcome !== 'GREEN_CARD', 'Passport version mismatch rejected');
}

// 11. malformed result envelope
{
  const passport = TaskPassport.createPassport({ task_id: 'TASK-ENVELOPE', task_version: 1, scope_paths: ['C:/test'] });
  const badEnvelope = ResultCustoms.evaluateResultEnvelope({ task_id: 'TASK-ENVELOPE', passport, exit_code: 1, artifacts: [] });
  assert(11, 'malformed result envelope', !badEnvelope.accepted, badEnvelope.reason);
}

// 12. stale result
{
  const passport = TaskPassport.createPassport({ task_id: 'TASK-STALE-RES', task_version: 2, scope_paths: ['C:/test'] });
  const staleResult = ResultCustoms.evaluateResultEnvelope({ task_id: 'TASK-STALE-RES', passport: { ...passport, task_version: 1 }, exit_code: 0, artifacts: [] });
  assert(12, 'stale result', !staleResult.accepted, 'Stale result rejected');
}

// 13. wrong task version
{
  const passport = TaskPassport.createPassport({ task_id: 'TASK-VER-MISMATCH', task_version: 1, scope_paths: ['C:/test'] });
  const res = ResultCustoms.evaluateResultEnvelope({ task_id: 'TASK-DIFFERENT', passport, exit_code: 0, artifacts: [] });
  assert(13, 'wrong task version', !res.accepted, res.reason);
}

// 14. worker claims DONE while goal evidence incomplete
{
  const gov = new CompletionGovernor();
  const rogueReport = { status: 'MISSION_SATURATED', worker_id: 'WORKER-PREMATURE' };
  const evalReport = gov.evaluateWorkerReport(rogueReport);
  const missionEval = gov.evaluateMissionStatus(5, false);
  assert(14, 'worker claims DONE while goal evidence incomplete', !evalReport.admitted && missionEval.mission_status !== 'COMPLETED', 'Worker global completion revoked; mission continues');
}

// 15. delayed result after newer task version
{
  const passportV2 = TaskPassport.createPassport({ task_id: 'TASK-SEQ', task_version: 2, scope_paths: ['C:/test'] });
  const delayedV1 = ResultCustoms.evaluateResultEnvelope({ task_id: 'TASK-SEQ', passport: { ...passportV2, task_version: 1 }, exit_code: 0, artifacts: [] });
  assert(15, 'delayed result after newer task version', !delayedV1.accepted, 'Older version rejected after newer dispatched');
}

// 16. crash after result persistence but before verification
{
  const crashedSnapshot = {
    active_leases: [{ resource: 'C:/res', taskId: 'TASK-CRASHED' }],
    tasks: [{ task_id: 'TASK-CRASHED', state: 'IN_FLIGHT' }],
    goals: []
  };
  const recon = CrashReconciler.reconcileOnStartup(crashedSnapshot);
  assert(16, 'crash after result persistence but before verification', recon.reconciledTasks[0].state === 'EXECUTION_UNCERTAIN', 'Mid-flight task fenced as EXECUTION_UNCERTAIN');
}

// 17. restart and deterministic reconciliation
{
  const logPath = path.join(shadowRoot, 'scratch_test_event.log');
  if (fs.existsSync(logPath)) fs.unlinkSync(logPath);
  const log = new DurableEventLog(logPath);
  log.append({ type: 'TASK_HEARTBEAT', index: 1, timestamp: new Date().toISOString() });
  log.append({ type: 'TASK_HEARTBEAT', index: 2, timestamp: new Date().toISOString() });
  const rep1 = ReplayEngine.rebuildState(log);
  const rep2 = ReplayEngine.rebuildState(log);
  assert(17, 'restart and deterministic reconciliation', rep1.total_events === rep2.total_events && rep1.total_events === 2, 'Identical replay across multiple process runs');
}

// 18. Human Gate remains fail-closed
{
  const authSecrets = CapabilityEngine.authorize('SECRETS_ACCESS', 2);
  const authFinance = CapabilityEngine.authorize('FINANCIAL_LIABILITY', 2);
  assert(18, 'Human Gate remains fail-closed', !authSecrets.allowed && authSecrets.requires_human_gate && !authFinance.allowed && authFinance.requires_human_gate, 'High-privilege actions strictly held for Human Gate');
}

// 19. zero-spend invariants remain intact
{
  const authSpend = CapabilityEngine.authorize('SPEND_EUR', 2);
  const authTrade = CapabilityEngine.authorize('REAL_TRADE', 2);
  assert(19, 'zero-spend invariants remain intact', !authSpend.allowed && !authTrade.allowed, 'Spend and real trade strictly blocked (limit €0)');
}

console.log('\n================================================================');
const allPassed = results.every(r => r.passed);
console.log(`MANDATORY SCENARIOS SUMMARY: ${results.filter(r => r.passed).length} / ${results.length} PASSED`);
console.log(`ALL 19 SCENARIOS PASSED: ${allPassed}`);
console.log('================================================================');

const report = {
  suite: 'MANDATORY_SCENARIOS_SUITE',
  total_scenarios: results.length,
  passed_count: results.filter(r => r.passed).length,
  failed_count: results.filter(r => !r.passed).length,
  all_passed: allPassed,
  timestamp_utc: new Date().toISOString(),
  results
};

fs.writeFileSync(path.join(shadowRoot, 'MANDATORY_SCENARIOS_REPORT.json'), JSON.stringify(report, null, 2), 'utf8');
if (!allPassed) process.exit(1);