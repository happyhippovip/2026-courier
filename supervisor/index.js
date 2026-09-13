// Courier Supervisor Plane P0 — Unified Interface with Hardened Production Gates
// Architectural Invariant:
// This is NOT a second Courier. It is a SUPERVISOR PLANE used by Courier.
// Courier remains the ONLY canonical orchestrator.

const path = require('path');
const {
  LEASE_STATUS,
  SUPERVISOR_DECISION,
  RESOURCE_STATE,
  RESOURCE_ACTION,
  EVENT_TYPE,
  THRESHOLDS,
  SAFETY_INVARIANTS,
  DEFAULT_MACHINE_CONCURRENCY
} = require('./types');

const { AuditLedger } = require('./audit_ledger');
const { ProcessLeaseManager } = require('./lease_manager');
const { ProgressTracker, PROGRESS_EVIDENCE_TYPES, ResultCustoms, EvidenceVerifier } = require('./progress_tracker');
const { StallPolicy } = require('./stall_policy');
const { DiagnosticBundleManager } = require('./diagnostic_bundle');
const { ScreenshotSpec, SENSITIVE_UI_KEYWORDS } = require('./screenshot_spec');
const { DecisionEngine, BorderGuard, TaskPassport, CompletionGovernor } = require('./decision_engine');
const { TaskHygiene } = require('./task_hygiene');
const { RestartReconciler } = require('./reconciliation');
const { MachineResourceGovernor } = require('./resource_governor');
const { NoStackingDetector, ResourceLockManager } = require('./no_stacking');
const { ChiefEscalationEnvelope } = require('./chief_envelope');
const { WorkStealingPool } = require('./work_stealing');

class SupervisorPlane {
  constructor(runtimeDir = null) {
    this.runtimeDir = runtimeDir || path.join(__dirname, '..', 'runtime');

    this.auditLedger = new AuditLedger(path.join(this.runtimeDir, 'audit'));
    this.leaseManager = new ProcessLeaseManager(path.join(this.runtimeDir, 'leases'), this.auditLedger);
    this.noStacking = new NoStackingDetector(this.leaseManager);
    this.lockManager = this.noStacking.lockManager;
    this.workStealingPool = new WorkStealingPool({
      storageDir: path.join(this.runtimeDir, 'work_stealing'),
      lockManager: this.lockManager
    });

    this.progressTracker = new ProgressTracker(path.join(this.runtimeDir, 'leases'), this.leaseManager, this.auditLedger);
    this.stallPolicy = new StallPolicy();
    this.diagnosticManager = new DiagnosticBundleManager(path.join(this.runtimeDir, 'diagnostics'));
    this.decisionEngine = new DecisionEngine(this.stallPolicy, this.lockManager);
    this.hygiene = new TaskHygiene(this.leaseManager, this.auditLedger);
    this.reconciler = new RestartReconciler(this.leaseManager, this.auditLedger);
    this.resourceGovernor = new MachineResourceGovernor();
    this.completionGovernor = this.decisionEngine.completionGovernor;
  }

  // Pre-Dispatch Choke Point (GAP-004: BorderGuard Check)
  admitForDispatch(task, passport) {
    return this.decisionEngine.evaluatePreDispatchAdmission(task, passport, this.lockManager);
  }

  // Result Intake Choke Point (GAP-005: ResultCustoms Check)
  evaluateResultEnvelope(params) {
    return this.progressTracker.evaluateAndRecordResultEnvelope(params);
  }

  // Worker Report Admission (GAP-003: Worker Completion Revocation)
  evaluateWorkerReport(workerReport) {
    return this.decisionEngine.evaluateWorkerReport(workerReport);
  }

  // Process Identity Verification (GAP-002: PID + StartTime + TaskToken)
  verifyProcessIdentity(pid, expectedStartTimeEpoch = null, expectedTaskToken = null) {
    return this.leaseManager.verifyProcessIdentity(pid, expectedStartTimeEpoch, expectedTaskToken);
  }

  // Safe Termination (GAP-002: Fail-closed on unverified identity)
  safeTerminateProcess(leaseId, expectedToken = null) {
    return this.leaseManager.safeTerminateProcess(leaseId, expectedToken);
  }

  // Safety audit
  getSafetyInvariants() {
    return { ...SAFETY_INVARIANTS };
  }
}

module.exports = {
  SupervisorPlane,
  AuditLedger,
  ProcessLeaseManager,
  ProgressTracker,
  PROGRESS_EVIDENCE_TYPES,
  ResultCustoms,
  EvidenceVerifier,
  StallPolicy,
  DiagnosticBundleManager,
  ScreenshotSpec,
  SENSITIVE_UI_KEYWORDS,
  DecisionEngine,
  BorderGuard,
  TaskPassport,
  CompletionGovernor,
  TaskHygiene,
  RestartReconciler,
  MachineResourceGovernor,
  NoStackingDetector,
  ResourceLockManager,
  ChiefEscalationEnvelope,
  WorkStealingPool,
  LEASE_STATUS,
  SUPERVISOR_DECISION,
  RESOURCE_STATE,
  RESOURCE_ACTION,
  EVENT_TYPE,
  THRESHOLDS,
  SAFETY_INVARIANTS,
  DEFAULT_MACHINE_CONCURRENCY
};