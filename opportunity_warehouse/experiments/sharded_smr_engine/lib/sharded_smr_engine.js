/**
 * Sharded SMR Consensus Engine
 * Implements an asynchronous BFT cross-shard state machine replication engine.
 * Coordinates atomic 2-Phase Commit (2PC) over independent BFT shard clusters,
 * ensuring all-or-nothing cross-shard atomicity with Byzantine quorum validation.
 */

const crypto = require('crypto');

function sha256(data) {
  return crypto.createHash('sha256').update(typeof data === 'string' ? data : JSON.stringify(data)).digest('hex');
}

class ShardNode {
  constructor(shardId, nodeId) {
    this.shardId = shardId;
    this.nodeId = nodeId;
    this.state = new Map(); // key -> value
    this.locks = new Map(); // key -> txId
  }

  prepare(txId, readKeys, writeOperations) {
    // Check for lock conflicts
    for (const key of readKeys.concat(Object.keys(writeOperations))) {
      if (this.locks.has(key) && this.locks.get(key) !== txId) {
        return { vote: 'ABORT', reason: 'LOCK_CONFLICT', shardId: this.shardId, nodeId: this.nodeId };
      }
    }

    // Acquire speculative locks
    for (const key of Object.keys(writeOperations)) {
      this.locks.set(key, txId);
    }

    const voteSig = sha256(`${this.nodeId}_prepare_${txId}_${this.shardId}`);
    return { vote: 'PREPARE', signature: voteSig, shardId: this.shardId, nodeId: this.nodeId };
  }

  commit(txId, writeOperations) {
    for (const [k, v] of Object.entries(writeOperations)) {
      this.state.set(k, v);
      if (this.locks.get(k) === txId) {
        this.locks.delete(k);
      }
    }
    return sha256(`${this.nodeId}_commit_${txId}`);
  }

  abort(txId, writeOperations) {
    for (const k of Object.keys(writeOperations)) {
      if (this.locks.get(k) === txId) {
        this.locks.delete(k);
      }
    }
    return sha256(`${this.nodeId}_abort_${txId}`);
  }
}

class ShardCluster {
  constructor(shardId, nodeIds, faultTolerance = 1) {
    this.shardId = shardId;
    this.nodeIds = nodeIds;
    this.f = faultTolerance;
    this.quorum = 2 * this.f + 1;
    this.nodes = nodeIds.map(id => new ShardNode(shardId, id));
  }

  prepareTransaction(txId, readKeys, writeOperations) {
    const prepares = [];
    const aborts = [];

    for (const node of this.nodes) {
      const res = node.prepare(txId, readKeys, writeOperations);
      if (res.vote === 'PREPARE') prepares.push(res);
      else aborts.push(res);
    }

    if (prepares.length >= this.quorum) {
      return {
        status: 'SHARD_PREPARED',
        shardId: this.shardId,
        signatures: prepares.map(p => ({ nodeId: p.nodeId, sig: p.signature })),
        qcId: sha256({ txId, shardId: this.shardId, status: 'PREPARED' })
      };
    }

    return {
      status: 'SHARD_ABORTED',
      shardId: this.shardId,
      details: aborts
    };
  }

  commitTransaction(txId, writeOperations) {
    for (const node of this.nodes) {
      node.commit(txId, writeOperations);
    }
  }

  abortTransaction(txId, writeOperations) {
    for (const node of this.nodes) {
      node.abort(txId, writeOperations);
    }
  }

  get(key) {
    return this.nodes[0].state.get(key);
  }
}

class ShardedSMREngine {
  constructor(shardConfigs, faultTolerance = 1) {
    // shardConfigs: { 'shard_A': ['n0', 'n1', 'n2', 'n3'], 'shard_B': ['n0', 'n1', 'n2', 'n3'] }
    this.shards = new Map();
    for (const [shardId, nodes] of Object.entries(shardConfigs)) {
      this.shards.set(shardId, new ShardCluster(shardId, nodes, faultTolerance));
    }
    this.committedTransactions = [];
  }

  executeCrossShardTx(txId, shardOperations) {
    // shardOperations: { 'shard_A': { reads: [], writes: { key1: 'val1' } }, 'shard_B': { ... } }
    const preparedQCs = [];

    // Phase 1: Prepare across all participant shards
    for (const [shardId, ops] of Object.entries(shardOperations)) {
      const cluster = this.shards.get(shardId);
      if (!cluster) throw new Error('Unknown shard: ' + shardId);

      const prepRes = cluster.prepareTransaction(txId, ops.reads || [], ops.writes || {});
      if (prepRes.status !== 'SHARD_PREPARED') {
        // Any shard fails prepare -> Global Abort!
        this.globalAbort(txId, shardOperations);
        return { success: false, status: 'GLOBAL_ABORTED', failedShard: shardId };
      }
      preparedQCs.push(prepRes);
    }

    // Phase 2: All shards successfully prepared -> Global Commit!
    this.globalCommit(txId, shardOperations);
    this.committedTransactions.push({ txId, preparedQCs, timestamp: new Date().toISOString() });

    return {
      success: true,
      status: 'GLOBAL_COMMITTED',
      txId,
      participantShardCount: preparedQCs.length,
      preparedQCs
    };
  }

  globalCommit(txId, shardOperations) {
    for (const [shardId, ops] of Object.entries(shardOperations)) {
      const cluster = this.shards.get(shardId);
      cluster.commitTransaction(txId, ops.writes || {});
    }
  }

  globalAbort(txId, shardOperations) {
    for (const [shardId, ops] of Object.entries(shardOperations)) {
      const cluster = this.shards.get(shardId);
      cluster.abortTransaction(txId, ops.writes || {});
    }
  }

  getShardValue(shardId, key) {
    const cluster = this.shards.get(shardId);
    return cluster ? cluster.get(key) : undefined;
  }
}

module.exports = { ShardedSMREngine, ShardCluster, ShardNode };
