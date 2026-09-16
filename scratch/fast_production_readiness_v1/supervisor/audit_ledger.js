// Supervisor Audit Ledger — Append-Only Durable Event Stream
// Invariant: Historical events must never be rewritten or deleted.

const fs = require('fs');
const path = require('path');
const crypto = require('crypto');

class AuditLedger {
  constructor(storageDir = null) {
    this.storageDir = storageDir || path.join(__dirname, '..', 'runtime', 'audit');
    if (!fs.existsSync(this.storageDir)) {
      fs.mkdirSync(this.storageDir, { recursive: true });
    }
    this.eventsFile = path.join(this.storageDir, 'supervisor_events.jsonl');
  }

  recordEvent({
    task_id,
    task_version = 1,
    goal_id = null,
    worker_id = null,
    process_lease_id = null,
    machine_id = 'WINDOWS_LOCAL',
    event_type,
    previous_state = null,
    new_state = null,
    reason_codes = [],
    evidence_refs = [],
    decision = null
  }) {
    if (!event_type) {
      throw new Error('[AUDIT_ERROR] event_type is required');
    }

    const timestamp = new Date().toISOString();
    const eventId = `EVT-SUP-${Date.now()}-${crypto.randomBytes(3).toString('hex').toUpperCase()}`;

    const canonicalDecision = {
      event_id: eventId,
      timestamp,
      task_id,
      process_lease_id,
      event_type,
      decision,
      reason_codes
    };
    const decisionFingerprint = crypto
      .createHash('sha256')
      .update(JSON.stringify(canonicalDecision))
      .digest('hex');

    const eventRecord = {
      event_id: eventId,
      timestamp,
      task_id,
      task_version,
      goal_id,
      worker_id,
      process_lease_id,
      machine_id,
      event_type,
      previous_state,
      new_state,
      reason_codes,
      evidence_refs,
      decision,
      decision_fingerprint: decisionFingerprint
    };

    // Ensure newline separation if prior write crashed without trailing newline
    if (fs.existsSync(this.eventsFile)) {
      const stats = fs.statSync(this.eventsFile);
      if (stats.size > 0) {
        const fd = fs.openSync(this.eventsFile, 'r');
        const buf = Buffer.alloc(1);
        fs.readSync(fd, buf, 0, 1, stats.size - 1);
        fs.closeSync(fd);
        if (buf.toString('utf8') !== '\n') {
          fs.appendFileSync(this.eventsFile, '\n', 'utf8');
        }
      }
    }

    // Append-only write
    fs.appendFileSync(this.eventsFile, JSON.stringify(eventRecord) + '\n', 'utf8');

    return eventRecord;
  }

  getEvents(filterFn = null) {
    if (!fs.existsSync(this.eventsFile)) return [];
    const lines = fs.readFileSync(this.eventsFile, 'utf8').split('\n').filter(Boolean);
    const events = [];
    for (const line of lines) {
      try {
        events.push(JSON.parse(line));
      } catch (err) {
        // Trailing corruption recovery: skip incomplete/truncated lines from abrupt crash
      }
    }
    return filterFn ? events.filter(filterFn) : events;
  }

  getEventsForTask(taskId) {
    return this.getEvents(e => e.task_id === taskId);
  }

  getEventsForProcess(leaseId) {
    return this.getEvents(e => e.process_lease_id === leaseId);
  }
}

module.exports = {
  AuditLedger
};
