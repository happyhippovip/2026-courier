// Progress Evidence Tracker — Real Signal vs. Elapsed Time
// Invariant: Progress is based on verifiable evidence. A quiet process is NOT automatically hung.

const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const { EVENT_TYPE, LEASE_STATUS } = require('./types');

const PROGRESS_EVIDENCE_TYPES = Object.freeze({
  LOG_GROWTH: 'LOG_GROWTH',
  TEST_COMPLETION: 'TEST_COMPLETION',
  ARTIFACT_CREATION: 'ARTIFACT_CREATION',
  HEARTBEAT: 'HEARTBEAT',
  STATE_TRANSITION: 'STATE_TRANSITION',
  FILE_OUTPUT: 'FILE_OUTPUT',
  CPU_ACTIVITY: 'CPU_ACTIVITY',
  VERIFICATION_PROOF: 'VERIFICATION_PROOF',
  RESULT_FINGERPRINT: 'RESULT_FINGERPRINT',
  DURABLE_EVENT: 'DURABLE_EVENT'
});

class ProgressTracker {
  constructor(storageDir = null, leaseManager = null, auditLedger = null) {
    this.storageDir = storageDir || path.join(__dirname, '..', 'runtime', 'leases');
    if (!fs.existsSync(this.storageDir)) {
      fs.mkdirSync(this.storageDir, { recursive: true });
    }
    this.evidenceFile = path.join(this.storageDir, 'progress_evidence.jsonl');
    this.leaseManager = leaseManager;
    this.auditLedger = auditLedger;
    this.evidenceRecords = [];
    this._load();
  }

  _load() {
    if (fs.existsSync(this.evidenceFile)) {
      try {
        const lines = fs.readFileSync(this.evidenceFile, 'utf8').split('\n').filter(Boolean);
        this.evidenceRecords = lines.map(l => JSON.parse(l));
      } catch (err) {
        console.error(`[PROGRESS_TRACKER] Warning loading ${this.evidenceFile}:`, err.message);
      }
    }
  }

  recordProgress({
    process_lease_id,
    task_id,
    evidence_type,
    value,
    source = 'LOCAL_MONITOR'
  }) {
    if (!process_lease_id || !task_id || !evidence_type) {
      throw new Error('[PROGRESS_ERROR] process_lease_id, task_id, and evidence_type are required');
    }

    const timestamp = new Date().toISOString();
    const evidenceId = `EVD-${Date.now()}-${crypto.randomBytes(3).toString('hex').toUpperCase()}`;
    const fpRaw = `${process_lease_id}:${task_id}:${evidence_type}:${JSON.stringify(value)}:${timestamp}`;
    const fingerprint = crypto.createHash('sha256').update(fpRaw).digest('hex');

    const entry = {
      evidence_id: evidenceId,
      process_lease_id,
      task_id,
      timestamp,
      evidence_type,
      value,
      source,
      fingerprint
    };

    this.evidenceRecords.push(entry);
    fs.appendFileSync(this.evidenceFile, JSON.stringify(entry) + '\n', 'utf8');

    // Update lease last_progress_at and status
    if (this.leaseManager) {
      const lease = this.leaseManager.getLease(process_lease_id);
      if (lease) {
        lease.last_progress_at = timestamp;
        if (lease.status === LEASE_STATUS.STARTING || lease.status === LEASE_STATUS.RUNNING || lease.status === LEASE_STATUS.STALLED) {
          this.leaseManager.updateStatus(process_lease_id, LEASE_STATUS.PROGRESSING, `Progress confirmed via ${evidence_type}`);
        } else {
          this.leaseManager._persist();
        }
      }
    }

    if (this.auditLedger) {
      this.auditLedger.recordEvent({
        task_id,
        process_lease_id,
        event_type: EVENT_TYPE.PROGRESS_OBSERVED,
        evidence_refs: [evidenceId],
        reason_codes: [evidence_type]
      });
    }

    return entry;
  }

  getEvidenceForProcess(leaseId) {
    return this.evidenceRecords.filter(e => e.process_lease_id === leaseId);
  }

  getLatestProgressForProcess(leaseId) {
    const list = this.getEvidenceForProcess(leaseId);
    return list.length > 0 ? list[list.length - 1] : null;
  }
}

module.exports = {
  PROGRESS_EVIDENCE_TYPES,
  ProgressTracker
};
