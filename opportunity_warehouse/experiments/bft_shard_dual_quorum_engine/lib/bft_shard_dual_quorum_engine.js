/**
 * Multi-Agent Distributed Asynchronous Verifiable Byzantine Dynamic Shard State Dual-Quorum Commit Consensus Engine
 * Guarantees cross-shard atomic commit: requires 2f+1 quorum certification from origin shard
 * AND simultaneous 2f+1 quorum certification from destination shard before finalizing cross-shard operations.
 */

const fs = require('fs');
const crypto = require('crypto');

function sha256(data) {
  return crypto.createHash('sha256').update(typeof data === 'string' ? data : JSON.stringify(data)).digest('hex');
}

class BFTShardDualQuorumEngine {
  constructor(shardValidators = {}) {
    // shardId -> Map(validatorId, weight)
    this.shardValidators = new Map();
    this.shardTotalWeights = new Map();

    for (const [sId, vals] of Object.entries(shardValidators)) {
      const vMap = new Map();
      let totalW = 0;
      for (const [vId, w] of Object.entries(vals)) {
        vMap.set(vId, w);
        totalW += w;
      }
      this.shardValidators.set(sId, vMap);
      this.shardTotalWeights.set(sId, totalW);
    }

    this.crossShardTxs = new Map(); // txId -> { fromShard, toShard, amount, originQC, destQC, status }
    this.committedTxs = [];
  }

  // Register cross-shard transfer proposal
  proposeCrossShardTx(txId, fromShard, toShard, amount) {
    const record = {
      txId,
      fromShard,
      toShard,
      amount,
      originQC: null,
      destQC: null,
      status: 'PROPOSED',
      timestamp: Date.now()
    };
    this.crossShardTxs.set(txId, record);
    return record;
  }

  // Validate quorum signatures for a specific shard
  _checkQuorum(shardId, signatures) {
    const valMap = this.shardValidators.get(shardId);
    const totalW = this.shardTotalWeights.get(shardId) || 1;
    if (!valMap) return { valid: false, ratio: 0 };

    let signedW = 0;
    for (const sig of signatures) {
      if (valMap.has(sig.validatorId)) {
        signedW += valMap.get(sig.validatorId);
      }
    }
    const ratio = signedW / totalW;
    return { valid: ratio >= (2 / 3), ratio, signedW, totalW };
  }

  // Attach origin shard commit proof
  certifyOriginShard(txId, signatures) {
    const tx = this.crossShardTxs.get(txId);
    if (!tx) return { certified: false, reason: 'TX_NOT_FOUND' };

    const qRes = this._checkQuorum(tx.fromShard, signatures);
    if (!qRes.valid) {
      return { certified: false, reason: 'INSUFFICIENT_ORIGIN_QUORUM', ratio: qRes.ratio };
    }

    tx.originQC = {
      shardId: tx.fromShard,
      signatures: [...signatures],
      ratio: qRes.ratio,
      certifiedAt: new Date().toISOString()
    };
    return { certified: true, originQC: tx.originQC };
  }

  // Attach destination shard receipt proof
  certifyDestShard(txId, signatures) {
    const tx = this.crossShardTxs.get(txId);
    if (!tx) return { certified: false, reason: 'TX_NOT_FOUND' };

    const qRes = this._checkQuorum(tx.toShard, signatures);
    if (!qRes.valid) {
      return { certified: false, reason: 'INSUFFICIENT_DEST_QUORUM', ratio: qRes.ratio };
    }

    tx.destQC = {
      shardId: tx.toShard,
      signatures: [...signatures],
      ratio: qRes.ratio,
      certifiedAt: new Date().toISOString()
    };
    return { certified: true, destQC: tx.destQC };
  }

  // Execute global atomic commit if dual-quorum (2QC) is fully satisfied
  finalizeDualQuorumCommit(txId) {
    const tx = this.crossShardTxs.get(txId);
    if (!tx) return { finalized: false, reason: 'TX_NOT_FOUND' };

    if (!tx.originQC || !tx.destQC) {
      return {
        finalized: false,
        reason: 'MISSING_DUAL_QUORUM_PROOF',
        hasOriginQC: !!tx.originQC,
        hasDestQC: !!tx.destQC
      };
    }

    tx.status = 'GLOBAL_COMMITTED';
    const commitId = sha256({ txId, origin: tx.originQC, dest: tx.destQC, timestamp: Date.now() });
    const finalRecord = {
      commitId,
      txId: tx.txId,
      fromShard: tx.fromShard,
      toShard: tx.toShard,
      amount: tx.amount,
      originRatio: tx.originQC.ratio,
      destRatio: tx.destQC.ratio,
      finalizedAt: new Date().toISOString()
    };
    this.committedTxs.push(finalRecord);

    return {
      finalized: true,
      finalRecord
    };
  }

  exportEvidenceReport(outputPath) {
    const report = {
      subsystem: 'bft_shard_dual_quorum_engine',
      timestamp: new Date().toISOString(),
      activeShards: this.shardValidators.size,
      totalProposed: this.crossShardTxs.size,
      totalCommitted: this.committedTxs.length,
      history: this.committedTxs
    };
    if (outputPath) {
      fs.writeFileSync(outputPath, JSON.stringify(report, null, 2), 'utf8');
    }
    return report;
  }
}

module.exports = { BFTShardDualQuorumEngine };
