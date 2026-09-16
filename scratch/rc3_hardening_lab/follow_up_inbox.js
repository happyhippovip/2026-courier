/**
 * FOLLOW-UP INBOX MODEL (ISOLATED LAB)
 * 
 * Append-only follow-up inbox for preserving user/worker ideas during execution.
 * Enforces:
 * - 11 canonical fields:
 *   follow_up_id, created_at, source, goal_id, related_task_id, worker_id, thought, reason, priority, dependency, status
 * - 8 canonical statuses:
 *   CAPTURED, NEEDS_DISCUSSION, CANDIDATE, APPROVED_NEXT, MERGED, SUPERSEDED, REJECTED, DISPATCHED
 * - Append-only persistence; history never deleted.
 * - Merge & Supersede preserve historical records and provenance.
 * - In-flight non-disruption: Ideas captured while worker busy are held, NOT automatically dispatched.
 * - Duplicate thought recognition without history destruction.
 */

const fs = require('fs');
const path = require('path');
const crypto = require('crypto');

const FOLLOW_UP_STATUS = Object.freeze({
  CAPTURED: 'CAPTURED',
  NEEDS_DISCUSSION: 'NEEDS_DISCUSSION',
  CANDIDATE: 'CANDIDATE',
  APPROVED_NEXT: 'APPROVED_NEXT',
  MERGED: 'MERGED',
  SUPERSEDED: 'SUPERSEDED',
  REJECTED: 'REJECTED',
  DISPATCHED: 'DISPATCHED'
});

const VALID_STATUS_TRANSITIONS = {
  [FOLLOW_UP_STATUS.CAPTURED]: [
    FOLLOW_UP_STATUS.NEEDS_DISCUSSION,
    FOLLOW_UP_STATUS.CANDIDATE,
    FOLLOW_UP_STATUS.SUPERSEDED,
    FOLLOW_UP_STATUS.REJECTED
  ],
  [FOLLOW_UP_STATUS.NEEDS_DISCUSSION]: [
    FOLLOW_UP_STATUS.CANDIDATE,
    FOLLOW_UP_STATUS.SUPERSEDED,
    FOLLOW_UP_STATUS.REJECTED
  ],
  [FOLLOW_UP_STATUS.CANDIDATE]: [
    FOLLOW_UP_STATUS.APPROVED_NEXT,
    FOLLOW_UP_STATUS.MERGED,
    FOLLOW_UP_STATUS.SUPERSEDED,
    FOLLOW_UP_STATUS.REJECTED
  ],
  [FOLLOW_UP_STATUS.APPROVED_NEXT]: [
    FOLLOW_UP_STATUS.DISPATCHED,
    FOLLOW_UP_STATUS.MERGED,
    FOLLOW_UP_STATUS.SUPERSEDED,
    FOLLOW_UP_STATUS.REJECTED
  ],
  [FOLLOW_UP_STATUS.MERGED]: [],
  [FOLLOW_UP_STATUS.SUPERSEDED]: [],
  [FOLLOW_UP_STATUS.REJECTED]: [],
  [FOLLOW_UP_STATUS.DISPATCHED]: []
};

class FollowUpInbox {
  constructor(storageDir = null) {
    this.storageDir = storageDir || path.join(__dirname, '..', 'runtime', 'follow_up');
    if (!fs.existsSync(this.storageDir)) {
      fs.mkdirSync(this.storageDir, { recursive: true });
    }
    this.ledgerPath = path.join(this.storageDir, 'follow_up_inbox.jsonl');
    this.items = new Map(); // id -> latest item
    this.thoughtIndex = new Map(); // thought_fingerprint -> Array of item IDs
    this._load();
  }

  static computeThoughtFingerprint(goal_id, thought) {
    const norm = `${goal_id}:${(thought || '').trim().toLowerCase()}`;
    return crypto.createHash('sha256').update(norm).digest('hex');
  }

  _load() {
    if (fs.existsSync(this.ledgerPath)) {
      try {
        const raw = fs.readFileSync(this.ledgerPath, 'utf8');
        const lines = raw.split('\n').map(l => l.trim()).filter(Boolean);
        for (const line of lines) {
          let entry;
          try {
            entry = JSON.parse(line);
          } catch (lineErr) {
            continue; // Trailing corruption recovery: skip truncated line
          }
          if (entry.event === 'STATUS_TRANSITION') {
            const existing = this.items.get(entry.follow_up_id);
            if (existing) {
              existing.status = entry.to_status;
              existing.status_meta = entry.meta;
              existing.updated_at = entry.timestamp;
            }
          } else if (entry.event === 'ITEM_MERGED') {
            const target = this.items.get(entry.target_id);
            const source = this.items.get(entry.source_id);
            if (target && source) {
              if (!target.merged_sources) target.merged_sources = [];
              target.merged_sources.push({
                source_id: entry.source_id,
                source_thought: source.thought,
                source_created_at: source.created_at,
                merged_at: entry.timestamp
              });
            }
          } else if (entry.follow_up_id) {
            this.items.set(entry.follow_up_id, entry);
            const fp = FollowUpInbox.computeThoughtFingerprint(entry.goal_id, entry.thought);
            if (!this.thoughtIndex.has(fp)) {
              this.thoughtIndex.set(fp, []);
            }
            if (!this.thoughtIndex.get(fp).includes(entry.follow_up_id)) {
              this.thoughtIndex.get(fp).push(entry.follow_up_id);
            }
          }
        }
      } catch (err) {
        console.error(`[INBOX_ERROR] Could not load ${this.ledgerPath}:`, err.message);
      }
    }
  }

  captureIdea({
    source = 'USER',
    goal_id,
    related_task_id = null,
    worker_id = null,
    thought,
    reason = '',
    priority = 'MEDIUM',
    dependency = null
  }) {
    if (!goal_id) throw new Error('[INBOX_ERROR] goal_id is required');
    if (!thought || !thought.trim()) throw new Error('[INBOX_ERROR] thought is required');

    const timestamp = new Date().toISOString();
    const follow_up_id = `FUP-${Date.now()}-${crypto.randomBytes(3).toString('hex').toUpperCase()}`;
    const thought_fp = FollowUpInbox.computeThoughtFingerprint(goal_id, thought);

    const existingDuplicates = this.thoughtIndex.get(thought_fp) || [];
    const isDuplicate = existingDuplicates.length > 0;

    const item = {
      follow_up_id,
      created_at: timestamp,
      source,
      goal_id,
      related_task_id,
      worker_id,
      thought: thought.trim(),
      reason: reason.trim(),
      priority,
      dependency,
      status: FOLLOW_UP_STATUS.CAPTURED,
      is_duplicate: isDuplicate,
      prior_duplicate_ids: existingDuplicates.slice(),
      provenance: {
        captured_during_task: related_task_id,
        worker_busy: !!related_task_id
      },
      updated_at: timestamp
    };

    this.items.set(follow_up_id, item);
    if (!this.thoughtIndex.has(thought_fp)) {
      this.thoughtIndex.set(thought_fp, []);
    }
    this.thoughtIndex.get(thought_fp).push(follow_up_id);

    this._appendLedger(item);
    return item;
  }

  transition(followUpId, targetStatus, meta = {}) {
    const item = this.items.get(followUpId);
    if (!item) throw new Error(`[INBOX_ERROR] Item ${followUpId} not found`);

    const allowed = VALID_STATUS_TRANSITIONS[item.status] || [];
    if (!allowed.includes(targetStatus)) {
      throw new Error(`[INBOX_TRANSITION_ERROR] Cannot transition ${followUpId} from ${item.status} to ${targetStatus}`);
    }

    const prevStatus = item.status;
    item.status = targetStatus;
    item.updated_at = new Date().toISOString();
    item.status_meta = meta;

    this._appendLedger({
      event: 'STATUS_TRANSITION',
      follow_up_id: followUpId,
      from_status: prevStatus,
      to_status: targetStatus,
      timestamp: item.updated_at,
      meta
    });

    return item;
  }

  merge(sourceId, targetId, reason = 'MERGED_INTO_TARGET') {
    const source = this.items.get(sourceId);
    const target = this.items.get(targetId);
    if (!source || !target) throw new Error('[INBOX_ERROR] Source or Target item not found');

    // Merge preserves provenance: records targetId in source, and sourceId in target's merged_from
    this.transition(sourceId, FOLLOW_UP_STATUS.MERGED, { merged_into: targetId, reason });

    if (!target.merged_sources) target.merged_sources = [];
    target.merged_sources.push({
      source_id: sourceId,
      source_thought: source.thought,
      source_created_at: source.created_at,
      merged_at: new Date().toISOString()
    });
    this.items.set(targetId, target);

    this._appendLedger({
      event: 'ITEM_MERGED',
      source_id: sourceId,
      target_id: targetId,
      timestamp: new Date().toISOString()
    });

    return { source, target };
  }

  supersede(oldId, newId, reason = 'SUPERSEDED_BY_NEWER_ITEM') {
    const oldItem = this.items.get(oldId);
    if (!oldItem) throw new Error(`[INBOX_ERROR] Item ${oldId} not found`);

    this.transition(oldId, FOLLOW_UP_STATUS.SUPERSEDED, { superseded_by: newId, reason });
    return oldItem;
  }

  getItem(followUpId) {
    return this.items.get(followUpId) || null;
  }

  listAll() {
    return Array.from(this.items.values());
  }

  listByStatus(status) {
    return Array.from(this.items.values()).filter(i => i.status === status);
  }

  _appendLedger(entry) {
    if (fs.existsSync(this.ledgerPath)) {
      const stats = fs.statSync(this.ledgerPath);
      if (stats.size > 0) {
        const fd = fs.openSync(this.ledgerPath, 'r');
        const buf = Buffer.alloc(1);
        fs.readSync(fd, buf, 0, 1, stats.size - 1);
        fs.closeSync(fd);
        if (buf.toString('utf8') !== '\n') {
          fs.appendFileSync(this.ledgerPath, '\n', 'utf8');
        }
      }
    }
    fs.appendFileSync(this.ledgerPath, JSON.stringify(entry) + '\n', 'utf8');
  }
}

module.exports = {
  FOLLOW_UP_STATUS,
  FollowUpInbox
};
