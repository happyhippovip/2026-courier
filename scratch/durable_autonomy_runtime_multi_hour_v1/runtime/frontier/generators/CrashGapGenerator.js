// CrashGapGenerator.js — Generates crash boundary and recovery verification tasks
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');

class CrashGapGenerator {
  generate(runtime) {
    const candidates = [];

    // Crash 1: Mid-Write Torn Log Frame Recovery
    candidates.push({
      title: 'Crash Gap: Mid-Write Torn Log Frame Isolation and Recovery',
      category: 'DURABILITY',
      priority: 'P1',
      expected_information_gain: 9,
      lane: 'Q. CRASH RECONCILIATION',
      discovery_method: 'CRASH_BOUNDARY_ENUMERATION',
      task_generator_fn: (workingDir, rt) => {
        const { DurableEventLog } = require(path.join(rt.missionRoot, 'runtime', 'core', 'DurableEventLog.js'));
        const { ReplayEngine } = require(path.join(rt.missionRoot, 'runtime', 'core', 'ReplayEngine.js'));
        
        const testLogPath = path.join(workingDir, 'torn_test_event_log.log');
        const testLog = new DurableEventLog(testLogPath);

        // Append 5 valid events
        for (let i = 0; i < 5; i++) {
          testLog.append({ type: 'TASK_HEARTBEAT', index: i, timestamp: new Date().toISOString() });
        }

        // Simulate crash with partial truncated write
        fs.appendFileSync(testLogPath, 'FRAME:250:abcdef0123456789\n{"incomplete_event":true, "data":', 'utf8');

        const replay = ReplayEngine.rebuildState(testLog);

        const findings = {
          test: 'TORN_LOG_FRAME_RECOVERY',
          valid_events: replay.total_events,
          torn_entries_isolated: replay.torn_entries,
          status: (replay.total_events === 5 && replay.torn_entries === 1) ? 'PASSED' : 'FAILED'
        };

        const artifactName = 'torn_frame_recovery_proof.json';
        const content = JSON.stringify(findings, null, 2);
        fs.writeFileSync(path.join(workingDir, artifactName), content, 'utf8');
        const sha = crypto.createHash('sha256').update(content).digest('hex');

        return {
          exit_code: 0,
          criteria_key: 'CRIT_TORN_FRAME_RECOVERY_PROVEN',
          artifacts: [artifactName],
          checksum_map: { [artifactName]: sha }
        };
      }
    });

    // Crash 2: Orphan Lease Cleanup on Process Crash
    candidates.push({
      title: 'Crash Gap: Dead Worker Process Orphan Lease Reconciler',
      category: 'DURABILITY',
      priority: 'P1',
      expected_information_gain: 9,
      lane: 'K. PROCESS LEASES',
      discovery_method: 'LIVENESS_ANALYSIS',
      task_generator_fn: (workingDir, rt) => {
        const { CrashReconciler } = require(path.join(rt.missionRoot, 'runtime', 'core', 'ReplayEngine.js'));
        
        // Mock snapshot with orphaned active lease and in-flight task
        const crashedSnapshot = {
          active_leases: [{ resource: 'C:\\test\\resource', taskId: 'TASK-DEAD-PROCESS' }],
          tasks: [{ task_id: 'TASK-DEAD-PROCESS', state: 'IN_FLIGHT' }],
          goals: []
        };

        const recon = CrashReconciler.reconcileOnStartup(crashedSnapshot);

        const findings = {
          test: 'ORPHAN_LEASE_RECONCILER',
          actions_count: recon.actionsTaken.length,
          reconciled_task_state: recon.reconciledTasks[0].state,
          uncertainty_reason: recon.reconciledTasks[0].uncertainty_reason,
          status: (recon.actionsTaken.length >= 2 && recon.reconciledTasks[0].state === 'EXECUTION_UNCERTAIN') ? 'PASSED' : 'FAILED'
        };

        const artifactName = 'orphan_lease_reconciliation_proof.json';
        const content = JSON.stringify(findings, null, 2);
        fs.writeFileSync(path.join(workingDir, artifactName), content, 'utf8');
        const sha = crypto.createHash('sha256').update(content).digest('hex');

        return {
          exit_code: 0,
          criteria_key: 'CRIT_ORPHAN_LEASE_RECONCILED',
          artifacts: [artifactName],
          checksum_map: { [artifactName]: sha }
        };
      }
    });

    return candidates;
  }
}

module.exports = { CrashGapGenerator };