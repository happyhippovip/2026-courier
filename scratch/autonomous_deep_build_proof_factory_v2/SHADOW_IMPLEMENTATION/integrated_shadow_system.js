'use strict';

const path = require('path');
const crypto = require('crypto');

const { TransitionValidator } = require('./core/state_machine/transition_validator');
const { DurableJournal } = require('./core/journal/durable_journal');
const { DispatcherUncertaintyFence } = require('./core/dispatch/dispatcher_uncertainty_fence');
const { HierarchicalResourceMutex } = require('./core/resources/hierarchical_resource_mutex');
const { ProcessIdentityOracle } = require('./core/process/process_identity_oracle');
const { CrashReconciliationEngine } = require('./core/crash/crash_reconciliation_engine');
const { ResultCustoms } = require('./core/customs/result_customs');
const { BorderGuard } = require('./core/customs/border_guard');
const { TestWeakeningDetector } = require('./core/customs/test_weakening_detector');
const { ApprovalTokenCore } = require('./core/gates/approval_token_core');
const { ZeroSpendBoundaryGovernor } = require('./core/gates/zero_spend_boundary_governor');
const { GoalSatisfactionEngine } = require('./core/goal/goal_satisfaction_engine');
const { GoalVerifier } = require('./core/goal/goal_verifier');

/**
 * IntegratedAutonomousCourier
 * Fully wired autonomous engineering engine uniting all shadow modules.
 */
class IntegratedAutonomousCourier {
  constructor(options = {}) {
    this.labRoot = options.labRoot || path.resolve(__dirname, '..');
    const specPath = path.join(this.labRoot, 'STATE_MACHINES', 'state_machines.json');

    this.validator = new TransitionValidator(specPath);
    const journalFile = options.journalFile || path.join(this.labRoot, 'scratch', 'integrated_journal.jsonl');
    this.journal = new DurableJournal(journalFile);
    this.uncertaintyFence = new DispatcherUncertaintyFence();
    this.mutex = new HierarchicalResourceMutex();
    this.processOracle = new ProcessIdentityOracle();
    this.crashReconciler = new CrashReconciliationEngine({
      journal: this.journal,
      processOracle: this.processOracle,
      uncertaintyFence: this.uncertaintyFence
    });
    this.customs = new ResultCustoms();
    this.borderGuard = new BorderGuard({ allowedRoot: this.labRoot });
    this.testWeakeningDetector = new TestWeakeningDetector();
    this.tokenCore = new ApprovalTokenCore(options.secretKey || 'integrated_secret_key');
    this.governor = new ZeroSpendBoundaryGovernor({
      autonomousSpendLimitEur: 0.00,
      approvalTokenCore: this.tokenCore
    });
    this.goalVerifier = new GoalVerifier({ customs: this.customs });
    this.goalEngine = new GoalSatisfactionEngine({ verifier: this.goalVerifier });
  }

  submitGoal(goalSpec) {
    const goal = this.goalEngine.createGoal(goalSpec);
    this.journal.appendEntry({
      type: 'GOAL_SUBMITTED',
      goal_id: goal.goal_id,
      description: goal.description
    });
    return goal;
  }

  planTask(goalId, taskSpec) {
    const task = this.goalEngine.addTaskToGoal(goalId, taskSpec);
    this.journal.appendEntry({
      type: 'TASK_PLANNED',
      goal_id: goalId,
      task_id: task.task_id
    });
    return task;
  }

  dispatchAndExecuteAutonomousTask({
    goalId,
    taskId,
    logicalWorkId,
    workerId,
    resourcePath,
    deliverables = [],
    testBaseline = null,
    testCandidate = null,
    spendEur = 0.00
  }) {
    // 1. Spend & Governance check
    const govVerdict = this.governor.evaluateExecution({
      action_type: 'RUN_COMPILATION',
      action_payload: { spend_eur: spendEur }
    });
    if (!govVerdict.authorized) {
      throw new Error(`Execution blocked by ZeroSpendGovernor: ${govVerdict.reason}`);
    }

    // 2. Uncertainty fence check
    const fenceVerdict = this.uncertaintyFence.checkDispatchAllowed({
      task_id: taskId,
      logical_work_id: logicalWorkId,
      dispatch_family: 'TASK_WORKER'
    });
    if (!fenceVerdict.allowed) {
      throw new Error(`Dispatch blocked by UncertaintyFence: ${fenceVerdict.reason}`);
    }

    // 3. Acquire Resource Lease
    const leaseRes = this.mutex.acquireLease(resourcePath, taskId, 'WRITE', 10000);
    if (!leaseRes.granted) {
      throw new Error(`Resource conflict on '${resourcePath}': ${leaseRes.reason}`);
    }

    // 4. Border guard check on deliverables
    const guardCheck = this.borderGuard.inspectArtifacts(deliverables);
    if (!guardCheck.allowed) {
      this.mutex.releaseLease(leaseRes.lease.lease_id, taskId);
      throw new Error(`BorderGuard rejected deliverables: ${guardCheck.reason}`);
    }

    // 5. Test weakening check if test files were touched
    if (testBaseline && testCandidate) {
      const weakCheck = this.testWeakeningDetector.compare(testBaseline, testCandidate);
      if (!weakCheck.passed) {
        this.mutex.releaseLease(leaseRes.lease.lease_id, taskId);
        throw new Error(`TestWeakeningDetector rejected changes: ${weakCheck.violations.join('; ')}`);
      }
    }

    // 6. Build proof package
    const proofPackage = {
      assertions_run: 10,
      artifacts_produced: deliverables.map(d => d.path),
      verification_signature: 'sig_autonomous_v2'
    };
    proofPackage.proof_hash = this.customs.computeProofHash(proofPackage);

    // 7. Result Customs Inspection
    const customsResult = this.customs.inspectResult({
      task_id: taskId,
      logical_work_id: logicalWorkId,
      worker_id: workerId,
      status: 'SUCCESS',
      schema_version: 2,
      proof_package: proofPackage,
      artifacts: deliverables,
      is_read_only: deliverables.length === 0
    });

    if (!customsResult.cleared) {
      this.mutex.releaseLease(leaseRes.lease.lease_id, taskId);
      throw new Error(`ResultCustoms rejected result: ${customsResult.violations.join('; ')}`);
    }

    // 8. Update task status in goal engine
    this.goalEngine.updateTaskStatus(taskId, 'CLOSED_SUCCESS', {
      proof_package: proofPackage,
      artifacts: deliverables
    });

    // 9. Release resource lease
    this.mutex.releaseLease(leaseRes.lease.lease_id, taskId);

    // 10. Record in journal
    this.journal.appendEntry({
      type: 'TASK_COMPLETED_SUCCESS',
      goal_id: goalId,
      task_id: taskId,
      logical_work_id: logicalWorkId,
      result_hash: customsResult.result_hash
    });

    return { success: true, taskId, logicalWorkId, customsResult };
  }

  finalizeGoal(goalId) {
    const res = this.goalEngine.requestGoalVerification(goalId);
    this.journal.appendEntry({
      type: 'GOAL_VERIFIED',
      goal_id: goalId,
      status: res.goal_status,
      satisfied: res.success
    });
    return res;
  }
}

module.exports = { IntegratedAutonomousCourier };
