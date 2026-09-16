'use strict';

const crypto = require('crypto');

/**
 * LegacyAdapter
 * Adapts historical RC3/V1 records to canonical V2 schema specifications.
 */
class LegacyAdapter {
  constructor() {
    this.statusMap = {
      'DONE': 'CLOSED_SUCCESS',
      'SUCCESS': 'CLOSED_SUCCESS',
      'ERROR': 'CLOSED_FAILED',
      'FAILED': 'CLOSED_FAILED',
      'RUNNING': 'IN_PROGRESS',
      'PENDING': 'READY',
      'READY': 'READY',
      'CANCELLED': 'CANCELLED'
    };
  }

  deriveLogicalWorkId(legacyRecord) {
    // Deterministic hash derived from stable legacy identity attributes
    const stableFields = {
      id: legacyRecord.id || legacyRecord.task_id || 'unknown',
      name: legacyRecord.name || legacyRecord.type || 'generic',
      created_at: legacyRecord.created_at || legacyRecord.timestamp || 0
    };
    return 'work_' + crypto.createHash('sha256').update(JSON.stringify(stableFields)).digest('hex').slice(0, 16);
  }

  adaptTaskRecord(legacyRecord) {
    if (!legacyRecord || typeof legacyRecord !== 'object') {
      throw new Error('Legacy record must be a valid object');
    }

    const taskId = legacyRecord.id || legacyRecord.task_id;
    if (!taskId) {
      throw new Error('Legacy record missing required task identifier (id/task_id)');
    }

    const legacyStatus = (legacyRecord.state || legacyRecord.status || 'PENDING').toUpperCase();
    const mappedStatus = this.statusMap[legacyStatus] || 'UNKNOWN_LEGACY';

    const logicalWorkId = legacyRecord.logical_work_id || this.deriveLogicalWorkId(legacyRecord);

    const adapted = {
      task_id: taskId,
      logical_work_id: logicalWorkId,
      goal_id: legacyRecord.goal_id || 'legacy_unassigned_goal',
      status: mappedStatus,
      schema_version: 2,
      migrated_from_legacy: true,
      original_legacy_state: legacyStatus,
      created_at_ms: legacyRecord.created_at ? new Date(legacyRecord.created_at).getTime() : Date.now(),
      proof_package: legacyRecord.proof_package || {
        assertions_run: mappedStatus === 'CLOSED_SUCCESS' ? 1 : 0,
        migrated_unverified: true
      },
      artifacts: Array.isArray(legacyRecord.artifacts) ? legacyRecord.artifacts : []
    };

    return adapted;
  }

  reconstructJournalHashChain(legacyJournalLines) {
    let prevHash = '0'.repeat(64);
    const chained = [];

    for (let i = 0; i < legacyJournalLines.length; i++) {
      const line = legacyJournalLines[i];
      const entry = typeof line === 'string' ? JSON.parse(line) : { ...line };

      entry.seq = i + 1;
      entry.prev_hash = prevHash;
      entry.schema_version = 2;

      const canonical = JSON.stringify({
        seq: entry.seq,
        prev_hash: entry.prev_hash,
        type: entry.type || 'LEGACY_EVENT',
        payload: entry.payload || {}
      });
      entry.entry_hash = crypto.createHash('sha256').update(canonical).digest('hex');
      prevHash = entry.entry_hash;

      chained.push(entry);
    }

    return chained;
  }
}

module.exports = { LegacyAdapter };
