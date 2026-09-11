/**
 * Multi-Agent Distributed Asynchronous Verifiable Dual-Quorum Byzantine Consensus Engine
 * Implements asymmetric dual quorums (Fast Quorum Q_fast = N and Slow Quorum Q_slow = 2f+1)
 * for sub-millisecond fast-path consensus with fallback to HotStuff 3-chain pipelining.
 */

const crypto = require('crypto');

function hashObject(obj) {
  return crypto.createHash('sha256').update(JSON.stringify(obj)).digest('hex');
}

class DualQuorumBlock {
  constructor(view, parentHash, txs, leaderId) {
    this.view = view;
    this.parentHash = parentHash;
    this.txs = Array.isArray(txs) ? txs : [];
    this.leaderId = leaderId;
    this.timestamp = Date.now();
    this.blockHash = hashObject({
      view: this.view,
      parentHash: this.parentHash,
      txs: this.txs,
      leaderId: this.leaderId
    });
  }
}

class BFTDualQuorumEngine {
  constructor(nodeCount = 4) {
    this.nodeCount = nodeCount;
    this.f = Math.floor((nodeCount - 1) / 3); // f=1
    this.qSlow = 2 * this.f + 1; // 3
    this.qFast = nodeCount; // 4 (Unanimous fast quorum)

    this.blocks = new Map();
    this.votes = new Map(); // "view:nodeId" -> vote
    this.qcs = new Map(); // view -> QC
    this.committedBlocks = [];
    this.committedTxs = [];

    // Genesis Block
    const genesisHash = '0000000000000000000000000000000000000000000000000000000000000000';
    const genesis = new DualQuorumBlock(0, genesisHash, [], 'GENESIS');
    this.blocks.set(genesis.blockHash, genesis);
    this.highestQC = { view: 0, blockHash: genesis.blockHash, signatures: [] };
    this.qcs.set(0, this.highestQC);
  }

  proposeBlock(view, parentHash, txs, leaderId) {
    if (!this.blocks.has(parentHash)) {
      throw new Error('Parent block not found: ' + parentHash);
    }

    const block = new DualQuorumBlock(view, parentHash, txs, leaderId);
    this.blocks.set(block.blockHash, block);
    return block;
  }

  castVote(view, blockHash, voterNodeId) {
    const block = this.blocks.get(blockHash);
    if (!block || block.view !== view) throw new Error('Invalid vote for block');

    const voteKey = view + ':' + voterNodeId;
    if (this.votes.has(voteKey)) {
      throw new Error('Double voting detected from node ' + voterNodeId + ' in view ' + view);
    }

    const vote = {
      view,
      blockHash,
      voterNodeId,
      sig: hashObject({ view, blockHash, voterNodeId, role: 'DUAL_QUORUM_VOTE' })
    };
    this.votes.set(voteKey, vote);
    return vote;
  }

  evaluateFastQuorumCommit(view, blockHash) {
    const matchingVotes = [];
    for (const vote of this.votes.values()) {
      if (vote.view === view && vote.blockHash === blockHash) {
        matchingVotes.push(vote);
      }
    }

    if (matchingVotes.length >= this.qFast) {
      const block = this.blocks.get(blockHash);
      return this._commitBlock(block, 'DUAL_QUORUM_FAST_PATH');
    }

    return { committed: false, reason: 'FAST_QUORUM_NOT_MET', voteCount: matchingVotes.length, required: this.qFast };
  }

  createSlowQC(view, blockHash) {
    const matchingVotes = [];
    for (const vote of this.votes.values()) {
      if (vote.view === view && vote.blockHash === blockHash) {
        matchingVotes.push(vote);
      }
    }

    if (matchingVotes.length < this.qSlow) {
      throw new Error('Insufficient votes for slow QC: has ' + matchingVotes.length + ', requires ' + this.qSlow);
    }

    const qc = {
      view,
      blockHash,
      signatures: matchingVotes.slice(0, this.qSlow)
    };
    this.qcs.set(view, qc);
    if (view > this.highestQC.view) {
      this.highestQC = qc;
    }
    return qc;
  }

  evaluate3ChainCommit(b3Hash) {
    // HotStuff 3-Chain Rule: B3 -> B2 -> B1
    const b3 = this.blocks.get(b3Hash);
    if (!b3) return null;
    const b2 = this.blocks.get(b3.parentHash);
    if (!b2) return null;
    const b1 = this.blocks.get(b2.parentHash);
    if (!b1) return null;

    if (b3.view === b2.view + 1 && b2.view === b1.view + 1) {
      return this._commitBlock(b1, 'HOTSTUFF_3CHAIN_FALLBACK');
    }
    return null;
  }

  _commitBlock(block, mode) {
    if (this.committedBlocks.includes(block.blockHash)) {
      return { committed: false, reason: 'ALREADY_COMMITTED' };
    }

    this.committedBlocks.push(block.blockHash);
    this.committedTxs.push(...block.txs);

    return {
      committed: true,
      mode,
      view: block.view,
      blockHash: block.blockHash,
      txs: block.txs,
      totalCommittedTxs: this.committedTxs.length
    };
  }

  getStats() {
    return {
      nodeCount: this.nodeCount,
      qFast: this.qFast,
      qSlow: this.qSlow,
      blocksCount: this.blocks.size,
      qcsCount: this.qcs.size,
      committedBlocksCount: this.committedBlocks.length,
      totalCommittedTxs: this.committedTxs.length
    };
  }
}

module.exports = { DualQuorumBlock, BFTDualQuorumEngine };
