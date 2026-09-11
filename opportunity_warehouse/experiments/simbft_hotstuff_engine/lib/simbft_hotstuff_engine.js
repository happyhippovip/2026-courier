/**
 * Multi-Agent Distributed Asynchronous Verifiable SimBFT-HotStuff Hybrid Consensus Engine
 * Implements SimBFT's single-round linear vote aggregation with HotStuff pipelined block finality.
 */

const crypto = require('crypto');

function hashObject(obj) {
  return crypto.createHash('sha256').update(JSON.stringify(obj)).digest('hex');
}

class SimBFTBlock {
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

class SimBFTHotStuffEngine {
  constructor(nodeCount = 4) {
    this.nodeCount = nodeCount;
    this.f = Math.floor((nodeCount - 1) / 3); // f=1
    this.quorumSize = 2 * this.f + 1; // 3

    this.blocks = new Map(); // blockHash -> SimBFTBlock
    this.qcs = new Map(); // view -> QC
    this.votes = new Map(); // "view:nodeId" -> vote
    this.committedBlocks = [];
    this.committedTxs = [];

    // Initialize Genesis
    const genesis = new SimBFTBlock(0, '0000000000000000000000000000000000000000000000000000000000000000', [], 'GENESIS');
    this.blocks.set(genesis.blockHash, genesis);
    this.highestQC = { view: 0, blockHash: genesis.blockHash, signatures: [] };
    this.qcs.set(0, this.highestQC);
  }

  proposeBlock(view, parentHash, txs, leaderId) {
    if (!this.blocks.has(parentHash)) {
      throw new Error('Parent block not found: ' + parentHash);
    }
    const block = new SimBFTBlock(view, parentHash, txs, leaderId);
    this.blocks.set(block.blockHash, block);
    return block;
  }

  castVote(view, blockHash, voterNodeId) {
    const block = this.blocks.get(blockHash);
    if (!block || block.view !== view) {
      throw new Error('Invalid vote for block');
    }

    const voteKey = view + ':' + voterNodeId;
    if (this.votes.has(voteKey)) {
      throw new Error('Double voting detected from node ' + voterNodeId + ' in view ' + view);
    }

    const vote = {
      view,
      blockHash,
      voterNodeId,
      sig: hashObject({ view, blockHash, voterNodeId, role: 'SIMBFT_VOTE' })
    };
    this.votes.set(voteKey, vote);
    return vote;
  }

  aggregateVotesToQC(view, blockHash) {
    const relevantVotes = [];
    for (const [key, vote] of this.votes.entries()) {
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
      return this._commitBlock(b1);
    }
    return null;
  }

  _commitBlock(block) {
    if (this.committedBlocks.includes(block.blockHash)) {
      return { committed: false, reason: 'ALREADY_COMMITTED' };
    }

    this.committedBlocks.push(block.blockHash);
    this.committedTxs.push(...block.txs);

    return {
      committed: true,
      mode: 'SIMBFT_HOTSTUFF_3CHAIN_COMMIT',
      view: block.view,
      blockHash: block.blockHash,
      leaderId: block.leaderId,
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

module.exports = { SimBFTBlock, SimBFTHotStuffEngine };
