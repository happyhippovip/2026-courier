/**
 * Checkpoint BFT Consensus Engine
 * Implements periodic stable checkpointing and state synchronization for BFT state machines.
 * Generates Stable Checkpoint Certificates (SCC) with 2f+1 signatures, enabling bounded log
 * truncation, fast state recovery for lagging replicas, and garbage collection.
 */

const crypto = require('crypto');

function sha256(data) {
  return crypto.createHash('sha256').update(typeof data === 'string' ? data : JSON.stringify(data)).digest('hex');
}

class ReplicaState {
  constructor(nodeId) {
    this.nodeId = nodeId;
    this.state = {};
    this.log = []; // Array of { seq, tx }
    this.lastStableSeq = 0;
    this.lastStableDigest = 'GENESIS_STATE';
  }

  applyTx(seq, tx) {
    this.log.push({ seq, tx });
    if (tx.type === 'SET') {
      this.state[tx.key] = tx.value;
    }
    return sha256(this.state);
  }

  createCheckpointVote(seq) {
    const digest = sha256(this.state);
    return {
      seq,
      digest,
      nodeId: this.nodeId,
      signature: sha256(`${this.nodeId}_chkpt_${seq}_${digest}`)
    };
  }

  truncateLog(stableSeq, stableDigest) {
    this.log = this.log.filter(entry => entry.seq > stableSeq);
    this.lastStableSeq = stableSeq;
    this.lastStableDigest = stableDigest;
  }
}

class CheckpointBFTEngine {
  constructor(replicaIds, checkpointInterval = 5, faultTolerance = 1) {
    this.replicaIds = replicaIds; // ['r0', 'r1', 'r2', 'r3']
    this.n = replicaIds.length;
    this.f = faultTolerance;
    this.quorum = 2 * this.f + 1; // 3
    this.checkpointInterval = checkpointInterval;

    this.replicas = replicaIds.map(id => new ReplicaState(id));
    this.currentSeq = 1;
    this.stableCertificates = new Map(); // seq -> SCC
  }

  executeTransaction(tx) {
    const seq = this.currentSeq++;
    const digests = [];

    for (const replica of this.replicas) {
      const digest = replica.applyTx(seq, tx);
      digests.push(digest);
    }

    let checkpointResult = null;
    // Check if checkpoint interval reached
    if (seq % this.checkpointInterval === 0) {
      checkpointResult = this._triggerCheckpoint(seq);
    }

    return { seq, stateDigest: digests[0], checkpointResult };
  }

  _triggerCheckpoint(seq) {
    const votes = [];
    for (const replica of this.replicas) {
      votes.push(replica.createCheckpointVote(seq));
    }

    // Group votes by digest
    const digestMap = new Map();
    for (const v of votes) {
      if (!digestMap.has(v.digest)) digestMap.set(v.digest, []);
      digestMap.get(v.digest).push(v);
    }

    for (const [digest, matchingVotes] of digestMap.entries()) {
      if (matchingVotes.length >= this.quorum) {
        // Quorum achieved: Create Stable Checkpoint Certificate (SCC)
        const scc = {
          seq,
          stateDigest: digest,
          signers: matchingVotes.map(v => v.nodeId).sort(),
          signatures: matchingVotes.map(v => v.signature),
          certId: sha256({ seq, digest, signers: matchingVotes.map(v => v.nodeId).sort() })
        };

        this.stableCertificates.set(seq, scc);

        // Truncate logs across all replicas
        for (const replica of this.replicas) {
          replica.truncateLog(seq, digest);
        }

        return { success: true, scc };
      }
    }

    return { success: false, reason: 'QUORUM_NOT_MET' };
  }

  syncLaggingReplica(laggingReplica, targetSeq) {
    const scc = this.stableCertificates.get(targetSeq);
    if (!scc) throw new Error('No stable checkpoint found for seq: ' + targetSeq);

    // Sync state snapshot from a quorum node
    const reference = this.replicas.find(r => r.lastStableSeq >= targetSeq);
    laggingReplica.state = JSON.parse(JSON.stringify(reference.state));
    laggingReplica.lastStableSeq = scc.seq;
    laggingReplica.lastStableDigest = scc.stateDigest;
    laggingReplica.log = [];

    return { synced: true, seq: scc.seq, certId: scc.certId };
  }

  getStableCertificate(seq) {
    return this.stableCertificates.get(seq);
  }
}

module.exports = { CheckpointBFTEngine, ReplicaState };
