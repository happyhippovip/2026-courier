/**
 * BFT Shard View-Synchronization Consensus Engine
 * Implements pacemaker-synchronized view changes with 2f+1 view-change quorum certificates.
 */

const crypto = require('crypto');

class BFTShardViewSyncEngine {
  constructor(shardId, totalValidators = 4, timeoutMs = 2000) {
    this.shardId = shardId;
    this.totalValidators = totalValidators;
    this.faultTolerance = Math.floor((totalValidators - 1) / 3); // f
    this.quorumThreshold = 2 * this.faultTolerance + 1; // 2f + 1
    this.currentView = 0;
    this.timeoutMs = timeoutMs;
    this.viewChangeVotes = new Map(); // view -> Map(validatorId, vote)
    this.viewHistory = [];
    this.lastSynchronizedAt = Date.now();
  }

  hash(payload) {
    return crypto.createHash('sha256').update(JSON.stringify(payload)).digest('hex');
  }

  triggerTimeout(validatorId) {
    const targetView = this.currentView + 1;
    const votePayload = {
      shardId: this.shardId,
      validatorId: validatorId,
      targetView: targetView,
      timestamp: Date.now()
    };
    const voteSig = this.hash(votePayload);

    if (!this.viewChangeVotes.has(targetView)) {
      this.viewChangeVotes.set(targetView, new Map());
    }
    const votesForView = this.viewChangeVotes.get(targetView);
    votesForView.set(validatorId, { payload: votePayload, signature: voteSig });

    // Check if quorum achieved
    if (votesForView.size >= this.quorumThreshold) {
      return this.aggregateNewViewCertificate(targetView);
    }

    return {
      status: 'AWAITING_QUORUM',
      currentVotes: votesForView.size,
      quorumRequired: this.quorumThreshold
    };
  }

  aggregateNewViewCertificate(newView) {
    const votesForView = this.viewChangeVotes.get(newView);
    const voterIds = Array.from(votesForView.keys());
    const proofSignatures = voterIds.map(vid => votesForView.get(vid).signature);

    const certificate = {
      shardId: this.shardId,
      view: newView,
      voterCount: voterIds.length,
      voterIds: voterIds,
      quorumCertificateHash: this.hash({ newView, voterIds, proofSignatures }),
      finalizedAt: new Date().toISOString()
    };

    this.currentView = newView;
    this.lastSynchronizedAt = Date.now();
    this.viewHistory.push(certificate);

    return {
      status: 'VIEW_SYNCHRONIZED',
      newView: this.currentView,
      certificate: certificate
    };
  }

  getSynchronizationStatus() {
    return {
      shardId: this.shardId,
      currentView: this.currentView,
      quorumThreshold: this.quorumThreshold,
      totalViewsSynchronized: this.viewHistory.length,
      lastSynchronizedAt: this.lastSynchronizedAt
    };
  }
}

module.exports = { BFTShardViewSyncEngine };
