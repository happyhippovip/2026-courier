/**
 * Multi-Turn Context Compaction Ledger & Rollback Guard
 * Maintains an immutable, content-addressed Merkle DAG of context compaction checkpoints,
 * verifying chain integrity and enabling instantaneous rollback to historical uncompacted states
 * if downstream execution detects hallucination or intent drift.
 */

const crypto = require('crypto');

class CompactionRollbackGuard {
  constructor() {
    this.checkpoints = [];
    this.activeCheckpointId = null;
  }

  hashContext(contextObj) {
    const serialized = JSON.stringify(contextObj);
    return crypto.createHash('sha256').update(serialized).digest('hex');
  }

  createCheckpoint(turnIndex, rawContext, compactedContext, meta = {}) {
    const rawHash = this.hashContext(rawContext);
    const compactedHash = this.hashContext(compactedContext);
    const prevHash = this.checkpoints.length > 0 ? this.checkpoints[this.checkpoints.length - 1].merkleHash : 'GENESIS_ROOT';

    const id = 'cp_turn_' + turnIndex + '_' + Date.now();
    const merkleHash = crypto.createHash('sha256')
      .update(prevHash + ':' + rawHash + ':' + compactedHash)
      .digest('hex');

    const rawTokens = Math.max(1, Math.round(JSON.stringify(rawContext).length / 4));
    const compactedTokens = Math.max(1, Math.round(JSON.stringify(compactedContext).length / 4));
    const savingsPct = Number((((rawTokens - compactedTokens) / rawTokens) * 100).toFixed(1));

    const record = {
      id,
      turnIndex,
      timestamp: Date.now(),
      prevHash,
      rawHash,
      compactedHash,
      merkleHash,
      rawTokens,
      compactedTokens,
      savingsPct,
      rawContextSnapshot: JSON.parse(JSON.stringify(rawContext)),
      compactedContextSnapshot: JSON.parse(JSON.stringify(compactedContext)),
      status: 'ACTIVE',
      meta
    };

    this.checkpoints.push(record);
    this.activeCheckpointId = id;
    return record;
  }

  verifyChainIntegrity() {
    if (this.checkpoints.length === 0) return true;

    for (let i = 0; i < this.checkpoints.length; i++) {
      const curr = this.checkpoints[i];
      const expectedPrev = i === 0 ? 'GENESIS_ROOT' : this.checkpoints[i - 1].merkleHash;
      if (curr.prevHash !== expectedPrev) return false;

      const recomputedMerkle = crypto.createHash('sha256')
        .update(curr.prevHash + ':' + curr.rawHash + ':' + curr.compactedHash)
        .digest('hex');

      if (recomputedMerkle !== curr.merkleHash) return false;
    }
    return true;
  }

  rollbackToCheckpoint(checkpointId) {
    const targetIdx = this.checkpoints.findIndex(c => c.id === checkpointId);
    if (targetIdx === -1) {
      throw new Error('Checkpoint not found: ' + checkpointId);
    }

    // Mark subsequent checkpoints as ROLLED_BACK
    for (let i = targetIdx + 1; i < this.checkpoints.length; i++) {
      this.checkpoints[i].status = 'ROLLED_BACK';
    }

    this.activeCheckpointId = checkpointId;
    const restored = this.checkpoints[targetIdx];

    return {
      restoredCheckpointId: checkpointId,
      turnIndex: restored.turnIndex,
      rawContext: restored.rawContextSnapshot,
      revertedTurnsCount: this.checkpoints.length - 1 - targetIdx
    };
  }
}

module.exports = { CompactionRollbackGuard };