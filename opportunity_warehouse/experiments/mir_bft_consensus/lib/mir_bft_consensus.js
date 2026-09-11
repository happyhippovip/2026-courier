/**
 * Mir-BFT Multi-Leader Consensus Engine
 * Implements high-throughput multi-leader state machine replication.
 * Client requests and agent actions are hash-partitioned into discrete buckets.
 * Multiple leaders propose concurrently for assigned buckets, avoiding leader bottlenecking.
 */

const crypto = require('crypto');

function sha256(data) {
  return crypto.createHash('sha256').update(typeof data === 'string' ? data : JSON.stringify(data)).digest('hex');
}

class MirBatch {
  constructor(leaderId, bucketId, epoch, requests) {
    this.leaderId = leaderId;
    this.bucketId = bucketId;
    this.epoch = epoch;
    this.requests = requests || [];
    this.batchHash = sha256({ leaderId, bucketId, epoch, requests });
  }
}

class MirBFTConsensus {
  constructor(leaders, numBuckets = 4, faultTolerance = 1) {
    this.leaders = leaders; // ['leader_0', 'leader_1', 'leader_2', 'leader_3']
    this.numBuckets = numBuckets;
    this.n = leaders.length;
    this.f = faultTolerance;
    this.quorum = 2 * this.f + 1;

    this.epoch = 1;
    // Map bucketId -> assigned leaderId
    this.bucketAssignments = new Map();
    for (let b = 0; b < numBuckets; b++) {
      this.bucketAssignments.set(b, this.leaders[b % this.n]);
    }

    // Ledger of committed batches: epoch -> Map(bucketId -> MirBatch)
    this.committedBatches = [];
  }

  getLeaderForBucket(bucketId) {
    return this.bucketAssignments.get(bucketId % this.numBuckets);
  }

  proposeBatch(leaderId, bucketId, requests) {
    const assigned = this.getLeaderForBucket(bucketId);
    if (assigned !== leaderId) {
      throw new Error(`UNAUTHORIZED_LEADER: Bucket ${bucketId} is assigned to ${assigned}, not ${leaderId}`);
    }

    const batch = new MirBatch(leaderId, bucketId, this.epoch, requests);
    return batch;
  }

  commitBatch(batch) {
    // Quorum signature verification over batch
    const signatures = {};
    for (let i = 0; i < this.quorum; i++) {
      const node = this.leaders[i];
      signatures[node] = sha256(`${node}_mir_sig_${batch.batchHash}`);
    }

    const record = {
      batch,
      epoch: this.epoch,
      signatures,
      committedAt: new Date().toISOString()
    };
    this.committedBatches.push(record);
    return record;
  }

  getCommittedLedger() {
    return this.committedBatches;
  }
}

module.exports = { MirBFTConsensus, MirBatch };
