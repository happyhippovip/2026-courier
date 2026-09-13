/**
 * crash_watchdog.js - Automated Zero-Telemetry Worker Crash Watchdog & Lease Revocation Engine
 * 
 * Invariants:
 * 1. Zero-Overhead Liveness Check: Uses Windows process.kill(pid, 0) / ESRCH detection.
 * 2. Immediate Orphan Lock Release: Revokes locks held by dead PIDs so independent work is never blocked.
 * 3. Zero-Loss Re-queueing: Reclaims abandoned tasks in WorkStealingPool back to PENDING.
 * 4. Audit Trail Integrity: Records structured crash autopsy and audit events without external network calls.
 * 5. Strictly maintains €0 autonomous spend.
 */

const fs = require('fs');
const path = require('path');
const { LEASE_STATUS, EVENT_TYPE } = require('./types');
const { ResourceLockManager } = require('../governance/ResourceLockManager');

class WorkerCrashWatchdog {
  constructor(options = {}) {
    this.leaseManager = options.leaseManager;
    this.lockManager = options.lockManager || new ResourceLockManager();
    this.workStealingPool = options.workStealingPool || null;
    this.auditLedger = options.auditLedger || null;
    this.heartbeatTimeoutMs = options.heartbeatTimeoutMs || 30000;

    this.crashHistory = [];
    this.totalCrashesDetected = 0;
    this.totalRecoveries = 0;
    this.lastAuditTime = null;
  }

  static isPidAlive(pid) {
    if (!pid || typeof pid !== 'number' || pid <= 0) return false;
    try {
      // Sending signal 0 tests process existence without terminating it
      process.kill(pid, 0);
      return true;
    } catch (err) {
      // EPERM means process exists but we lack permission -> process is definitely alive
      if (err.code === 'EPERM') return true;
      // ESRCH means process does not exist -> process is dead
      return false;
    }
  }

  reconcileCrashes() {
    this.lastAuditTime = new Date().toISOString();
    const results = {
      timestamp: this.lastAuditTime,
      scanned_leases: 0,
      active_leases: 0,
      dead_leases_reclaimed: [],
      recovered_tasks: [],
      evicted_workers: []
    };

    // 1. Scan Process Lease Manager if available
    if (this.leaseManager) {
      const allLeases = this.leaseManager.getAllLeases ? this.leaseManager.getAllLeases() : [];
      results.scanned_leases = allLeases.length;

      for (const lease of allLeases) {
        // Only inspect active or starting leases
        if (
          lease.status === LEASE_STATUS.STARTING ||
          lease.status === LEASE_STATUS.RUNNING ||
          lease.status === LEASE_STATUS.PROGRESSING
        ) {
          results.active_leases++;
          const pid = lease.pid;
          const alive = WorkerCrashWatchdog.isPidAlive(pid);

          if (!alive) {
            // Dead process detected!
            this.totalCrashesDetected++;
            const crashEvent = {
              lease_id: lease.process_lease_id,
              task_id: lease.task_id,
              dead_pid: pid,
              command: lease.command,
              detected_at: this.lastAuditTime,
              reason: 'PROCESS_UNEXPECTEDLY_EXITED'
            };

            this.crashHistory.push(crashEvent);
            results.dead_leases_reclaimed.push(crashEvent);

            // Update lease status
            this.leaseManager.updateStatus(
              lease.process_lease_id,
              LEASE_STATUS.TERMINATED,
              `Dead worker PID ${pid} detected by crash watchdog`
            );

            // Release any held resource locks
            if (this.lockManager) {
              this.lockManager.releaseAllForTask(lease.task_id);
            }

            // Audit ledger record
            if (this.auditLedger && this.auditLedger.recordEvent) {
              this.auditLedger.recordEvent({
                event_type: EVENT_TYPE.RECONCILIATION_CRASH_DETECTED || 'WORKER_CRASH_DETECTED',
                process_lease_id: lease.process_lease_id,
                details: crashEvent
              });
            }
          }
        }
      }
    }

    // 2. Scan Work Stealing Pool for abandoned or dead claims
    if (this.workStealingPool && this.workStealingPool.tasks) {
      const now = Date.now();
      for (const task of this.workStealingPool.tasks.values()) {
        if (task.status === 'CLAIMED') {
          // Check worker heartbeat or elapsed time
          const claimedAt = task.claimed_at ? new Date(task.claimed_at).getTime() : now;
          const elapsed = now - claimedAt;

          // Check if associated worker is dead
          let workerDead = false;
          if (task.claimed_by && this.workStealingPool.workers) {
            const w = this.workStealingPool.workers.get(task.claimed_by);
            if (w && w.pid) {
              workerDead = !WorkerCrashWatchdog.isPidAlive(w.pid);
            }
          }

          if (workerDead || elapsed > this.heartbeatTimeoutMs) {
            // Reclaim task back to PENDING
            this.lockManager.release(task.resource_path, task.task_id);
            task.status = 'PENDING';
            task.claimed_by = null;
            task.claimed_at = null;
            task.claim_token = null;
            task.abandoned_count = (task.abandoned_count || 0) + 1;
            this.totalRecoveries++;

            results.recovered_tasks.push({
              task_id: task.task_id,
              elapsed_ms: elapsed,
              recovered_at: this.lastAuditTime
            });
          }
        }
      }

      if (results.recovered_tasks.length > 0 && this.workStealingPool._persist) {
        this.workStealingPool._persist();
      }
    }

    return results;
  }

  getTelemetry() {
    return {
      healthy: true,
      last_audit_time: this.lastAuditTime,
      total_crashes_detected: this.totalCrashesDetected,
      total_recoveries: this.totalRecoveries,
      recent_crashes: this.crashHistory.slice(-10)
    };
  }
}

module.exports = {
  WorkerCrashWatchdog
};
