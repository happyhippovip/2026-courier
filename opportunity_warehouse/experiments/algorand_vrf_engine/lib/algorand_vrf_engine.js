/**
 * Multi-Agent Distributed Algorand-Style VRF Consensus Engine
 * Implements cryptographic sortition via Verifiable Random Functions (VRF)
 * to randomly select secret proposer and voting committees without prior communication.
 */

const crypto = require('crypto');

class VRFNode {
  constructor(nodeId, stakeWeight = 10, secretKey = null) {
    this.nodeId = nodeId;
    this.stakeWeight = stakeWeight;
    this.secretKey = secretKey || crypto.createHash('sha256').update('node-secret:' + nodeId).digest('hex');
  }

  // Evaluate VRF over seed string
  evaluateVRF(seed, round) {
    const message = seed + ':' + round + ':' + this.nodeId;
    const vrfHash = crypto.createHmac('sha256', this.secretKey).update(message).digest('hex');
    const vrfValue = parseInt(vrfHash.substring(0, 8), 16);
    return { vrfHash, vrfValue };
  }

  // Sortition check: returns number of selected sub-users for committee
  sortition(seed, round, committeeExpectedSize, totalStake) {
    const { vrfHash, vrfValue } = this.evaluateVRF(seed, round);
    const normalized = vrfValue / 0xFFFFFFFF; // [0, 1]
    const p = (committeeExpectedSize * this.stakeWeight) / totalStake;

    const isSelected = normalized < p;
    return {
      nodeId: this.nodeId,
      isSelected,
      vrfHash,
      normalized,
      threshold: p
    };
  }
}

class AlgorandVRFCoordinator {
  constructor(nodes) {
    this.nodes = nodes;
    this.totalStake = nodes.reduce((acc, n) => acc + n.stakeWeight, 0);
  }

  runRound(round, seed, expectedCommitteeSize = 3) {
    const selections = [];
    for (const node of this.nodes) {
      const res = node.sortition(seed, round, expectedCommitteeSize, this.totalStake);
      if (res.isSelected) {
        selections.push(res);
      }
    }

    return {
      round,
      seed,
      expectedCommitteeSize,
      actualSelectedCount: selections.length,
      committee: selections.map(s => s.nodeId),
      sortitionDetails: selections
    };
  }
}

module.exports = { VRFNode, AlgorandVRFCoordinator };
