// Supervisor Plane Compatibility Layer
// Invariant: Courier remains the ONLY canonical orchestrator.
// This module provides compatibility wrappers ensuring economic experiments can attach to
// Supervisor Plane leases, progress tracking, stall detection, and hygiene without duplicating orchestrator roles.

class SupervisorCompatibility {
  static createEconomicWorkEnvelope({
    goal_id = 'GOAL-ECONOMIC-FIRST-5-EURO',
    task_id,
    task_version = 1,
    worker_id = 'WORKER-WINDOWS-ECONOMIC',
    machine_id = 'WINDOWS_WORKER',
    experiment_id = null,
    opportunity_id = null,
    process_lease_id = null,
    evidence_refs = []
  }) {
    if (!task_id) throw new Error('[SUPERVISOR_COMPAT_ERROR] task_id is required');

    return {
      goal_id,
      task_id,
      task_version,
      worker_id,
      machine_id,
      experiment_id,
      opportunity_id,
      process_lease_id: process_lease_id || 'PENDING_LEASE_ACQUISITION',
      evidence_refs: Array.isArray(evidence_refs) ? evidence_refs : [],
      created_at: new Date().toISOString(),
      compatibility_version: 'P0_COMPATIBLE',
      runtime_hooks: {
        supports_process_lease: true,
        supports_progress_evidence: true,
        supports_stall_detection: true,
        supports_resource_governor: true,
        supports_diagnostic_bundle: true,
        supports_task_hygiene: true
      }
    };
  }

  static wrapEconomicTask({
    goal_id = 'GOAL-ECONOMIC-FIRST-5-EURO',
    task_id,
    task_version = 1,
    worker_id = 'WORKER-WINDOWS-ECONOMIC',
    machine_id = 'WINDOWS_WORKER',
    experiment_id = null,
    opportunity_id = null,
    process_lease_id = null,
    evidence_refs = [],
    payload = {}
  }) {
    const env = this.createEconomicWorkEnvelope({
      goal_id,
      task_id,
      task_version,
      worker_id,
      machine_id,
      experiment_id,
      opportunity_id: opportunity_id || (payload && payload.opportunity_id),
      process_lease_id,
      evidence_refs
    });
    return {
      supervisor_envelope_version: 'v1',
      ...env,
      payload
    };
  }

  static bindProcessLease(envelope, processLease) {
    if (!envelope || !processLease) {
      throw new Error('[SUPERVISOR_COMPAT_ERROR] envelope and processLease are required');
    }
    return {
      ...envelope,
      process_lease_id: processLease.process_lease_id,
      bound_pid: processLease.pid,
      command: processLease.command,
      bound_at: new Date().toISOString()
    };
  }
}

module.exports = {
  SupervisorCompatibility
};
