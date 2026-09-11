/**
 * BFT Shard Dynamic Committee Re-Allocation Engine
 * Implements deterministic validator committee shuffling across shards using VRF epoch entropy.
 */

const crypto = require('crypto');

class BFTShardCommitteeReallocationEngine {
  constructor(shardCount = 4, committeeSizePerShard = 4) {
    this.shardCount = shardCount;
    this.committeeSizePerShard = committeeSizePerShard;
    this.epoch = 0;
    this.currentAssignments = new Map(); // shardId -> Array<validatorId>
    this.history = [];
  }

  hash(payload) {
    return crypto.createHash('sha256').update(typeof payload === 'string' ? payload : JSON.stringify(payload)).digest('hex');
  }

  reallocate(epoch, epochEntropySeed, validatorPool) {
    if (validatorPool.length < this.shardCount * this.committeeSizePerShard) {
      throw new Error('Insufficient validator pool size for shard committee allocation');
    }

    this.epoch = epoch;
    // Deterministic pseudo-random shuffle based on epochEntropySeed
    const sortedPool = [...validatorPool].sort();
    const seedInt = parseInt(this.hash(epochEntropySeed).substring(0, 8), 16);

    // Knuth-Fisher-Yates shuffle seeded with deterministic hash
    const shuffled = [...sortedPool];
    for (let i = shuffled.length - 1; i > 0; i--) {
      const hVal = parseInt(this.hash(epochEntropySeed + ':' + i).substring(0, 8), 16);
      const j = hVal % (i + 1);
      const temp = shuffled[i];
      shuffled[i] = shuffled[j];
      shuffled[j] = temp;
    }

    this.currentAssignments.clear();
    for (let s = 0; s < this.shardCount; s++) {
      const shardId = 'shard-' + s;
      const committee = shuffled.slice(s * this.committeeSizePerShard, (s + 1) * this.committeeSizePerShard);
      this.currentAssignments.set(shardId, committee);
    }

    const allocationSummary = {
      epoch: this.epoch,
      epochEntropySeed: epochEntropySeed,
      assignments: Object.fromEntries(this.currentAssignments),
      assignmentCommitment: this.hash({ epoch, seed: epochEntropySeed, assignments: Object.fromEntries(this.currentAssignments) }),
      timestamp: new Date().toISOString()
    };

    this.history.push(allocationSummary);
    return allocationSummary;
  }

  getCommitteeForShard(shardId) {
    return this.currentAssignments.get(shardId) || [];
  }
}

module.exports = { BFTShardCommitteeReallocationEngine };
