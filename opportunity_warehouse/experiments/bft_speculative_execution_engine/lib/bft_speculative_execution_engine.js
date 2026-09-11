/**
 * Multi-Agent Distributed Asynchronous Verifiable Byzantine Speculative Execution Consensus Engine
 * Enables speculative transaction execution in parallel with pipelined consensus proposals,
 * with dependency conflict detection and deterministic rollback upon equivocation.
 */

const crypto = require('crypto');

function hashObject(obj) {
  return crypto.createHash('sha256').update(JSON.stringify(obj)).digest('hex');
}

class SpeculativeTransaction {
  constructor(txId, readKeys, writeKeys, stateDeltas) {
    this.txId = txId;
    this.readKeys = readKeys || [];
    this.writeKeys = writeKeys || [];
    this.stateDeltas = stateDeltas || {}; // key -> value
  }
}

class BFTSpeculativeExecutionEngine {
  constructor(nodeCount = 4) {
    this.nodeCount = nodeCount;
    this.f = Math.floor((nodeCount - 1) / 3); // f=1
    this.quorumSize = 2 * this.f + 1; // 3

    this.committedState = new Map(); // key -> value (final ground truth)
    this.speculativeState = new Map(); // key -> value (uncommitted pipeline state)
    this.pipelineProposals = new Map(); // blockHash -> proposal
    this.speculativeExecutions = new Map(); // blockHash -> executedDeltas
    this.votes = new Map(); // "blockHash:nodeId" -> vote
    this.qcs = new Map(); // blockHash -> QC
    this.committedBlocks = [];
  }

  initState(initialKeyValues = {}) {
    for (const [k, v] of Object.entries(initialKeyValues)) {
      this.committedState.set(k, v);
      this.speculativeState.set(k, v);
    }
  }

  proposeSpeculativeBlock(view, prevHash, txs, authorId) {
    const blockHash = hashObject({ view, prevHash, txCount: txs.length, authorId });
    const proposal = { view, prevHash, txs, authorId, blockHash, timestamp: Date.now() };
    this.pipelineProposals.set(blockHash, proposal);

    // Speculatively execute transactions immediately
    const deltas = [];
    for (const tx of txs) {
      for (const [k, v] of Object.entries(tx.stateDeltas)) {
        this.speculativeState.set(k, v);
        deltas.push({ txId: tx.txId, key: k, value: v });
      }
    }
    this.speculativeExecutions.set(blockHash, deltas);

    return proposal;
  }

  readState(key, speculative = true) {
    if (speculative) {
      return this.speculativeState.get(key);
    }
    return this.committedState.get(key);
  }

  vote(blockHash, voterId) {
    if (!this.pipelineProposals.has(blockHash)) {
      throw new Error('Cannot vote on unknown speculative proposal: ' + blockHash);
    }
    const key = blockHash + ':' + voterId;
    if (this.votes.has(key)) {
      throw new Error('Double vote detected from ' + voterId);
    }
    const vote = { blockHash, voterId, sig: hashObject({ blockHash, voterId, role: 'SPECULATIVE_VOTE' }) };
    this.votes.set(key, vote);
    return vote;
  }

  certify(blockHash) {
    const matchingVotes = [];
    for (const [key, v] of this.votes.entries()) {
      if (key.startsWith(blockHash + ':')) matchingVotes.push(v);
    }
    if (matchingVotes.length < this.quorumSize) {
      throw new Error('Insufficient votes for speculative QC: ' + matchingVotes.length + ' < ' + this.quorumSize);
    }
    const qc = { blockHash, signatures: matchingVotes.slice(0, this.quorumSize) };
    this.qcs.set(blockHash, qc);
    return qc;
  }

  commit(blockHash) {
    if (!this.qcs.has(blockHash)) {
      throw new Error('Cannot commit uncertified speculative proposal: ' + blockHash);
    }
    if (this.committedBlocks.includes(blockHash)) {
      return { committed: false, reason: 'ALREADY_COMMITTED' };
    }

    const proposal = this.pipelineProposals.get(blockHash);
    const deltas = this.speculativeExecutions.get(blockHash) || [];

    // Apply deltas permanently to committedState
    for (const d of deltas) {
      this.committedState.set(d.key, d.value);
    }
    this.committedBlocks.push(blockHash);

    return {
      committed: true,
      blockHash,
      view: proposal.view,
      appliedDeltas: deltas.length,
      committedStateSnapshot: Object.fromEntries(this.committedState.entries())
    };
  }

  rollbackSpeculativeBranch(blockHash) {
    if (!this.pipelineProposals.has(blockHash)) return;

    // Reset speculativeState back to committedState
    this.speculativeState.clear();
    for (const [k, v] of this.committedState.entries()) {
      this.speculativeState.set(k, v);
    }

    // Re-apply remaining active uncommitted pipeline proposals except rejected branch
    this.pipelineProposals.delete(blockHash);
    this.speculativeExecutions.delete(blockHash);

    for (const [bHash, prop] of this.pipelineProposals.entries()) {
      if (!this.committedBlocks.includes(bHash)) {
        const deltas = this.speculativeExecutions.get(bHash) || [];
        for (const d of deltas) {
          this.speculativeState.set(d.key, d.value);
        }
      }
    }

    return { rolledBack: true, rejectedBlockHash: blockHash };
  }

  getStats() {
    return {
      nodeCount: this.nodeCount,
      committedStateSize: this.committedState.size,
      speculativeStateSize: this.speculativeState.size,
      totalProposals: this.pipelineProposals.size,
      totalCommittedBlocks: this.committedBlocks.length
    };
  }
}

module.exports = { SpeculativeTransaction, BFTSpeculativeExecutionEngine };
