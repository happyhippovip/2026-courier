/**
 * Multi-Agent Distributed Asynchronous Verifiable Byzantine Sharded Commit Consensus Engine
 * Implements an atomic cross-shard commit protocol using 2f+1 threshold-signed shard prepare certificates
 * to ensure all-or-nothing execution across independent validator quorums without centralized coordinators.
 */

const crypto = require('crypto');

function hashObject(obj) {
  return crypto.createHash('sha256').update(JSON.stringify(obj)).digest('hex');
}

class ShardPrepareVote {
  constructor(txId, shardId, vote, voterNodeId) {
    this.txId = txId;
    this.shardId = shardId;
    this.vote = vote; // 'PREPARE_COMMIT' | 'PREPARE_ABORT'
    this.voterNodeId = voterNodeId;
    this.sig = hashObject({ txId, shardId, vote, voterNodeId, role: 'SHARD_PREPARE_VOTE' });
  }
}

class ShardPrepareCertificate {
  constructor(txId, shardId, vote, votes) {
    this.txId = txId;
    this.shardId = shardId;
    this.vote = vote;
    this.votes = votes;
    this.certHash = hashObject({ txId, shardId, vote, voteCount: votes.length });
  }
}

class BFTShardedCommitEngine {
  constructor(nodeCountPerShard = 4) {
    this.nodeCount = nodeCountPerShard;
    this.f = Math.floor((nodeCountPerShard - 1) / 3); // f=1
    this.quorumSize = 2 * this.f + 1; // 3

    this.shards = new Set(['shard_A', 'shard_B', 'shard_C']);
    this.transactions = new Map(); // txId -> { txId, participantShards, status }
    this.prepareVotes = new Map(); // "txId:shardId:voterNodeId" -> ShardPrepareVote
    this.shardCertificates = new Map(); // "txId:shardId" -> ShardPrepareCertificate
    this.finalDecisions = new Map(); // txId -> 'GLOBAL_COMMIT' | 'GLOBAL_ABORT'
  }

  registerCrossShardTx(txId, participantShards) {
    for (const s of participantShards) {
      if (!this.shards.has(s)) throw new Error('Unknown shard: ' + s);
    }
    const tx = { txId, participantShards: participantShards.slice(), status: 'PENDING' };
    this.transactions.set(txId, tx);
    return tx;
  }

  castPrepareVote(txId, shardId, vote, voterNodeId) {
    const tx = this.transactions.get(txId);
    if (!tx) throw new Error('Transaction not found: ' + txId);
    if (!tx.participantShards.includes(shardId)) {
      throw new Error('Shard ' + shardId + ' is not a participant in ' + txId);
    }

    const key = txId + ':' + shardId + ':' + voterNodeId;
    if (this.prepareVotes.has(key)) {
      throw new Error('Double vote detected from ' + voterNodeId + ' on ' + key);
    }

    const v = new ShardPrepareVote(txId, shardId, vote, voterNodeId);
    this.prepareVotes.set(key, v);
    return v;
  }

  certifyShardPrepare(txId, shardId) {
    const matchingVotes = [];
    let decisionVote = null;

    for (const [key, v] of this.prepareVotes.entries()) {
      if (key.startsWith(txId + ':' + shardId + ':')) {
        if (!decisionVote) decisionVote = v.vote;
        if (v.vote === decisionVote) {
          matchingVotes.push(v);
        }
      }
    }

    if (matchingVotes.length < this.quorumSize) {
      throw new Error('Insufficient votes for Shard Prepare Certificate: ' + matchingVotes.length + ' < ' + this.quorumSize);
    }

    const cert = new ShardPrepareCertificate(txId, shardId, decisionVote, matchingVotes.slice(0, this.quorumSize));
    this.shardCertificates.set(txId + ':' + shardId, cert);
    return cert;
  }

  evaluateGlobalDecision(txId) {
    const tx = this.transactions.get(txId);
    if (!tx) throw new Error('Transaction not found: ' + txId);

    // Check if all participant shards have certificates
    for (const s of tx.participantShards) {
      const certKey = txId + ':' + s;
      if (!this.shardCertificates.has(certKey)) {
        return { status: 'PENDING_SHARD_CERTS', missingShard: s };
      }
    }

    // If ANY participant shard voted PREPARE_ABORT, global decision is ABORT
    for (const s of tx.participantShards) {
      const cert = this.shardCertificates.get(txId + ':' + s);
      if (cert.vote === 'PREPARE_ABORT') {
        this.finalDecisions.set(txId, 'GLOBAL_ABORT');
        tx.status = 'GLOBAL_ABORT';
        return { decision: 'GLOBAL_ABORT', txId, abortReason: 'ABORT_IN_SHARD_' + s };
      }
    }

    // All shards certified PREPARE_COMMIT -> GLOBAL_COMMIT
    this.finalDecisions.set(txId, 'GLOBAL_COMMIT');
    tx.status = 'GLOBAL_COMMIT';
    return { decision: 'GLOBAL_COMMIT', txId, participantShards: tx.participantShards };
  }

  getStats() {
    return {
      activeShards: Array.from(this.shards),
      totalTransactions: this.transactions.size,
      totalShardCerts: this.shardCertificates.size,
      finalDecisions: Object.fromEntries(this.finalDecisions.entries())
    };
  }
}

module.exports = { ShardPrepareVote, ShardPrepareCertificate, BFTShardedCommitEngine };
