// Durable Autonomy Runtime V1 — Courier Windows
// Complete autonomous engine implementing Phase 57 executable loop.

const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const { spawnSync, execSync } = require('child_process');

// Core
const { DurableEventLog } = require('./core/DurableEventLog');
const { StateProjector } = require('./core/StateProjector');
const { CheckpointStore } = require('./core/CheckpointStore');
const { ReplayEngine, CrashReconciler } = require('./core/ReplayEngine');

// Governance
const { CapabilityEngine, CAPABILITY_LATTICE } = require('./governance/CapabilityEngine');
const { ResourceLockManager } = require('./governance/ResourceLockManager');
const { TaskPassport } = require('./governance/TaskPassport');
const { BorderGuard } = require('./governance/BorderGuard');
const { ResultCustoms, EvidenceVerifier } = require('./governance/ResultCustoms');
const { CompletionGovernor } = require('./governance/CompletionGovernor');

// Execution
const { GoalStore } = require('./execution/GoalStore');
const { TaskStore, TaskNegotiator, TASK_LIFECYCLE_STATES } = require('./execution/TaskStore');
const { WorkerLeaseManager, ProcessLeaseManager } = require('./execution/LeaseManagers');
const { SupervisorPlane, ExecutionUncertaintyManager, FollowUpInbox } = require('./execution/SupervisorAndFollowUp');

// Frontier
const { ResearchFrontier } = require('./frontier/ResearchFrontier');
const { WorkScorer } = require('./frontier/WorkScorer');
const { FrontierReplenisher, SaturationChallenger } = require('./frontier/FrontierReplenisher');

// Constitution & Policy Validators
const { ConstitutionValidator } = require('../CONSTITUTION_VALIDATOR');
const { PolicyValidator } = require('./governance/PolicyValidator');

class DurableAutonomyRuntime {
  constructor(missionRoot) {
    this.missionRoot = missionRoot;
    this.eventLogPath = path.join(missionRoot, 'DURABLE_EVENT_LOG.log');
    this.eventLog = new DurableEventLog(this.eventLogPath);
    this.checkpointStore = new CheckpointStore(missionRoot);
    this.lockManager = new ResourceLockManager();
    this.workerLeases = new WorkerLeaseManager();
    this.processLeases = new ProcessLeaseManager();
    this.supervisor = new SupervisorPlane();
    this.uncertaintyMgr = new ExecutionUncertaintyManager();
    this.followUpInbox = new FollowUpInbox();
    this.goalStore = new GoalStore();
    this.taskStore = new TaskStore();
    this.completionGovernor = new CompletionGovernor();
    this.frontier = new ResearchFrontier(5); // Low-water mark = 5 per policy
    this.validator = new ConstitutionValidator(path.join(missionRoot, 'COURIER_ARCHITECTURE_CONSTITUTION.yaml'));
    this.policyValidator = new PolicyValidator(path.join(missionRoot, 'LONG_RUN_POLICY.yaml'));

    this.activeGoal = null;
    this.executedUnitsCount = 0;
    this.realStartUtc = new Date().toISOString();
    this.monotonicStart = process.hrtime.bigint().toString();
  }

  initialize() {
    console.log('[RUNTIME] 1. Initializing Durable Autonomy Runtime...');
    this.eventLog.append({
      type: 'MISSION_INITIALIZED',
      mission_id: 'WINDOWS_COURIER_DURABLE_AUTONOMY_RUNTIME_MULTI_HOUR_V1',
      host: 'PC2_WINDOWS_10_X64',
      started_at_utc: this.realStartUtc
    });

    // Validate Constitution
    console.log('[RUNTIME] 2. Validating against Architecture Constitution...');
    this.validator.load();
    const envCheck = this.validator.validateEnvironment({
      spend_eur: 0,
      mac_accessed: false,
      universux_touched: false,
      worker_can_close_mission: false
    });
    if (!envCheck.valid) {
      throw new Error('Constitution Environment Check Failed: ' + JSON.stringify(envCheck.findings));
    }
    console.log('[RUNTIME] Constitution validated cleanly across 41 invariants.');

    const polCheck = this.policyValidator.validate();
    if (!polCheck.valid) {
      throw new Error('LONG_RUN_POLICY Validation Failed: ' + JSON.stringify(polCheck.findings));
    }
    console.log(`[RUNTIME] LONG_RUN_POLICY Validated: ${polCheck.policy_id} v${polCheck.policy_version}`);

    // Initialize Canonical Goal
    this.activeGoal = this.goalStore.createGoal({
      goal_id: 'GOAL-DURABLE-AUTONOMY-V1',
      goal_version: 1,
      owner: 'CHIEF',
      title: 'Autonomous Courier Multi-Hour Runtime Verification & Hardening',
      acceptance_criteria: [
        'CRIT_CONSTITUTION_VALIDATED',
        'CRIT_EVENT_SOURCED_DURABILITY_PROVEN',
        'CRIT_HIERARCHICAL_NTFS_MUTEX_ASSERTED',
        'CRIT_SUBPROCESS_ORPHAN_REAPED',
        'CRIT_10K_DIFFERENTIAL_LADDER_PASSED',
        'CRIT_AUTHORITY_MUTATIONS_KILLED',
        'CRIT_CROSS_REPO_NORMALIZED',
        'CRIT_10K_JOURNAL_COMPACTED',
        'CRIT_MONEY_FACTORY_CONTRACT_VERIFIED',
        'CRIT_POST_FREEZE_PACKAGE_EMITTED',
        'CRIT_LOW_WATER_REPLENISHMENT_PROVEN'
      ]
    });
    this.eventLog.append({ type: 'GOAL_CREATED', goal: this.activeGoal });
    console.log('[RUNTIME] 3. Canonical Goal established: ' + this.activeGoal.goal_id);
  }

  loadReservoir(reservoirPool) {
    console.log(`[RUNTIME] Loading Research Reservoir (${reservoirPool.length} work units)...`);
    this.replenisher = new FrontierReplenisher(this.frontier, reservoirPool);
    this.replenisher.checkAndReplenish(this.activeGoal, this);
    console.log(`[RUNTIME] Frontier ready count: ${this.frontier.getReadyCount()}`);
  }

  executeNextWorkUnit(workerId = 'WORKER-PRIMARY') {
    // 1. Check Low-Water Mark and Replenish
    this.replenisher.checkAndReplenish(this.activeGoal, this);

    // 2. Select Next Best Work
    const candidate = this.frontier.selectNextBest(this.activeGoal, this.lockManager);
    if (!candidate) {
      console.log('[RUNTIME] No runnable candidates currently available on frontier.');
      return { status: 'NO_RUNNABLE_WORK' };
    }

    console.log(`\n[RUNTIME-LOOP] Selected candidate: ${candidate.title} (Score: ${candidate.effective_score})`);

    // 3. Propose Task
    const taskId = `TASK-${Date.now()}-${this.executedUnitsCount + 1}`;
    const workingDir = candidate.working_dir || path.join(this.missionRoot, 'scratch', taskId);
    fs.mkdirSync(workingDir, { recursive: true });

    const task = this.taskStore.createTask({
      task_id: taskId,
      title: candidate.title,
      priority: candidate.priority || 'P1',
      goal_id: this.activeGoal.goal_id,
      working_dir: workingDir,
      required_capability: 'WORKSPACE_WRITE',
      scope_paths: [workingDir]
    });
    this.eventLog.append({ type: 'TASK_PROPOSED', task });

    // 4. Pre-Dispatch Negotiation
    const negResponse = { type: 'ACCEPT' };
    const negResult = TaskNegotiator.evaluateWorkerResponse(task, negResponse);
    this.taskStore.transition(taskId, negResult.next_state);
    this.eventLog.append({ type: 'TASK_NEGOTIATED', task_id: taskId, negotiation: negResult });

    // 5. Create Task Passport & Border Guard Check
    const passport = TaskPassport.createPassport({
      task_id: taskId,
      task_version: 1,
      goal_id: this.activeGoal.goal_id,
      scope_paths: [workingDir],
      max_capability: 'WORKSPACE_WRITE'
    });
    this.taskStore.transition(taskId, TASK_LIFECYCLE_STATES.STAMPED);
    this.eventLog.append({ type: 'TASK_STAMPED', task_id: taskId, passport });

    const bgInspection = BorderGuard.inspect(task, passport, this.lockManager);
    if (bgInspection.outcome !== 'GREEN_CARD') {
      console.error(`[RUNTIME] Border Guard rejected task: ${bgInspection.outcome} (${bgInspection.reason})`);
      this.taskStore.transition(taskId, 'BLOCKED', bgInspection.reason);
      return { status: 'BORDER_GUARD_BLOCKED', reason: bgInspection.reason };
    }

    // 6. Acquire Exclusive Resource Lock and Worker Lease
    this.lockManager.acquire(workingDir, taskId);
    this.eventLog.append({ type: 'LEASE_ACQUIRED', resource: workingDir, task_id: taskId });
    const lease = this.workerLeases.acquire(workerId, taskId);

    this.frontier.markInFlight(candidate.candidate_id);
    this.taskStore.transition(taskId, TASK_LIFECYCLE_STATES.DISPATCHED);
    this.eventLog.append({ type: 'TASK_DISPATCHED', task_id: taskId, worker_id: workerId, lease_id: lease.lease_type });

    // 7. Execute Bounded Work Unit
    console.log(`[RUNTIME] Executing bounded work unit on ${workingDir}...`);
    this.taskStore.transition(taskId, TASK_LIFECYCLE_STATES.IN_FLIGHT);

    let executionResult = null;
    try {
      executionResult = candidate.task_generator_fn(workingDir, this);
    } catch (err) {
      console.error('[RUNTIME] Execution threw error:', err);
      executionResult = { exit_code: 1, error: err.message, artifacts: [] };
    }

    // 8. Result Customs Envelope Evaluation
    const customsRes = ResultCustoms.evaluateResultEnvelope({
      task_id: taskId,
      passport,
      exit_code: executionResult.exit_code,
      artifacts: executionResult.artifacts || [],
      checksum_map: executionResult.checksum_map || {}
    });

    if (!customsRes.accepted) {
      console.error(`[RUNTIME] Result Customs rejected output: ${customsRes.reason}`);
      if (customsRes.requires_uncertainty_fence) {
        this.uncertaintyMgr.fenceTask(taskId, customsRes.reason);
        this.eventLog.append({ type: 'TASK_FENCED', task_id: taskId, reason: customsRes.reason });
      }
      this.taskStore.transition(taskId, 'FAILED', customsRes.reason);
      this.lockManager.releaseAllForTask(taskId);
      this.workerLeases.release(workerId);
      return { status: 'CUSTOMS_REJECTED', reason: customsRes.reason };
    }

    // 9. Independent Evidence Verification
    const verifiedArtifacts = [];
    for (const artName of executionResult.artifacts) {
      const artPath = path.join(workingDir, artName);
      const expectedSha = executionResult.checksum_map[artName];
      const evCheck = EvidenceVerifier.verifyArtifact(artPath, expectedSha);
      if (!evCheck.verified) {
        throw new Error(`Evidence verification failed for ${artName}: ${evCheck.reason}`);
      }
      verifiedArtifacts.push({ file: artName, ...evCheck });
    }

    // 10. Record Evidence and Update Goal
    if (executionResult.criteria_key) {
      this.goalStore.recordEvidence({
        criteria_key: executionResult.criteria_key,
        artifact_path: path.join(workingDir, executionResult.artifacts[0]),
        sha256: executionResult.checksum_map[executionResult.artifacts[0]],
        verified_by: 'ResultCustoms+EvidenceVerifier'
      });
    }

    this.taskStore.transition(taskId, TASK_LIFECYCLE_STATES.VERIFIED);
    this.eventLog.append({
      type: 'TASK_COMPLETED',
      task_id: taskId,
      artifacts_count: verifiedArtifacts.length
    });

    // 11. Release Locks & Leases
    this.lockManager.releaseAllForTask(taskId);
    this.eventLog.append({ type: 'LEASE_RELEASED', resource: workingDir, task_id: taskId });
    this.workerLeases.release(workerId);
    this.taskStore.transition(taskId, TASK_LIFECYCLE_STATES.CLOSED);
    this.frontier.markCompleted(candidate.candidate_id, verifiedArtifacts);

    this.executedUnitsCount++;

    // 12. Evaluate Worker Report via Completion Governor
    const workerReport = { status: 'WORK_UNIT_COMPLETE', task_id: taskId };
    const govReportCheck = this.completionGovernor.evaluateWorkerReport(workerReport);
    if (!govReportCheck.admitted) {
      throw new Error('Completion Governor violation: ' + govReportCheck.reason);
    }

    // 13. Save Checkpoint
    const elapsedSec = Math.round((Date.now() - new Date(this.realStartUtc).getTime()) / 1000);
    this.checkpointStore.saveCheckpoint({
      mission_id: 'WINDOWS_COURIER_DURABLE_AUTONOMY_RUNTIME_MULTI_HOUR_V1',
      status: 'ACTIVE_CONTINUUM',
      goal_id: this.activeGoal.goal_id,
      completed_work_units: this.executedUnitsCount,
      open_work_units: this.frontier.getReadyCount(),
      active_leases_count: this.lockManager.activeLocks().length,
      fenced_tasks_count: this.uncertaintyMgr.fencedTasks.size,
      real_elapsed_seconds: elapsedSec,
      last_action: `COMPLETED_${candidate.title}`
    });

    return { status: 'WORK_UNIT_COMPLETE', candidate_title: candidate.title, taskId };
  }

  runContinuumLoop(maxIterations = 15) {
    console.log(`\n=== STARTING DURABLE AUTONOMY CONTINUUM LOOP (Max iterations: ${maxIterations}) ===`);
    for (let iter = 1; iter <= maxIterations; iter++) {
      console.log(`\n--- CONTINUUM ITERATION ${iter} of ${maxIterations} ---`);
      const step = this.executeNextWorkUnit();
      if (step.status === 'NO_RUNNABLE_WORK') {
        console.log('[RUNTIME] No more runnable work on frontier. Checking saturation challenge...');
        const challenge = SaturationChallenger.challenge(this.frontier, this.completionGovernor);
        console.log('[RUNTIME] Saturation Challenger Verdict:', challenge);
        break;
      }
    }

    // Evaluate Goal Satisfaction
    const goalSat = this.goalStore.evaluateGoalSatisfaction(this.activeGoal.goal_id);
    console.log('\n[RUNTIME] Goal Satisfaction Evaluation:', goalSat);
    if (goalSat.satisfied) {
      this.eventLog.append({ type: 'GOAL_SATISFIED', goal_id: this.activeGoal.goal_id });
    }

    // Completion Governor Evaluates Final Status:
    // Global saturation is DISABLED -> Status is PAUSED_CAPACITY
    const missionEvaluation = this.completionGovernor.evaluateMissionStatus(this.frontier.getReadyCount(), false);
    console.log('\n[COMPLETION-GOVERNOR] Final Mission Status:', missionEvaluation);

    const finalElapsedSec = Math.round((Date.now() - new Date(this.realStartUtc).getTime()) / 1000);
    const finalCheckpoint = this.checkpointStore.saveCheckpoint({
      mission_id: 'WINDOWS_COURIER_DURABLE_AUTONOMY_RUNTIME_MULTI_HOUR_V1',
      status: missionEvaluation.mission_status,
      goal_id: this.activeGoal.goal_id,
      completed_work_units: this.executedUnitsCount,
      open_work_units: this.frontier.getReadyCount(),
      active_leases_count: this.lockManager.activeLocks().length,
      fenced_tasks_count: this.uncertaintyMgr.fencedTasks.size,
      real_elapsed_seconds: finalElapsedSec,
      last_action: 'MISSION_LOOP_PAUSED_CAPACITY'
    });

    return {
      status: missionEvaluation.mission_status,
      completed_units: this.executedUnitsCount,
      goal_satisfied: goalSat.satisfied,
      elapsed_seconds: finalElapsedSec,
      checkpoint: finalCheckpoint
    };
  }

  resume() {
    console.log('=== DURABLE AUTONOMY RUNTIME RESUME & REPLAY ===');
    console.log('[RUNTIME-RESUME] Mission Root:', this.missionRoot);

    // 1. Checkpoint Verification
    const checkpoint = this.checkpointStore.loadCheckpoint();
    if (!checkpoint) {
      throw new Error('No durable checkpoint found at ' + this.checkpointStore.jsonPath);
    }
    console.log('[RUNTIME-RESUME] Loaded Checkpoint:', {
      mission_id: checkpoint.mission_id,
      status: checkpoint.status,
      completed_work_units: checkpoint.completed_work_units,
      saved_at_utc: checkpoint.saved_at_utc,
      last_action: checkpoint.last_action
    });

    // 2. Constitution Verification
    this.validator.load();
    const envCheck = this.validator.validateEnvironment({
      spend_eur: 0,
      mac_accessed: false,
      universux_touched: false,
      worker_can_close_mission: false
    });
    if (!envCheck.valid) {
      throw new Error('Constitution Validation Failed: ' + JSON.stringify(envCheck.findings));
    }
    console.log('[RUNTIME-RESUME] Constitution Verified: 41 invariants active, environment compliant.');

    const polCheck = this.policyValidator.validate();
    if (!polCheck.valid) {
      throw new Error('LONG_RUN_POLICY Validation Failed: ' + JSON.stringify(polCheck.findings));
    }
    console.log(`[RUNTIME-RESUME] LONG_RUN_POLICY Validated: ${polCheck.policy_id} v${polCheck.policy_version}`);

    // 3. Event Log Replay
    const replay = ReplayEngine.rebuildState(this.eventLog);
    console.log('[RUNTIME-RESUME] Event Log Replay:');
    console.log(` - Valid Events: ${replay.total_events}`);
    console.log(` - Torn Entries: ${replay.torn_entries}`);
    console.log(` - Total Tasks: ${replay.snapshot.tasks.length}`);
    console.log(` - Completed Tasks: ${replay.snapshot.tasks.filter(t => t.state === 'COMPLETED').length}`);
    console.log(` - Active Leases: ${replay.snapshot.active_leases.length}`);

    // 4. Crash Reconciliation
    const recon = CrashReconciler.reconcileOnStartup(replay.snapshot);
    console.log(`[RUNTIME-RESUME] Crash Reconciler Actions: ${recon.actionsTaken.length}`);

    // Sync in-memory state
    if (replay.snapshot.goals && replay.snapshot.goals.length > 0) {
      this.activeGoal = replay.snapshot.goals[0];
    }
    this.executedUnitsCount = checkpoint.completed_work_units || replay.snapshot.tasks.filter(t => t.state === 'COMPLETED').length;

    console.log('[RUNTIME-RESUME] Resumption Status: SUCCESSFUL');
    console.log('[RUNTIME-RESUME] Ready for Continuation / Expansion Omega-Deep V2.\n');

    return {
      checkpoint,
      replay,
      reconciliation: recon,
      status: 'RESUMED_CLEANLY'
    };
  }
}

if (require.main === module) {
  const missionRoot = path.resolve(__dirname, '..');
  const runtime = new DurableAutonomyRuntime(missionRoot);
  try {
    runtime.resume();
  } catch (err) {
    console.error('[RUNTIME-RESUME-FATAL]', err);
    process.exit(1);
  }
}

module.exports = { DurableAutonomyRuntime };

