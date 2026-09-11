/**
 * Multi-Agent Distributed Asynchronous Verifiable Byzantine View-Sync Consensus Engine
 * Implements high-resilience linear view-synchronization (Timeout Certificates)
 * ensuring fast recovery from leader failures and partition-free view transitions.
 */

const crypto = require('crypto');

function hashObject(obj) {
  return crypto.createHash('sha256').update(JSON.stringify(obj)).digest('hex');
}

class TimeoutMessage {
  constructor(nodeId, view, highestQC) {
    this.nodeId = nodeId;
    this.view = view;
    this.highestQC = highestQC;
    this.timestamp = Date.now();
    this.sig = hashObject({ nodeId, view, highestQC: highestQC ? highestQC.blockHash : null, type: 'TIMEOUT' });
  }
}

class TimeoutCertificate {
  constructor(view, timeouts) {
    this.view = view;
    this.timeouts = timeouts;
    // Highest QC among all timeout messages
    let bestQC = null;
    for (const t of timeouts) {
      if (t.highestQC && (!bestQC || t.highestQC.view > bestQC.view)) {
        bestQC = t.highestQC;
      }
    }
    this.highestQC = bestQC;
    this.tcHash = hashObject({ view, timeoutCount: timeouts.length, bestQC: bestQC ? bestQC.blockHash : null });
  }
}

class BFTViewSyncEngine {
  constructor(nodeCount = 4) {
    this.nodeCount = nodeCount;
    this.f = Math.floor((nodeCount - 1) / 3); // f=1
    this.quorumSize = 2 * this.f + 1; // 3

    this.currentViews = new Map(); // nodeId -> currentView
    for (let i = 0; i < nodeCount; i++) {
      this.currentViews.set('node_' + i, 1);
    }

    this.timeouts = new Map(); // "view:nodeId" -> TimeoutMessage
    this.timeoutCertificates = new Map(); // view -> TimeoutCertificate
    this.proposals = new Map(); // blockHash -> proposal
    this.votes = new Map(); // "blockHash:nodeId" -> vote
    this.qcs = new Map(); // blockHash -> QC
    this.committedBlocks = [];

    // Genesis Block
    const genesisHash = '0000000000000000000000000000000000000000000000000000000000000000';
    this.highestQC = { blockHash: genesisHash, view: 0, signatures: [] };
    this.qcs.set(genesisHash, this.highestQC);
  }

  getLeader(view) {
    return 'node_' + ((view - 1) % this.nodeCount);
  }

  emitTimeout(nodeId, view) {
    const nodeView = this.currentViews.get(nodeId);
    if (view !== nodeView) {
      throw new Error('Timeout view mismatch for ' + nodeId + ': node in view ' + nodeView + ', timeout for ' + view);
    }

    const key = view + ':' + nodeId;
    if (this.timeouts.has(key)) {
      throw new Error('Double timeout emission detected for ' + nodeId + ' in view ' + view);
    }

    const msg = new TimeoutMessage(nodeId, view, this.highestQC);
    this.timeouts.set(key, msg);
    return msg;
  }

  aggregateTimeoutCertificate(view) {
    const matchingTimeouts = [];
    for (const [key, msg] of this.timeouts.entries()) {
      if (key.startsWith(view + ':')) {
        matchingTimeouts.push(msg);
      }
    }

    if (matchingTimeouts.length < this.quorumSize) {
      throw new Error('Insufficient timeout messages for TC: has ' + matchingTimeouts.length + ', requires ' + this.quorumSize);
    }

    const tc = new TimeoutCertificate(view, matchingTimeouts.slice(0, this.quorumSize));
    this.timeoutCertificates.set(view, tc);
    return tc;
  }

  syncToNewView(nodeId, tc) {
    if (!tc || typeof tc.view !== 'number') {
      throw new Error('Invalid Timeout Certificate provided for view sync');
    }

    const nextView = tc.view + 1;
    const current = this.currentViews.get(nodeId);
    if (nextView > current) {
      this.currentViews.set(nodeId, nextView);
      return { nodeId, synchronizedView: nextView, leader: this.getLeader(nextView) };
    }
    return { nodeId, currentView: current, reason: 'ALREADY_AHEAD' };
  }

  proposeBlock(view, tc, prevHash, txs, authorId) {
    const expectedLeader = this.getLeader(view);
    if (authorId !== expectedLeader) {
      throw new Error('Unauthorized leader: expected ' + expectedLeader + ', got ' + authorId);
    }

    if (view > 1 && (!tc || tc.view !== view - 1)) {
      throw new Error('Proposal in view ' + view + ' requires valid TC from view ' + (view - 1));
    }

    const blockHash = hashObject({ view, tcHash: tc ? tc.tcHash : null, prevHash, txs, authorId });
    const proposal = { view, tc, prevHash, txs, authorId, blockHash };
    this.proposals.set(blockHash, proposal);
    return proposal;
  }

  voteBlock(blockHash, voterNodeId) {
    const proposal = this.proposals.get(blockHash);
    if (!proposal) throw new Error('Proposal not found for vote: ' + blockHash);

    const voterView = this.currentViews.get(voterNodeId);
    if (voterView !== proposal.view) {
      throw new Error('Voter view mismatch: node in view ' + voterView + ', proposal in view ' + proposal.view);
    }

    const voteKey = blockHash + ':' + voterNodeId;
    if (this.votes.has(voteKey)) {
      throw new Error('Double vote detected from ' + voterNodeId);
    }

    const vote = {
      blockHash,
      voterNodeId,
      view: proposal.view,
      sig: hashObject({ blockHash, voterNodeId, view: proposal.view, type: 'VIEW_SYNC_VOTE' })
    };
    this.votes.set(voteKey, vote);
    return vote;
  }

  certifyBlock(blockHash) {
    const proposal = this.proposals.get(blockHash);
    if (!proposal) throw new Error('Proposal not found: ' + blockHash);

    const matchingVotes = [];
    for (const [key, v] of this.votes.entries()) {
      if (key.startsWith(blockHash + ':')) {
        matchingVotes.push(v);
      }
    }

    if (matchingVotes.length < this.quorumSize) {
      throw new Error('Insufficient votes for QC: has ' + matchingVotes.length + ', requires ' + this.quorumSize);
    }

    const qc = {
      blockHash,
      view: proposal.view,
      signatures: matchingVotes.slice(0, this.quorumSize)
    };
    this.qcs.set(blockHash, qc);
    if (proposal.view > this.highestQC.view) {
      this.highestQC = qc;
    }
    return qc;
  }

  commitBlock(blockHash) {
    if (!this.qcs.has(blockHash)) {
      throw new Error('Cannot commit uncertified block: ' + blockHash);
    }
    if (this.committedBlocks.includes(blockHash)) {
      return { committed: false, reason: 'ALREADY_COMMITTED' };
    }
    this.committedBlocks.push(blockHash);
    const proposal = this.proposals.get(blockHash);
    return {
      committed: true,
      blockHash,
      view: proposal.view,
      txs: proposal.txs
    };
  }

  getStats() {
    return {
      nodeCount: this.nodeCount,
      activeViews: Object.fromEntries(this.currentViews.entries()),
      totalTimeoutsEmitted: this.timeouts.size,
      totalTimeoutCertificates: this.timeoutCertificates.size,
      totalProposals: this.proposals.size,
      totalQCs: this.qcs.size,
      committedBlocksCount: this.committedBlocks.length
    };
  }
}

module.exports = { TimeoutMessage, TimeoutCertificate, BFTViewSyncEngine };
