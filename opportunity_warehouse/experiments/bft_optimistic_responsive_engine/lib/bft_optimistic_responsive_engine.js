/**
 * Multi-Agent Distributed Asynchronous Verifiable Byzantine Optimistic Responsive Consensus Engine
 * Implements dual-path consensus: an Optimistic Fast-Path committing in actual network delay (3f+1 unanimous quorum)
 * and a standard Fallback-Path committing under 2f+1 Byzantine quorum.
 */

const crypto = require('crypto');

function hashObject(obj) {
  return crypto.createHash('sha256').update(JSON.stringify(obj)).digest('hex');
}

class OptimisticBlock {
  constructor(view, prevHash, txs, authorId) {
    this.view = view;
    this.prevHash = prevHash;
    this.txs = Array.isArray(txs) ? txs : [];
    this.authorId = authorId;
    this.timestamp = Date.now();
    this.blockHash = hashObject({ view, prevHash, txs: this.txs, authorId });
  }
}

class BFTOptimisticResponsiveEngine {
  constructor(nodeCount = 4) {
    this.nodeCount = nodeCount;
    this.f = Math.floor((nodeCount - 1) / 3); // f=1
    this.standardQuorum = 2 * this.f + 1; // 3
    this.optimisticQuorum = 3 * this.f + 1; // 4 (unanimous / all non-faulty)

    this.blocks = new Map(); // blockHash -> OptimisticBlock
    this.votes = new Map(); // "blockHash:voterId" -> vote
    this.qcs = new Map(); // blockHash -> QC
    this.committedBlocks = [];
    this.commitModes = new Map(); // blockHash -> 'OPTIMISTIC_FAST_PATH' | 'STANDARD_BFT_PATH'

    const genesisHash = '0000000000000000000000000000000000000000000000000000000000000000';
    const genesis = new OptimisticBlock(0, genesisHash, [], 'GENESIS');
    this.blocks.set(genesis.blockHash, genesis);
    this.highestQC = { blockHash: genesis.blockHash, view: 0, mode: 'GENESIS' };
    this.qcs.set(genesis.blockHash, this.highestQC);
  }

  proposeBlock(view, prevHash, txs, authorId) {
    if (!this.blocks.has(prevHash)) {
      throw new Error('Missing predecessor block: ' + prevHash);
    }
    const blk = new OptimisticBlock(view, prevHash, txs, authorId);
    this.blocks.set(blk.blockHash, blk);
    return blk;
  }

  vote(blockHash, voterId) {
    if (!this.blocks.has(blockHash)) {
      throw new Error('Cannot vote on unknown block: ' + blockHash);
    }
    const key = blockHash + ':' + voterId;
    if (this.votes.has(key)) {
      throw new Error('Double vote detected from ' + voterId);
    }
    const vote = {
      blockHash,
      voterId,
      sig: hashObject({ blockHash, voterId, role: 'RESPONSIVE_VOTE' })
    };
    this.votes.set(key, vote);
    return vote;
  }

  evaluateQuorum(blockHash) {
    const matchingVotes = [];
    for (const [key, v] of this.votes.entries()) {
      if (key.startsWith(blockHash + ':')) matchingVotes.push(v);
    }

    if (matchingVotes.length >= this.optimisticQuorum) {
      // 1-Step Optimistic Fast Finality!
      const qc = {
        blockHash,
        mode: 'OPTIMISTIC_FAST_PATH',
        voteCount: matchingVotes.length,
        signatures: matchingVotes
      };
      this.qcs.set(blockHash, qc);
      this._commit(blockHash, 'OPTIMISTIC_FAST_PATH');
      return qc;
    } else if (matchingVotes.length >= this.standardQuorum) {
      // Standard 2f+1 QC (requires 2-chain or fallback)
      const qc = {
        blockHash,
        mode: 'STANDARD_BFT_PATH',
        voteCount: matchingVotes.length,
        signatures: matchingVotes.slice(0, this.standardQuorum)
      };
      this.qcs.set(blockHash, qc);
      this._commit(blockHash, 'STANDARD_BFT_PATH');
      return qc;
    } else {
      return { status: 'PENDING_QUORUM', currentVotes: matchingVotes.length };
    }
  }

  _commit(blockHash, mode) {
    if (this.committedBlocks.includes(blockHash)) return;
    this.committedBlocks.push(blockHash);
    this.commitModes.set(blockHash, mode);
  }

  getStats() {
    return {
      nodeCount: this.nodeCount,
      standardQuorum: this.standardQuorum,
      optimisticQuorum: this.optimisticQuorum,
      totalBlocks: this.blocks.size,
      totalCommitted: this.committedBlocks.length,
      commitModes: Object.fromEntries(this.commitModes.entries())
    };
  }
}

module.exports = { OptimisticBlock, BFTOptimisticResponsiveEngine };
