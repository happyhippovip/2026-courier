/**
 * Multi-Agent Distributed Raft Joint Consensus Dynamic Membership Reconfiguration
 * Implements two-phase joint consensus (Cold,new -> Cnew) guaranteeing
 * that no disjoint quorums can make independent decisions during cluster expansion.
 */

class RaftJointCluster {
  constructor(initialNodes) {
    this.cOld = new Set(initialNodes);
    this.cNew = null;
    this.state = 'STABLE'; // 'STABLE' | 'JOINT_CONSENSUS'
  }

  // Phase 1: Enter joint configuration Cold,new
  enterJointConsensus(newNodes) {
    this.cNew = new Set(newNodes);
    this.state = 'JOINT_CONSENSUS';
    return {
      state: this.state,
      cOld: Array.from(this.cOld),
      cNew: Array.from(this.cNew)
    };
  }

  // Check if a set of voting nodes forms a joint quorum
  hasJointQuorum(voterNodes) {
    const voters = new Set(voterNodes);

    // Must have majority in Cold
    let votesOld = 0;
    for (const node of this.cOld) {
      if (voters.has(node)) votesOld++;
    }
    const majorityOld = Math.floor(this.cOld.size / 2) + 1;
    const hasOldQuorum = votesOld >= majorityOld;

    if (this.state === 'STABLE') {
      return hasOldQuorum;
    }

    // In JOINT_CONSENSUS, must ALSO have majority in Cnew
    let votesNew = 0;
    for (const node of this.cNew) {
      if (voters.has(node)) votesNew++;
    }
    const majorityNew = Math.floor(this.cNew.size / 2) + 1;
    const hasNewQuorum = votesNew >= majorityNew;

    return hasOldQuorum && hasNewQuorum;
  }

  // Phase 2: Commit Cnew and return to STABLE
  commitNewConfiguration() {
    if (this.state !== 'JOINT_CONSENSUS') {
      throw new Error('Cannot commit Cnew: cluster not in JOINT_CONSENSUS');
    }
    this.cOld = new Set(this.cNew);
    this.cNew = null;
    this.state = 'STABLE';
    return {
      state: this.state,
      activeNodes: Array.from(this.cOld)
    };
  }
}

module.exports = { RaftJointCluster };
