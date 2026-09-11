/**
 * state_checkpointer.js - Multi-Agent Context State Checkpointer & Delta Replay Daemon
 * Captures, diffs, and replays progressive context window snapshots across agent turns.
 */
const crypto = require('crypto');

class ContextStateCheckpointer {
  constructor(options = {}) {
    this.snapshots = [];
    this.maxSnapshots = options.maxSnapshots || 50;
  }

  hashContent(content) {
    return crypto.createHash('sha256').update(content || '').digest('hex').slice(0, 12);
  }

  recordSnapshot(agentId, promptText, turnIndex = 0) {
    const hash = this.hashContent(promptText);
    const charCount = (promptText || '').length;

    let deltaCharCount = 0;
    if (this.snapshots.length > 0) {
      const prev = this.snapshots[this.snapshots.length - 1];
      deltaCharCount = charCount - prev.charCount;
    }

    const snapshot = {
      snapshotId: 'SNAP_' + (this.snapshots.length + 1).toString().padStart(3, '0'),
      agentId,
      turnIndex,
      hash,
      charCount,
      deltaCharCount,
      timestamp: new Date().toISOString(),
      content: promptText
    };

    this.snapshots.push(snapshot);
    if (this.snapshots.length > this.maxSnapshots) {
      this.snapshots.shift();
    }

    return {
      snapshotId: snapshot.snapshotId,
      agentId: snapshot.agentId,
      hash: snapshot.hash,
      charCount: snapshot.charCount,
      deltaCharCount: snapshot.deltaCharCount,
      totalRecorded: this.snapshots.length
    };
  }

  getSnapshot(snapshotId) {
    return this.snapshots.find(s => s.snapshotId === snapshotId) || null;
  }

  replayTo(snapshotId) {
    const idx = this.snapshots.findIndex(s => s.snapshotId === snapshotId);
    if (idx === -1) {
      return { success: false, error: 'Snapshot not found: ' + snapshotId };
    }

    const target = this.snapshots[idx];
    // Rollback: prune subsequent snapshots
    const removedCount = this.snapshots.length - 1 - idx;
    this.snapshots = this.snapshots.slice(0, idx + 1);

    return {
      success: true,
      restoredSnapshotId: target.snapshotId,
      restoredContent: target.content,
      removedSnapshotsCount: removedCount,
      currentLength: this.snapshots.length
    };
  }

  getLedgerSummary() {
    return {
      totalSnapshots: this.snapshots.length,
      history: this.snapshots.map(s => ({
        snapshotId: s.snapshotId,
        agentId: s.agentId,
        turnIndex: s.turnIndex,
        hash: s.hash,
        charCount: s.charCount,
        deltaCharCount: s.deltaCharCount,
        timestamp: s.timestamp
      }))
    };
  }
}

module.exports = { ContextStateCheckpointer };
