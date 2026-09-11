/**
 * HoneyBadgerBFT Asynchronous Consensus Engine (Phase 383)
 * Asynchronous Common Subset (ACS) implementation.
 */

class HoneyBadgerNode {
  constructor(nodeId, n = 4, isFaulty = false) {
    this.nodeId = nodeId;
    this.n = n;
    this.f = Math.floor((n - 1) / 3);
    this.threshold = n - this.f; // 3 for n=4
    this.isFaulty = isFaulty;
    this.receivedProposals = new Map();
  }

  proposeBatch(transactions) {
    if (this.isFaulty) return null;
    return {
      nodeId: this.nodeId,
      txs: transactions
    };
  }

  receiveProposal(proposal) {
    if (!proposal || !proposal.nodeId || !proposal.txs) return;
    this.receivedProposals.set(proposal.nodeId, proposal);
  }

  tryCommitCommonSubset() {
    if (this.receivedProposals.size < this.threshold) {
      return { status: 'PENDING', receivedCount: this.receivedProposals.size };
    }

    const includedNodes = Array.from(this.receivedProposals.keys()).slice(0, this.threshold);
    const batch = [];

    for (const nodeId of includedNodes) {
      const prop = this.receivedProposals.get(nodeId);
      batch.push(...prop.txs);
    }

    return {
      status: 'ACS_COMMITTED',
      includedNodes,
      totalTransactions: batch.length,
      batch
    };
  }
}

module.exports = { HoneyBadgerNode };
