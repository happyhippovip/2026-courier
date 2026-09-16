'use strict';

/**
 * SHADOW IMPLEMENTATION: DETERMINISTIC REPLAY ENGINE
 * Component: shadow/core/journal/replay_engine.js
 * Mission: WINDOWS_AUTONOMOUS_DEEP_BUILD_PROOF_FACTORY_V2
 */

const fs = require('fs');
const path = require('path');
const crypto = require('crypto');

class ReplayCorruptionError extends Error {
  constructor(message, details = {}) {
    super(message);
    this.name = 'ReplayCorruptionError';
    this.details = details;
  }
}

class CourierReplayEngine {
  constructor(options = {}) {
    this.disableCheckpointValidation = options.disableCheckpointValidation || false;
    this.state = {
      lastSeq: 0,
      lastHash: '0000000000000000000000000000000000000000000000000000000000000000',
      goals: new Map(),
      tasks: new Map(),
      leases: new Map(),
      approvals: new Map(),
      followUps: new Map()
    };
  }

  applyEvent(entry) {
    const { seq, entry_hash, data } = entry;
    const { entityType, entityId, action, payload } = data;

    switch (entityType) {
      case 'GOAL': {
        if (!this.state.goals.has(entityId)) {
          this.state.goals.set(entityId, { id: entityId, status: 'CREATED', history: [] });
        }
        const goal = this.state.goals.get(entityId);
        goal.status = payload.status || goal.status;
        goal.history.push({ seq, action, payload });
        break;
      }
      case 'TASK': {
        if (!this.state.tasks.has(entityId)) {
          this.state.tasks.set(entityId, { id: entityId, status: 'CREATED', history: [] });
        }
        const task = this.state.tasks.get(entityId);
        if (action === 'STATUS_TRANSITION') {
          task.status = payload.to;
        }
        task.history.push({ seq, action, payload });
        break;
      }
      case 'LEASE': {
        if (action === 'ACQUIRED') {
          this.state.leases.set(entityId, { id: entityId, ...payload });
        } else if (action === 'RELEASED') {
          this.state.leases.delete(entityId);
        }
        break;
      }
      case 'APPROVAL': {
        this.state.approvals.set(entityId, { id: entityId, ...payload });
        break;
      }
      case 'FOLLOW_UP': {
        this.state.followUps.set(entityId, { id: entityId, ...payload });
        break;
      }
      default:
        // Generic event logging
        break;
    }

    this.state.lastSeq = seq;
    this.state.lastHash = entry_hash;
  }

  replayEvents(events) {
    for (const evt of events) {
      this.applyEvent(evt);
    }
    return this.getStateFingerprint();
  }

  getStateFingerprint() {
    const canonicalState = {
      lastSeq: this.state.lastSeq,
      lastHash: this.state.lastHash,
      goals: Array.from(this.state.goals.entries()).sort((a, b) => a[0].localeCompare(b[0])),
      tasks: Array.from(this.state.tasks.entries()).sort((a, b) => a[0].localeCompare(b[0])),
      leases: Array.from(this.state.leases.entries()).sort((a, b) => a[0].localeCompare(b[0])),
      approvals: Array.from(this.state.approvals.entries()).sort((a, b) => a[0].localeCompare(b[0])),
      followUps: Array.from(this.state.followUps.entries()).sort((a, b) => a[0].localeCompare(b[0]))
    };

    return crypto.createHash('sha256').update(JSON.stringify(canonicalState)).digest('hex');
  }

  createCheckpoint(checkpointFilePath) {
    const canonicalState = {
      lastSeq: this.state.lastSeq,
      lastHash: this.state.lastHash,
      goals: Object.fromEntries(this.state.goals),
      tasks: Object.fromEntries(this.state.tasks),
      leases: Object.fromEntries(this.state.leases),
      approvals: Object.fromEntries(this.state.approvals),
      followUps: Object.fromEntries(this.state.followUps)
    };

    const payload = JSON.stringify(canonicalState);
    const checksum = crypto.createHash('sha256').update(payload).digest('hex');

    const envelope = {
      version: 1,
      created_at: new Date().toISOString(),
      checksum,
      state: canonicalState
    };

    const tmpPath = checkpointFilePath + '.tmp';
    fs.writeFileSync(tmpPath, JSON.stringify(envelope, null, 2), 'utf8');
    fs.renameSync(tmpPath, checkpointFilePath);

    return { checksum, seq: this.state.lastSeq };
  }

  recoverFromCheckpointAndTail(checkpointFilePath, journal) {
    if (!fs.existsSync(checkpointFilePath)) {
      throw new Error(`Checkpoint not found: ${checkpointFilePath}`);
    }

    const envelope = JSON.parse(fs.readFileSync(checkpointFilePath, 'utf8'));
    const payload = JSON.stringify(envelope.state);
    const expectedChecksum = crypto.createHash('sha256').update(payload).digest('hex');

    if (!this.disableCheckpointValidation && envelope.checksum !== expectedChecksum) {
      throw new ReplayCorruptionError(
        `Checkpoint checksum mismatch: recorded ${envelope.checksum}, calculated ${expectedChecksum}`,
        { recorded: envelope.checksum, calculated: expectedChecksum }
      );
    }

    // Hydrate state from checkpoint
    const raw = envelope.state;
    this.state.lastSeq = raw.lastSeq;
    this.state.lastHash = raw.lastHash;
    this.state.goals = new Map(Object.entries(raw.goals));
    this.state.tasks = new Map(Object.entries(raw.tasks));
    this.state.leases = new Map(Object.entries(raw.leases));
    this.state.approvals = new Map(Object.entries(raw.approvals));
    this.state.followUps = new Map(Object.entries(raw.followUps));

    // Replay journal events occurring AFTER the checkpoint seq
    const allJournalEvents = journal.verifyAndLoad();
    const tailEvents = allJournalEvents.filter(e => e.seq > raw.lastSeq);

    for (const evt of tailEvents) {
      this.applyEvent(evt);
    }

    return {
      checkpointSeq: raw.lastSeq,
      tailEventsApplied: tailEvents.length,
      finalSeq: this.state.lastSeq,
      finalFingerprint: this.getStateFingerprint()
    };
  }
}

module.exports = {
  CourierReplayEngine,
  ReplayEngine: CourierReplayEngine,
  ReplayCorruptionError
};
