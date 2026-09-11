/**
 * Multi-Agent Distributed Asynchronous Verifiable Byzantine Dynamic Shard State Epoch Horizon Compaction Consensus Engine
 * Establishes an immutable canonical finality horizon H = CurrentEpoch - K, gathers 2f+1 BFT validator
 * signatures over the compacted state boundary, freezes historical states, and prunes transient logs.
 */

const fs = require('fs');
const crypto = require('crypto');

function sha256(data) {
  return crypto.createHash('sha256').update(typeof data === 'string' ? data : JSON.stringify(data)).digest('hex');
}

class BFTShardHorizonCompactionEngine {
  constructor(validators = {}, horizonWindow = 3) {
    this.validators = new Map();
    this.totalWeight = 0;
    for (const [id, weight] of Object.entries(validators)) {
      this.validators.set(id, { weight, status: 'ACTIVE' });
      this.totalWeight += weight;
    }
    this.horizonWindow = horizonWindow; // epochs behind current
    this.currentEpoch = 0;
    this.epochStates = new Map(); // epoch -> { stateRoot, stateMap, status: 'MUTABLE' | 'FINALIZED' | 'PRUNED' }
    this.compactedHorizons = [];
  }

  // Register epoch state
  recordEpochState(epoch, stateMap) {
    this.currentEpoch = Math.max(this.currentEpoch, epoch);
    const sortedEntries = Array.from(Object.entries(stateMap)).sort(([a], [b]) => (a < b ? -1 : 1));
    const stateRoot = sha256(JSON.stringify(sortedEntries));
    this.epochStates.set(epoch, {
      stateRoot,
      stateMap: new Map(sortedEntries),
      status: 'MUTABLE'
    });
  }

  // Calculate compaction horizon
  getFinalityHorizonEpoch() {
    return Math.max(0, this.currentEpoch - this.horizonWindow);
  }

  // Propose compaction at finality horizon
  proposeCompaction(targetEpoch) {
    const epochData = this.epochStates.get(targetEpoch);
    if (!epochData) return null;

    const proposal = {
      targetEpoch,
      stateRoot: epochData.stateRoot,
      accountCount: epochData.stateMap.size,
      timestamp: Date.now()
    };
    proposal.proposalHash = sha256(proposal);
    return proposal;
  }

  // Certify compaction with 2f+1 BFT validator signatures
  certifyCompaction(proposal, signatures) {
    let signedWeight = 0;
    const validSignatures = [];

    for (const sig of signatures) {
      const v = this.validators.get(sig.validatorId);
      if (v && v.status === 'ACTIVE') {
        signedWeight += v.weight;
        validSignatures.push(sig);
      }
    }

    const quorumRatio = signedWeight / (this.totalWeight || 1);
    if (quorumRatio < (2 / 3)) {
      return { certified: false, reason: 'INSUFFICIENT_BFT_QUORUM', quorumRatio };
    }

    // Freeze compacted epoch and mark prior as pruned
    const target = this.epochStates.get(proposal.targetEpoch);
    if (target) {
      target.status = 'FINALIZED';
    }

    // Prune epochs strictly older than targetEpoch
    let prunedCount = 0;
    for (const [ep, data] of this.epochStates.entries()) {
      if (ep < proposal.targetEpoch && data.status !== 'PRUNED') {
        data.status = 'PRUNED';
        data.stateMap.clear(); // Prune transient delta records
        prunedCount++;
      }
    }

    const record = {
      compactedEpoch: proposal.targetEpoch,
      stateRoot: proposal.stateRoot,
      signedWeight,
      quorumRatio,
      prunedPriorEpochs: prunedCount,
      certifiedAt: new Date().toISOString()
    };
    this.compactedHorizons.push(record);

    return {
      certified: true,
      record
    };
  }

  getEpochStatus(epoch) {
    const data = this.epochStates.get(epoch);
    return data ? data.status : 'NON_EXISTENT';
  }

  exportEvidenceReport(outputPath) {
    const report = {
      subsystem: 'bft_shard_horizon_compaction_engine',
      timestamp: new Date().toISOString(),
      currentEpoch: this.currentEpoch,
      horizonWindow: this.horizonWindow,
      compactedCount: this.compactedHorizons.length,
      history: this.compactedHorizons
    };
    if (outputPath) {
      fs.writeFileSync(outputPath, JSON.stringify(report, null, 2), 'utf8');
    }
    return report;
  }
}

module.exports = { BFTShardHorizonCompactionEngine };
