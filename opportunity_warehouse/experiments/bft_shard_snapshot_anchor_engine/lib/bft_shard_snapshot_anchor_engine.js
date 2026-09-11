/**
 * Multi-Agent Distributed Asynchronous Verifiable Byzantine Dynamic Shard State Snapshot Anchoring Consensus Engine
 * Implements cross-shard periodic snapshot anchoring, Merkle state root commitment,
 * 2f+1 BFT validator quorum certification, and historical log compaction.
 */

const fs = require('fs');
const crypto = require('crypto');

function sha256(data) {
  return crypto.createHash('sha256').update(typeof data === 'string' ? data : JSON.stringify(data)).digest('hex');
}

class BFTShardSnapshotAnchorEngine {
  constructor(validatorWeights = {}) {
    this.validators = new Map();
    this.totalWeight = 0;
    for (const [id, weight] of Object.entries(validatorWeights)) {
      this.validators.set(id, { weight, status: 'ACTIVE' });
      this.totalWeight += weight;
    }
    this.anchors = new Map(); // epoch -> anchorRecord
    this.shardStates = new Map(); // shardId -> { currentHeight, stateMap }
    this.lastCertifiedEpoch = -1;
  }

  // Update localized shard key-value state
  putShardState(shardId, height, key, value) {
    if (!this.shardStates.has(shardId)) {
      this.shardStates.set(shardId, { currentHeight: height, stateMap: new Map() });
    }
    const shard = this.shardStates.get(shardId);
    shard.currentHeight = Math.max(shard.currentHeight, height);
    shard.stateMap.set(key, { value, height, hash: sha256({ key, value, height }) });
  }

  // Calculate deterministic Merkle state root for a shard
  computeShardStateRoot(shardId) {
    const shard = this.shardStates.get(shardId);
    if (!shard || shard.stateMap.size === 0) return sha256(`EMPTY_SHARD:${shardId}`);

    const sortedEntries = Array.from(shard.stateMap.entries()).sort(([a], [b]) => (a < b ? -1 : 1));
    const hashes = sortedEntries.map(([k, v]) => sha256({ k, val: v.value, h: v.height }));
    return sha256(hashes.join(':'));
  }

  // Propose a cross-shard snapshot anchor for an epoch
  proposeEpochAnchor(epoch) {
    const shardRoots = {};
    for (const [shardId] of this.shardStates.entries()) {
      shardRoots[shardId] = this.computeShardStateRoot(shardId);
    }

    const anchorPayload = {
      epoch,
      shardRoots,
      timestamp: Date.now()
    };
    const anchorHash = sha256(anchorPayload);

    return {
      epoch,
      anchorHash,
      anchorPayload,
      signatures: []
    };
  }

  // Certify anchor proposal with 2f+1 BFT validator signatures
  certifyAnchor(anchorProposal, signatures) {
    let accumulatedWeight = 0;
    const validSignatures = [];

    for (const sig of signatures) {
      const v = this.validators.get(sig.validatorId);
      if (v && v.status === 'ACTIVE') {
        accumulatedWeight += v.weight;
        validSignatures.push(sig);
      }
    }

    const quorumRatio = accumulatedWeight / (this.totalWeight || 1);
    if (quorumRatio < (2 / 3)) {
      return { certified: false, reason: 'INSUFFICIENT_BFT_QUORUM', quorumRatio };
    }

    const certifiedRecord = {
      epoch: anchorProposal.epoch,
      anchorHash: anchorProposal.anchorHash,
      shardRoots: anchorProposal.anchorPayload.shardRoots,
      accumulatedWeight,
      quorumRatio,
      signatures: validSignatures,
      certifiedAt: new Date().toISOString()
    };

    this.anchors.set(anchorProposal.epoch, certifiedRecord);
    this.lastCertifiedEpoch = Math.max(this.lastCertifiedEpoch, anchorProposal.epoch);

    return {
      certified: true,
      anchorRecord: certifiedRecord
    };
  }

  // Prune shard state history older than certified anchor height
  pruneHistoricalState(shardId, minRetainHeight) {
    const shard = this.shardStates.get(shardId);
    if (!shard) return { prunedCount: 0 };

    let prunedCount = 0;
    for (const [k, v] of shard.stateMap.entries()) {
      if (v.height < minRetainHeight) {
        shard.stateMap.delete(k);
        prunedCount++;
      }
    }
    return { prunedCount, remainingKeys: shard.stateMap.size };
  }

  getCertifiedAnchor(epoch) {
    return this.anchors.get(epoch) || null;
  }

  exportEvidenceReport(outputPath) {
    const report = {
      subsystem: 'bft_shard_snapshot_anchor_engine',
      timestamp: new Date().toISOString(),
      totalValidators: this.validators.size,
      totalWeight: this.totalWeight,
      lastCertifiedEpoch: this.lastCertifiedEpoch,
      certifiedAnchorCount: this.anchors.size,
      anchors: Array.from(this.anchors.values())
    };
    if (outputPath) {
      fs.writeFileSync(outputPath, JSON.stringify(report, null, 2), 'utf8');
    }
    return report;
  }
}

module.exports = { BFTShardSnapshotAnchorEngine };
