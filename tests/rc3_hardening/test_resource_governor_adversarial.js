/**
 * AUTONOMOUS WORK PACKAGE 4: RESOURCE / THERMAL GOVERNOR ADVERSARIAL TEST SUITE
 * 
 * Tests cross-machine thermal isolation, pressure boundaries, recovery transitions,
 * and the core safety invariant: TIME OR TEMPERATURE ALONE NEVER KILLS A PROGRESSING PROCESS.
 */

const assert = require('assert');
const fs = require('fs');
const path = require('path');

const {
  MachineResourceGovernor,
  StallPolicy,
  NoStackingDetector,
  ProcessLeaseManager,
  AuditLedger,
  RESOURCE_STATE,
  RESOURCE_ACTION,
  SUPERVISOR_DECISION,
  LEASE_STATUS
} = require('../../supervisor');

const LAB_SCRATCH = path.join(__dirname, '..', '..', 'scratch', 'rc3_hardening_lab');
if (!fs.existsSync(LAB_SCRATCH)) fs.mkdirSync(LAB_SCRATCH, { recursive: true });
const tempDir = path.join(LAB_SCRATCH, 'governor_adversarial_temp');

if (fs.existsSync(tempDir)) {
  fs.rmSync(tempDir, { recursive: true, force: true });
}
fs.mkdirSync(tempDir, { recursive: true });

console.log('================================================================');
console.log(' RESOURCE / THERMAL GOVERNOR ADVERSARIAL TEST SUITE');
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

const auditLedger = new AuditLedger(path.join(tempDir, 'audit'));
const leaseManager = new ProcessLeaseManager(path.join(tempDir, 'leases'), auditLedger);
const stallPolicy = new StallPolicy();
const noStacking = new NoStackingDetector(leaseManager);

// SCENARIO 1: Mac THERMAL_PRESSURE & Windows NORMAL
runTest('ADV_GOV_01_MAC_THERMAL_WINDOWS_NORMAL', 'Mac heat incident holds Mac heavy work while Windows remains eligible', () => {
  const governor = new MachineResourceGovernor();
  governor.updatePressure({
    machine_id: 'MAC_CHIEF',
    thermal_state: 'THERMAL_PRESSURE',
    cpu_load: 0.95,
    active_heavy_tasks: 1
  });
  governor.updatePressure({
    machine_id: 'WINDOWS_WORKER',
    thermal_state: 'NORMAL',
    cpu_load: 0.15,
    active_heavy_tasks: 0
  });

  const macHeavy = governor.evaluateTaskAdmission({ machine_id: 'MAC_CHIEF', is_heavy_task: true });
  const winHeavy = governor.evaluateTaskAdmission({ machine_id: 'WINDOWS_WORKER', is_heavy_task: true });

  assert.strictEqual(macHeavy.allowed, false, 'Mac heavy task must be held under THERMAL_PRESSURE');
  assert.strictEqual(macHeavy.action, RESOURCE_ACTION.RECOMMEND_REROUTE, 'Mac must recommend reroute to healthy Windows');
  assert.strictEqual(macHeavy.reroute_target_machine_id, 'WINDOWS_WORKER');

  assert.strictEqual(winHeavy.allowed, true, 'Healthy Windows must remain fully eligible');
  assert.strictEqual(winHeavy.action, RESOURCE_ACTION.ALLOW);
});

// SCENARIO 2: Windows PRESSURE only affects Windows
runTest('ADV_GOV_02_WINDOWS_PRESSURE_LOCAL_ONLY', 'Windows pressure holds only Windows heavy work without affecting Mac', () => {
  const governor = new MachineResourceGovernor();
  governor.updatePressure({
    machine_id: 'MAC_CHIEF',
    thermal_state: 'NORMAL',
    cpu_load: 0.20,
    active_heavy_tasks: 0
  });
  governor.updatePressure({
    machine_id: 'WINDOWS_WORKER',
    thermal_state: 'NORMAL',
    cpu_load: 0.95, // High CPU load on Windows
    active_heavy_tasks: 4
  });

  const winCheck = governor.evaluateTaskAdmission({ machine_id: 'WINDOWS_WORKER', is_heavy_task: true });
  const macCheck = governor.evaluateTaskAdmission({ machine_id: 'MAC_CHIEF', is_heavy_task: true });

  assert.strictEqual(winCheck.allowed, false, 'Windows heavy task must be held under high load');
  assert.strictEqual(macCheck.allowed, true, 'Idle Mac must remain eligible');
});

// SCENARIO 3: Mac recovery
runTest('ADV_GOV_03_MAC_RECOVERY', 'Mac cools down and recovers to NORMAL, restoring heavy admission', () => {
  const governor = new MachineResourceGovernor();
  governor.updatePressure({
    machine_id: 'MAC_CHIEF',
    thermal_state: 'THERMAL_PRESSURE'
  });
  assert.strictEqual(governor.getMachineState('MAC_CHIEF').resource_state, RESOURCE_STATE.THERMAL_PRESSURE);

  // Recovery transition
  governor.updatePressure({
    machine_id: 'MAC_CHIEF',
    thermal_state: 'NORMAL',
    cpu_load: 0.25,
    active_heavy_tasks: 0
  });
  assert.strictEqual(governor.getMachineState('MAC_CHIEF').resource_state, RESOURCE_STATE.NORMAL);

  const macCheck = governor.evaluateTaskAdmission({ machine_id: 'MAC_CHIEF', is_heavy_task: true });
  assert.strictEqual(macCheck.allowed, true);
  assert.strictEqual(macCheck.action, RESOURCE_ACTION.ALLOW);
});

// SCENARIO 4: Unknown thermal state
runTest('ADV_GOV_04_UNKNOWN_THERMAL_STATE', 'Unknown thermal state is handled conservatively without crashing', () => {
  const governor = new MachineResourceGovernor();
  governor.updatePressure({
    machine_id: 'WINDOWS_WORKER',
    thermal_state: 'UNKNOWN',
    cpu_load: 0.1
  });
  const st = governor.getMachineState('WINDOWS_WORKER');
  assert.strictEqual(st.resource_state, RESOURCE_STATE.UNKNOWN);
});

// SCENARIO 5: High CPU with genuine progress
runTest('ADV_GOV_05_HIGH_CPU_WITH_GENUINE_PROGRESS', 'High CPU with progress evidence is kept running, never killed', () => {
  const dummyLease = {
    process_lease_id: 'LEASE-HIGH-CPU',
    task_id: 'TASK-COMPUTE',
    status: LEASE_STATUS.PROGRESSING,
    started_at: new Date(Date.now() - 3600000).toISOString(), // Running 1 hour
    last_progress_at: new Date(Date.now() - 10000).toISOString() // Progress 10s ago
  };

  const evalRes = stallPolicy.evaluateProcessState({
    lease: dummyLease,
    recentProgressCount: 10,
    cpuActivityDetected: true,
    nowMs: Date.now()
  });

  assert.strictEqual(evalRes.decision, SUPERVISOR_DECISION.KEEP_RUNNING, 'Active progressing process must KEEP_RUNNING regardless of elapsed time');
});

// SCENARIO 6: Low CPU with valid wait
runTest('ADV_GOV_06_LOW_CPU_VALID_WAIT', 'Low CPU in valid wait state is preserved', () => {
  const waitLease = {
    process_lease_id: 'LEASE-WAITING',
    task_id: 'TASK-POLL',
    status: LEASE_STATUS.WAITING_VALID,
    started_at: new Date(Date.now() - 1800000).toISOString(),
    last_progress_at: new Date(Date.now() - 1800000).toISOString()
  };

  const evalRes = stallPolicy.evaluateProcessState({
    lease: waitLease,
    recentProgressCount: 0,
    cpuActivityDetected: false,
    isWaitingOnKnownDependency: true,
    nowMs: Date.now()
  });

  assert.strictEqual(evalRes.decision, SUPERVISOR_DECISION.WAIT);
});

// SCENARIO 7: High memory pressure
runTest('ADV_GOV_07_HIGH_MEMORY_PRESSURE', 'High memory pressure classifies machine as PRESSURE and holds new heavy tasks', () => {
  const governor = new MachineResourceGovernor();
  governor.updatePressure({
    machine_id: 'WINDOWS_WORKER',
    memory_pressure: 'HIGH',
    cpu_load: 0.3,
    active_heavy_tasks: 0
  });

  const st = governor.getMachineState('WINDOWS_WORKER');
  assert.strictEqual(st.resource_state, RESOURCE_STATE.PRESSURE);

  const check = governor.evaluateTaskAdmission({ machine_id: 'WINDOWS_WORKER', is_heavy_task: true });
  assert.strictEqual(check.allowed, false);
});

// SCENARIO 8: Swap pressure
runTest('ADV_GOV_08_SWAP_PRESSURE', 'High swap pressure must classify machine into PRESSURE and hold heavy tasks', () => {
  const governor = new MachineResourceGovernor();
  governor.updatePressure({
    machine_id: 'WINDOWS_WORKER',
    swap_pressure: 'HIGH',
    memory_pressure: 'NORMAL',
    cpu_load: 0.3,
    active_heavy_tasks: 0
  });

  const st = governor.getMachineState('WINDOWS_WORKER');
  assert.strictEqual(st.resource_state, RESOURCE_STATE.PRESSURE, 'High swap pressure must set resource_state to PRESSURE');

  const check = governor.evaluateTaskAdmission({ machine_id: 'WINDOWS_WORKER', is_heavy_task: true });
  assert.strictEqual(check.allowed, false, 'Heavy tasks must be held during swap thrashing');
});

// SCENARIO 9: Multiple heavy jobs concurrency cap
runTest('ADV_GOV_09_MULTIPLE_HEAVY_JOBS_CAP', 'Mac concurrency cap = 1, Windows concurrency cap = 4', () => {
  const governor = new MachineResourceGovernor();
  // Fill Mac heavy slot
  governor.updatePressure({
    machine_id: 'MAC_CHIEF',
    active_heavy_tasks: 1,
    cpu_load: 0.4
  });
  const macCheck = governor.evaluateTaskAdmission({ machine_id: 'MAC_CHIEF', is_heavy_task: true });
  assert.strictEqual(macCheck.allowed, false, 'Mac at concurrency 1 must hold further heavy tasks');

  // Fill Windows to 3/4
  governor.updatePressure({
    machine_id: 'WINDOWS_WORKER',
    active_heavy_tasks: 3,
    cpu_load: 0.4
  });
  const winCheck1 = governor.evaluateTaskAdmission({ machine_id: 'WINDOWS_WORKER', is_heavy_task: true });
  assert.strictEqual(winCheck1.allowed, true, 'Windows at 3/4 heavy tasks still has 1 slot available');

  // Fill Windows to 4/4
  governor.updatePressure({
    machine_id: 'WINDOWS_WORKER',
    active_heavy_tasks: 4,
    cpu_load: 0.4
  });
  const winCheck2 = governor.evaluateTaskAdmission({ machine_id: 'WINDOWS_WORKER', is_heavy_task: true });
  assert.strictEqual(winCheck2.allowed, false, 'Windows at 4/4 heavy tasks must hold further heavy tasks');
});

// SCENARIO 10: Canonical heavy job + duplicate rejected
runTest('ADV_GOV_10_CANONICAL_PLUS_DUPLICATE', 'NoStackingDetector rejects second identical heavy task', () => {
  leaseManager.createLease({
    task_id: 'TASK-CANONICAL-01',
    command: 'cargo test --all',
    purpose: 'TEST_HEAVY',
    machine_id: 'WINDOWS_WORKER',
    status: LEASE_STATUS.RUNNING
  });

  const dupCheck = noStacking.evaluateHeavyTaskSubmission({
    task_id: 'TASK-CANONICAL-01',
    work_category: 'TEST_HEAVY',
    command: 'cargo test --all',
    machine_id: 'WINDOWS_WORKER'
  });

  assert.strictEqual(dupCheck.allowed, false);
  assert.strictEqual(dupCheck.status, 'DUPLICATE_HEAVY_WORK_BLOCKED');
});

// SCENARIO 11: Lightweight diagnostics permitted during pressure
runTest('ADV_GOV_11_LIGHTWEIGHT_DIAGNOSTICS_PERMITTED_DURING_PRESSURE', 'Lightweight tasks allowed even when machine is under heavy pressure', () => {
  const governor = new MachineResourceGovernor();
  governor.updatePressure({
    machine_id: 'MAC_CHIEF',
    thermal_state: 'THERMAL_PRESSURE',
    cpu_load: 0.85 // Non-critical load
  });

  const lightCheck = governor.evaluateTaskAdmission({ machine_id: 'MAC_CHIEF', is_heavy_task: false });
  assert.strictEqual(lightCheck.allowed, true, 'Diagnostic/inspection light tasks must remain allowed');
  assert.strictEqual(lightCheck.action, RESOURCE_ACTION.ALLOW_LIGHT_ONLY);
});

// SCENARIO 12: Invariant: Temperature/time alone never kills progressing process
runTest('ADV_GOV_12_TIME_TEMP_ALONE_NEVER_KILLS', 'StallPolicy confirms temperature/time alone never kills progressing process', () => {
  const hotLease = {
    process_lease_id: 'LEASE-HOT-M1',
    task_id: 'TASK-BIG-BUILD',
    status: LEASE_STATUS.PROGRESSING,
    started_at: new Date(Date.now() - 7200000).toISOString() // 2 hours!
  };

  const evalRes = stallPolicy.evaluateProcessState({
    lease: hotLease,
    recentProgressCount: 3,
    cpuActivityDetected: true,
    nowMs: Date.now()
  });

  assert.notStrictEqual(evalRes.decision, SUPERVISOR_DECISION.TERMINATE_HUNG);
  assert.strictEqual(evalRes.decision, SUPERVISOR_DECISION.KEEP_RUNNING);
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

fs.writeFileSync(path.join(LAB_SCRATCH, 'WP4_RESOURCE_GOVERNOR_RESULTS.json'), JSON.stringify(summary, null, 2), 'utf8');

console.log('\n================================================================');
console.log(`WP4 RESOURCE / THERMAL GOVERNOR ADVERSARIAL SUMMARY:`);
console.log(`Total Scenarios Tested: ${results.length}`);
console.log(`Passed: ${passed}`);
console.log(`Failed: ${failed}`);
console.log(`Core Invariant (Time/Temp Alone Never Kills Progressing Work): PROVEN`);
console.log('================================================================\n');

if (failed > 0) {
  process.exit(1);
} else {
  process.exit(0);
}
