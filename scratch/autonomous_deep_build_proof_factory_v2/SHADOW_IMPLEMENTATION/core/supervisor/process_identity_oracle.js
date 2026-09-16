'use strict';

/**
 * SHADOW IMPLEMENTATION: PROCESS IDENTITY ORACLE (B01)
 * Component: shadow/core/supervisor/process_identity_oracle.js
 * Mission: WINDOWS_AUTONOMOUS_DEEP_BUILD_PROOF_FACTORY_V2
 */

class FatalProcessTerminationViolation extends Error {
  constructor(message, details = {}) {
    super(message);
    this.name = 'FatalProcessTerminationViolation';
    this.details = details;
  }
}

class ProcessIdentityOracle {
  constructor(options = {}) {
    this.allowUnknownKill = options.allowUnknownKill || false; // Dangerous mutant!
    this.disableStartTimeCheck = options.disableStartTimeCheck || false; // Dangerous mutant!
  }

  evaluateProcessIdentity(lease, osProcessInfo) {
    // lease: { pid, started_at_ms, task_token, machine_id, command_hash }
    // osProcessInfo: null (if dead), or { pid, start_time_ms, command_hash, permission_denied: boolean }

    if (!osProcessInfo) {
      return { verdict: 'MISMATCH', reason: 'Process does not exist in OS process table (dead)' };
    }

    if (osProcessInfo.permission_denied) {
      return { verdict: 'UNKNOWN', reason: 'OS permission denied while inspecting process metadata' };
    }

    if (osProcessInfo.pid !== lease.pid) {
      return { verdict: 'MISMATCH', reason: 'PID mismatch' };
    }

    // Windows PID Recycling Check
    if (!this.disableStartTimeCheck) {
      if (osProcessInfo.start_time_ms !== undefined && lease.started_at_ms !== undefined) {
        // If OS process started strictly after the lease was recorded, PID was recycled!
        if (osProcessInfo.start_time_ms > lease.started_at_ms + 2000) { // 2s clock skew tolerance
          return {
            verdict: 'MISMATCH',
            reason: `PID ${lease.pid} was recycled by OS. Lease started at ${lease.started_at_ms}, OS process started at ${osProcessInfo.start_time_ms}`
          };
        }
      } else {
        // Missing start-time metadata -> tri-state UNKNOWN
        return { verdict: 'UNKNOWN', reason: 'Process start-time metadata unavailable' };
      }
    }

    // Command hash check
    if (lease.command_hash && osProcessInfo.command_hash) {
      if (lease.command_hash !== osProcessInfo.command_hash) {
        return { verdict: 'MISMATCH', reason: 'Process command signature mismatch' };
      }
    }

    return { verdict: 'MATCH', reason: 'Verified exact PID and start-time identity match' };
  }

  safeTerminateProcess(lease, osProcessInfo, killerFn) {
    const evaluation = this.evaluateProcessIdentity(lease, osProcessInfo);

    if (evaluation.verdict === 'MATCH') {
      if (killerFn) {
        return killerFn(lease.pid);
      }
      return { terminated: true, pid: lease.pid, reason: 'MATCH identity verified' };
    }

    if (evaluation.verdict === 'UNKNOWN') {
      if (this.allowUnknownKill) {
        return { terminated: true, pid: lease.pid, status: 'MUTANT_DANGEROUS_UNKNOWN_KILL' };
      }
      throw new FatalProcessTerminationViolation(
        `[B01_PROCESS_IDENTITY_VIOLATION] Cannot kill PID ${lease.pid}: Identity verdict is UNKNOWN. Blind killing of unverified process is strictly forbidden.`,
        { lease, evaluation }
      );
    }

    // MISMATCH
    throw new FatalProcessTerminationViolation(
      `[B01_PROCESS_IDENTITY_VIOLATION] Refusing to kill PID ${lease.pid}: Identity verdict is MISMATCH (${evaluation.reason}). Target process is not owned by this lease!`,
      { lease, evaluation }
    );
  }
}

module.exports = {
  ProcessIdentityOracle,
  FatalProcessTerminationViolation
};
