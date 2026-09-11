/**
 * Multi-Agent Distributed Byzantine Fault Tolerant (PBFT) Consensus Coordinator
 * Coordinates consensus across autonomous agent nodes with 3f + 1 quorum thresholds
 * through Pre-Prepare, Prepare, and Commit message exchange phases.
 */

class PBFTNode {
  constructor(nodeId, clusterSize, isByzantine = false) {
    this.nodeId = nodeId;
    this.clusterSize = clusterSize; // N = 3f + 1
    this.f = Math.floor((clusterSize - 1) / 3);
    this.isByzantine = isByzantine;
    this.state = 'IDLE'; // 'IDLE' | 'PREPARED' | 'COMMITTED'
    this.prepareVotes = new Map(); // txId -> Set of senderIds
    this.commitVotes = new Map();  // txId -> Set of senderIds
  }

  handlePrePrepare(txId, proposal) {
    if (this.isByzantine) {
      // Byzantine node intentionally refuses or tampers
      return null;
    }

    if (!this.prepareVotes.has(txId)) this.prepareVotes.set(txId, new Set());
    this.prepareVotes.get(txId).add(this.nodeId); // Vote for self

    return {
      type: 'PREPARE',
      txId,
      proposal,
      nodeId: this.nodeId
    };
  }

  handlePrepare(msg) {
    if (this.isByzantine) return null;

    if (!this.prepareVotes.has(msg.txId)) this.prepareVotes.set(msg.txId, new Set());
    this.prepareVotes.get(msg.txId).add(msg.nodeId);

    // Quorum threshold: 2f + 1 prepares
    const threshold = 2 * this.f + 1;
    if (this.prepareVotes.get(msg.txId).size >= threshold && this.state === 'IDLE') {
      this.state = 'PREPARED';
      if (!this.commitVotes.has(msg.txId)) this.commitVotes.set(msg.txId, new Set());
      this.commitVotes.get(msg.txId).add(this.nodeId);

      return {
        type: 'COMMIT',
        txId: msg.txId,
        nodeId: this.nodeId
      };
    }
    return null;
  }

  handleCommit(msg) {
    if (this.isByzantine) return null;

    if (!this.commitVotes.has(msg.txId)) this.commitVotes.set(msg.txId, new Set());
    this.commitVotes.get(msg.txId).add(msg.nodeId);

    // Quorum threshold: 2f + 1 commits
    const threshold = 2 * this.f + 1;
    if (this.commitVotes.get(msg.txId).size >= threshold && this.state === 'PREPARED') {
      this.state = 'COMMITTED';
      return {
        status: 'CONSENSUS_REACHED',
        txId: msg.txId,
        nodeId: this.nodeId
      };
    }
    return null;
  }
}

class PBFTCoordinator {
  constructor(nodes) {
    this.nodes = nodes; // Array of PBFTNode
  }

  runConsensus(txId, proposal) {
    const leader = this.nodes[0];
    const prepareMessages = [];

    // Step 1: Pre-Prepare broadcast
    for (const node of this.nodes) {
      const prep = node.handlePrePrepare(txId, proposal);
      if (prep) prepareMessages.push(prep);
    }

    // Step 2: Prepare exchange
    const commitMessages = [];
    for (const prepMsg of prepareMessages) {
      for (const node of this.nodes) {
        const commitMsg = node.handlePrepare(prepMsg);
        if (commitMsg) commitMessages.push(commitMsg);
      }
    }

    // Step 3: Commit exchange
    let committedNodes = 0;
    for (const commitMsg of commitMessages) {
      for (const node of this.nodes) {
        const res = node.handleCommit(commitMsg);
        if (res && res.status === 'CONSENSUS_REACHED') {
          committedNodes++;
        }
      }
    }

    const honestNodes = this.nodes.filter(n => !n.isByzantine).length;
    const allHonestCommitted = this.nodes.filter(n => !n.isByzantine).every(n => n.state === 'COMMITTED');

    return {
      txId,
      clusterSize: this.nodes.length,
      honestNodes,
      allHonestCommitted,
      status: allHonestCommitted ? 'COMMITTED' : 'FAILED'
    };
  }
}

module.exports = { PBFTNode, PBFTCoordinator };
