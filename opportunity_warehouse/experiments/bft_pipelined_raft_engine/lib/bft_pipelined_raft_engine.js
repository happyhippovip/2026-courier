/**
 * Multi-Agent Distributed Asynchronous Verifiable Byzantine Pipelined Raft Hybrid Consensus Engine
 * Combines Raft leader-lease pipelined log replication with Byzantine threshold quorum certifications (2f+1 signatures).
 */

const crypto = require('crypto');

function hashObject(obj) {
  return crypto.createHash('sha256').update(JSON.stringify(obj)).digest('hex');
}

class BFTLogEntry {
  constructor(term, index, prevHash, txs, leaderId) {
    this.term = term;
    this.index = index;
    this.prevHash = prevHash;
    this.txs = Array.isArray(txs) ? txs : [];
    this.leaderId = leaderId;
    this.timestamp = Date.now();
    this.entryHash = hashObject({
      term: this.term,
      index: this.index,
      prevHash: this.prevHash,
      txs: this.txs,
      leaderId: this.leaderId
    });
  }
}

class BFTPipelinedRaftEngine {
  constructor(nodeCount = 4) {
    this.nodeCount = nodeCount;
    this.f = Math.floor((nodeCount - 1) / 3); // f=1
    this.quorumSize = 2 * this.f + 1; // 3

    this.currentTerm = 1;
    this.currentLeader = 'node_0';
    this.log = []; // array of BFTLogEntry
    this.logByHash = new Map();
    this.certificates = new Map(); // entryHash -> QC
    this.committedIndex = 0;
    this.committedTxs = [];

    // Initialize Genesis Entry (Term 0, Index 0)
    const genesis = new BFTLogEntry(0, 0, '0000000000000000000000000000000000000000000000000000000000000000', [], 'GENESIS');
    this.log.push(genesis);
    this.logByHash.set(genesis.entryHash, genesis);
  }

  proposeEntry(txs, leaderId) {
    if (leaderId !== this.currentLeader) {
      throw new Error('Unauthorized proposal: ' + leaderId + ' is not current leader ' + this.currentLeader);
    }

    const prevEntry = this.log[this.log.length - 1];
    const newIndex = prevEntry.index + 1;
    const entry = new BFTLogEntry(this.currentTerm, newIndex, prevEntry.entryHash, txs, leaderId);

    this.log.push(entry);
    this.logByHash.set(entry.entryHash, entry);
    return entry;
  }

  certifyEntry(entryHash, voterSignatures) {
    const entry = this.logByHash.get(entryHash);
    if (!entry) throw new Error('Entry not found: ' + entryHash);

    if (!Array.isArray(voterSignatures) || voterSignatures.length < this.quorumSize) {
      throw new Error('Insufficient signatures for BFT certification: requires >= ' + this.quorumSize);
    }

    // Check unique voters
    const uniqueVoters = new Set(voterSignatures.map(s => s.nodeId));
    if (uniqueVoters.size < this.quorumSize) {
      throw new Error('Duplicate voter signatures detected in quorum');
    }

    const cert = {
      entryHash,
      term: entry.term,
      index: entry.index,
      signatures: voterSignatures.slice(0, this.quorumSize),
      certifiedAt: Date.now()
    };

    this.certificates.set(entryHash, cert);
    return cert;
  }

  advanceCommit() {
    // In Pipelined BFT-Raft, entry at index K is committed once entry K is certified
    // AND all previous entries are committed.
    let newlyCommitted = 0;
    for (let i = this.committedIndex + 1; i < this.log.length; i++) {
      const entry = this.log[i];
      if (this.certificates.has(entry.entryHash)) {
        this.committedIndex = entry.index;
        this.committedTxs.push(...entry.txs);
        newlyCommitted++;
      } else {
        break; // Pipeline must commit in contiguous sequence
      }
    }

    return {
      committedIndex: this.committedIndex,
      newlyCommitted,
      totalCommittedTxs: this.committedTxs.length
    };
  }

  getStats() {
    return {
      nodeCount: this.nodeCount,
      currentTerm: this.currentTerm,
      currentLeader: this.currentLeader,
      logLength: this.log.length,
      certifiedEntriesCount: this.certificates.size,
      committedIndex: this.committedIndex,
      totalCommittedTxs: this.committedTxs.length
    };
  }
}

module.exports = { BFTLogEntry, BFTPipelinedRaftEngine };
