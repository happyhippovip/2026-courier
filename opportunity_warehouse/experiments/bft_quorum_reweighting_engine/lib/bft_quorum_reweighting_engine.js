/**
 * Byzantine Dynamic Quorum Re-weighting Consensus Engine
 * Dynamically adjusts validator voting weights across epochs,
 * computing dynamic 2/3 stake quorums without halting consensus execution.
 */

const crypto = require('crypto');

function sha256(data) {
  return crypto.createHash('sha256').update(typeof data === 'string' ? data : JSON.stringify(data)).digest('hex');
}

class BFTQuorumReweightingEngine {
  constructor(nodeId, initialWeights = {}) {
    this.nodeId = nodeId;
    this.currentEpoch = 0;
    this.weights = new Map(Object.entries(initialWeights)); // nodeId -> weight
    this.committedEpochs = [];
  }

  getTotalWeight() {
    let total = 0;
    for (const w of this.weights.values()) total += w;
    return total;
  }

  getQuorumThreshold() {
    const total = this.getTotalWeight();
    return Math.floor((2 * total) / 3) + 1;
  }

  proposeReweighting(nextEpoch, newWeights, payload) {
    if (nextEpoch !== this.currentEpoch + 1) {
      throw new Error(`Invalid epoch: expected ${this.currentEpoch + 1}, got ${nextEpoch}`);
    }

    const proposal = {
      epoch: nextEpoch,
      currentEpoch: this.currentEpoch,
      newWeights,
      payload,
      proposer: this.nodeId,
      timestamp: Date.now()
    };
    proposal.hash = sha256(proposal);
    return proposal;
  }

  certifyReweighting(proposal, signatures) {
    const requiredQuorum = this.getQuorumThreshold();
    let accumulatedWeight = 0;
    const validSigners = new Set();

    for (const sig of signatures) {
      if (this.weights.has(sig.nodeId)) {
        const expected = sha256(`${sig.nodeId}:${proposal.hash}:${proposal.epoch}`);
        if (sig.signature === expected) {
          validSigners.add(sig.nodeId);
          accumulatedWeight += this.weights.get(sig.nodeId);
        }
      }
    }

    if (accumulatedWeight < requiredQuorum) {
      return {
        committed: false,
        accumulatedWeight,
        requiredQuorum,
        reason: 'INSUFFICIENT_WEIGHT_QUORUM'
      };
    }

    // Apply new weights and advance epoch
    this.currentEpoch = proposal.epoch;
    this.weights.clear();
    for (const [node, w] of Object.entries(proposal.newWeights)) {
      this.weights.set(node, w);
    }

    const commitRecord = {
      epoch: proposal.epoch,
      accumulatedWeight,
      requiredQuorum,
      signers: Array.from(validSigners),
      newWeights: Object.fromEntries(this.weights)
    };
    this.committedEpochs.push(commitRecord);

    return { committed: true, commitRecord };
  }
}

module.exports = { BFTQuorumReweightingEngine };
