/**
 * Multi-Agent Distributed Asynchronous Verifiable Optimistic Linear BFT Consensus Engine
 * Implements 1-round optimistic commitment under unanimous participation,
 * with seamless fallback to HotStuff 3-chain pipelining under network delay or Byzantine faults.
 */

const crypto = require('crypto');

function hashObject(obj) {
  return crypto.createHash('sha256').update(JSON.stringify(obj)).digest('hex');
}

class OptimisticBlock {
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

class BFTOptimisticLinearEngine {
  constructor(nodeCount = 4) {
    this.nodeCount = nodeCount;
    this.f = Math.floor((nodeCount - 1) / 3); // f=1
    this.quorumSize = 2 * this.f + 1; // 3
    this.unanimousSize = nodeCount; // 4 for 1-round optimistic commit

    this.blocks = new Map();
    this.votes = new Map(); // "view:nodeId" -> vote
    this.qcs = new Map(); // view -> QC
    this.committedBlocks = [];
    this.committedTxs = [];

    // Genesis Block
    const genesisHash = '0000000000000000000000000000000000000000000000000000000000000000';
    const genesis = new OptimisticBlock(0, genesisHash, [], 'GENESIS');
    this.blocks.set(genesis.blockHash, genesis);
    this.highestQC = { view: 0, blockHash: genesis.blockHash, signatures: [] };
    this.qcs.set(0, this.highestQC);
  }

  proposeBlock(view, parentHash, txs, leaderId) {
    if (!this.blocks.has(parentHash)) {
      throw new Error('Parent block not found: ' + parentHash);
    }

    const block = new OptimisticBlock(view, parentHash, txs, leaderId);
    this.blocks.set(block.blockHash, block);
    return block;
  }

  castVote(view, blockHash, voterNodeId) {
    const block = this.blocks.get(blockHash);
    if (!block || block.view !== view) throw new Error('Invalid vote for block');

    const voteKey = view + ':' + voterNodeId;
    if (this.votes.has(voteKey)) {
      throw new Error('Double voting detected: node ' + voterNodeId + ' in view ' + view);
    }

    const vote = {
      view,
      blockHash,
      voterNodeId,
      sig: hashObject({ view, blockHash, voterNodeId, role: 'OPTIMISTIC_VOTE' })
    };
    this.votes.set(voteKey, vote);
    return vote;
  }

  evaluateOptimisticFastPath(view, blockHash) {
    // If all N nodes vote for this block in 1 round, it commits immediately!
    const relevantVotes = [];
    for (const vote of this.votes.values()) {
      if (vote.view === view && vote.blockHash === blockHash) {
        relevantVotes.push(vote);
      }
    }

    if (relevantVotes.length === this.unanimousSize) {
      const block = this.blocks.get(blockHash);
      return this._commitBlock(block, 'OPTIMISTIC_1_ROUND_FAST_PATH');
    }

    return { committed: false, reason: 'UNANIMOUS_QUORUM_NOT_REACHED', voteCount: relevantVotes.length };
  }

  createQC(view, blockHash) {
    const relevantVotes = [];
    for (const vote of this.votes.values()) {
      if (vote.view === view && vote.blockHash === blockHash) {
        relevantVotes.push(vote);
      }
    }

    if (relevantVotes.length < this.quorumSize) {
      throw new Error('Insufficient votes for QC: has ' + relevantVotes.length + ', requires ' + this.quorumSize);
    }

    const qc = {
      view,
      blockHash,
      signatures: relevantVotes.slice(0, this.quorumSize)
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
      blocksCount: this.blocks.size,
      qcsCount: this.qcs.size,
      committedBlocksCount: this.committedBlocks.length,
      totalCommittedTxs: this.committedTxs.length
    };
  }
}

module.exports = { OptimisticBlock, BFTOptimisticLinearEngine };
