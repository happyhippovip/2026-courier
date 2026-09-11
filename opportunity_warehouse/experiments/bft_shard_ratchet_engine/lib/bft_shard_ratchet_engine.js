/**
 * BFT Shard Finality Ratchet Consensus Engine
 * Implements monotonic epoch ratcheting across distributed shard quorums.
 * Prevents historical rollback and enforces forward-progress invariants during network partitions.
 */

const crypto = require('crypto');

class BftShardRatchetEngine {
  constructor(options = {}) {
    this.shardId = options.shardId || 'shard-0';
    this.currentEpoch = 0;
    this.highestCommittedEpoch = 0;
    this.epochCommitments = new Map();
    this.ratchetHistory = [];
  }

  proposeEpochTransition(proposedEpoch, stateRoot, quorumSignatures) {
    if (proposedEpoch <= this.highestCommittedEpoch) {
      throw new Error(`RATCHET_VIOLATION: Proposed epoch ${proposedEpoch} must be strictly greater than committed ${this.highestCommittedEpoch}`);
    }

    const requiredQuorum = 3;
    if (!quorumSignatures || quorumSignatures.length < requiredQuorum) {
      throw new Error(`QUORUM_DEFICIT: Received ${quorumSignatures ? quorumSignatures.length : 0} signatures, minimum ${requiredQuorum} required`);
    }

    const commitment = {
      shardId: this.shardId,
      epoch: proposedEpoch,
      previousEpoch: this.highestCommittedEpoch,
      stateRoot,
      signatures: quorumSignatures,
      ratchetTimestamp: new Date().toISOString(),
      commitmentHash: crypto.createHash('sha256').update(`${this.shardId}:${proposedEpoch}:${stateRoot}`).digest('hex')
    };

    this.highestCommittedEpoch = proposedEpoch;
    this.currentEpoch = proposedEpoch;
    this.epochCommitments.set(proposedEpoch, commitment);
    this.ratchetHistory.push(commitment);

    return commitment;
  }

  getRatchetProof(epoch) {
    return this.epochCommitments.get(epoch) || null;
  }
}

module.exports = { BftShardRatchetEngine };
