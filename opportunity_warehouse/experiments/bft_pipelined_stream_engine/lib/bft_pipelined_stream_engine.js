/**
 * Multi-Agent Distributed Asynchronous Verifiable Byzantine Pipelined Streaming Consensus Engine
 * Implements high-frequency micro-block streaming with continuous pipelining and 2-chain fast finality.
 */

const crypto = require('crypto');

function hashObject(obj) {
  return crypto.createHash('sha256').update(JSON.stringify(obj)).digest('hex');
}

class StreamingMicroBlock {
  constructor(streamSeq, view, prevHash, txs, authorId) {
    this.streamSeq = streamSeq;
    this.view = view;
    this.prevHash = prevHash;
    this.txs = Array.isArray(txs) ? txs : [];
    this.authorId = authorId;
    this.timestamp = Date.now();
    this.blockHash = hashObject({
      streamSeq: this.streamSeq,
      view: this.view,
      prevHash: this.prevHash,
      txs: this.txs,
      authorId: this.authorId
    });
  }
}

class BFTPipelinedStreamEngine {
  constructor(nodeCount = 4) {
    this.nodeCount = nodeCount;
    this.f = Math.floor((nodeCount - 1) / 3); // f=1
    this.quorumSize = 2 * this.f + 1; // 3

    this.microBlocks = new Map(); // blockHash -> StreamingMicroBlock
    this.votes = new Map(); // "blockHash:nodeId" -> vote
    this.streamQCs = new Map(); // blockHash -> QC
    this.committedBlocks = [];
    this.committedTxs = [];

    // Genesis MicroBlock
    const genesisHash = '0000000000000000000000000000000000000000000000000000000000000000';
    const genesis = new StreamingMicroBlock(0, 0, genesisHash, [], 'GENESIS');
    this.microBlocks.set(genesis.blockHash, genesis);
    this.highestQC = { blockHash: genesis.blockHash, streamSeq: 0, signatures: [] };
    this.streamQCs.set(genesis.blockHash, this.highestQC);
  }

  streamMicroBlock(streamSeq, view, prevHash, txs, authorId) {
    if (!this.microBlocks.has(prevHash)) {
      throw new Error('Previous micro-block not found: ' + prevHash);
    }

    const prev = this.microBlocks.get(prevHash);
    if (streamSeq !== prev.streamSeq + 1) {
      throw new Error('Non-contiguous stream sequence: expected ' + (prev.streamSeq + 1) + ', got ' + streamSeq);
    }

    const mb = new StreamingMicroBlock(streamSeq, view, prevHash, txs, authorId);
    this.microBlocks.set(mb.blockHash, mb);
    return mb;
  }

  castStreamVote(blockHash, voterNodeId) {
    const mb = this.microBlocks.get(blockHash);
    if (!mb) throw new Error('Micro-block not found for vote: ' + blockHash);

    const voteKey = blockHash + ':' + voterNodeId;
    if (this.votes.has(voteKey)) {
      throw new Error('Double streaming vote detected from node ' + voterNodeId);
    }

    const vote = {
      blockHash,
      voterNodeId,
      sig: hashObject({ blockHash, voterNodeId, role: 'STREAM_VOTE' })
    };
    this.votes.set(voteKey, vote);
    return vote;
  }

  certifyMicroBlock(blockHash) {
    const mb = this.microBlocks.get(blockHash);
    if (!mb) throw new Error('Micro-block not found: ' + blockHash);

    const matchingVotes = [];
    for (const [key, v] of this.votes.entries()) {
      if (key.startsWith(blockHash + ':')) {
        matchingVotes.push(v);
      }
    }

    if (matchingVotes.length < this.quorumSize) {
      throw new Error('Insufficient stream votes for QC: has ' + matchingVotes.length + ', requires ' + this.quorumSize);
    }

    const qc = {
      blockHash,
      streamSeq: mb.streamSeq,
      signatures: matchingVotes.slice(0, this.quorumSize)
    };
    this.streamQCs.set(blockHash, qc);
    if (mb.streamSeq > this.highestQC.streamSeq) {
      this.highestQC = qc;
    }
    return qc;
  }

  evaluate2ChainCommit(b2Hash) {
    // 2-Chain Streaming Finality: B2 -> B1
    // If B2 extends B1 and both have QCs, B1 is committed!
    const b2 = this.microBlocks.get(b2Hash);
    if (!b2) return null;

    const b1 = this.microBlocks.get(b2.prevHash);
    if (!b1 || !this.streamQCs.has(b1.blockHash) || !this.streamQCs.has(b2.blockHash)) {
      return null;
    }

    return this._commitMicroBlock(b1);
  }

  _commitMicroBlock(mb) {
    if (this.committedBlocks.includes(mb.blockHash)) {
      return { committed: false, reason: 'ALREADY_COMMITTED' };
    }

    this.committedBlocks.push(mb.blockHash);
    this.committedTxs.push(...mb.txs);

    return {
      committed: true,
      mode: 'PIPELINED_2CHAIN_STREAMING_COMMIT',
      streamSeq: mb.streamSeq,
      blockHash: mb.blockHash,
      txs: mb.txs,
      totalCommittedTxs: this.committedTxs.length
    };
  }

  getStats() {
    return {
      nodeCount: this.nodeCount,
      microBlocksCount: this.microBlocks.size,
      streamQCsCount: this.streamQCs.size,
      committedBlocksCount: this.committedBlocks.length,
      totalCommittedTxs: this.committedTxs.length
    };
  }
}

module.exports = { StreamingMicroBlock, BFTPipelinedStreamEngine };
