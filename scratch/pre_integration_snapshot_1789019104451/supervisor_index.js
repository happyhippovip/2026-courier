// Courier Supervisor Plane P0 — Unified Interface
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
const { ProgressTracker, PROGRESS_EVIDENCE_TYPES } = require('./progress_tracker');
const { StallPolicy } = require('./stall_policy');
const { DiagnosticBundleManager } = require('./diagnostic_bundle');
const { ScreenshotSpec, SENSITIVE_UI_KEYWORDS } = require('./screenshot_spec');
const { DecisionEngine } = require('./decision_engine');
const { TaskHygiene } = require('./task_hygiene');
const { RestartReconciler } = require('./reconciliation');
const { MachineResourceGovernor } = require('./resource_governor');
const { NoStackingDetector } = require('./no_stacking');
const { ChiefEscalationEnvelope } = require('./chief_envelope');

class SupervisorPlane {
  constructor(runtimeDir = null) {
    this.runtimeDir = runtimeDir || path.join(__dirname, '..', 'runtime');

    this.auditLedger = new AuditLedger(path.join(this.runtimeDir, 'audit'));
    this.leaseManager = new ProcessLeaseManager(path.join(this.runtimeDir, 'leases'), this.auditLedger);
    this.progressTracker = new ProgressTracker(path.join(this.runtimeDir, 'leases'), this.leaseManager, this.auditLedger);
    this.stallPolicy = new StallPolicy();
    this.diagnosticManager = new DiagnosticBundleManager(path.join(this.runtimeDir, 'diagnostics'));
    this.decisionEngine = new DecisionEngine(this.stallPolicy);
    this.hygiene = new TaskHygiene(this.leaseManager, this.auditLedger);
    this.reconciler = new RestartReconciler(this.leaseManager, this.auditLedger);
    this.resourceGovernor = new MachineResourceGovernor();
    this.noStacking = new NoStackingDetector(this.leaseManager);
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
  StallPolicy,
  DiagnosticBundleManager,
  ScreenshotSpec,
  SENSITIVE_UI_KEYWORDS,
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
  EVENT_TYPE,
  THRESHOLDS,
  SAFETY_INVARIANTS,
  DEFAULT_MACHINE_CONCURRENCY
};
