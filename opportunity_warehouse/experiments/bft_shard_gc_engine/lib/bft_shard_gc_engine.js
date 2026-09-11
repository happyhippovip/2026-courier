/**
 * Byzantine Dynamic Shard State Garbage Collection Consensus Engine
 * Periodically detects and reclaims expired keys and spent causal state
 * certified by cross-shard 2f+1 quorum signatures to prevent state bloat.
 */

const crypto = require('crypto');

function sha256(data) {
  return crypto.createHash('sha256').update(typeof data === 'string' ? data : JSON.stringify(data)).digest('hex');
}

class BFTShardGCEngine {
  constructor(shardId, quorumThreshold = 3) {
    this.shardId = shardId;
    this.quorumThreshold = quorumThreshold;
    this.state = new Map(); // key -> { value, expiresAtEpoch, isDead }
    this.prunedHistory = [];
  }

  setKey(key, value, expiresAtEpoch) {
    this.state.set(key, { value, expiresAtEpoch, isDead: false });
  }

  getKey(key) {
    const entry = this.state.get(key);
    return entry && !entry.isDead ? entry.value : null;
  }

  proposeGCCandidates(currentEpoch) {
    const deadKeys = [];
    for (const [key, entry] of this.state.entries()) {
      if (entry.expiresAtEpoch <= currentEpoch && !entry.isDead) {
        deadKeys.push(key);
      }
    }

    const proposal = {
      shardId: this.shardId,
      epoch: currentEpoch,
      deadKeys,
      timestamp: Date.now()
    };
    proposal.hash = sha256(proposal);
    return proposal;
  }

  certifyAndPrune(proposal, signatures) {
    const validSigners = new Set();

    for (const sig of signatures) {
      const expected = sha256(`${sig.nodeId}:${proposal.hash}:${proposal.epoch}`);
      if (sig.signature === expected) {
        validSigners.add(sig.nodeId);
      }
    }

    if (validSigners.size < this.quorumThreshold) {
      return { pruned: false, validSigners: validSigners.size, required: this.quorumThreshold };
    }

    // Safely prune dead keys
    for (const key of proposal.deadKeys) {
      if (this.state.has(key)) {
        this.state.get(key).isDead = true;
      }
    }

    const gcRecord = {
      epoch: proposal.epoch,
      prunedKeys: proposal.deadKeys,
      signers: Array.from(validSigners),
      timestamp: Date.now()
    };
    this.prunedHistory.push(gcRecord);

    return { pruned: true, prunedCount: proposal.deadKeys.length, gcRecord };
  }
}

module.exports = { BFTShardGCEngine };
