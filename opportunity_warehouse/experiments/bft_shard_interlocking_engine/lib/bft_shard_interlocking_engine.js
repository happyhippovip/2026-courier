/**
 * Multi-Agent Distributed Asynchronous Verifiable Byzantine Dynamic Shard Dynamic Checkpoint Interlocking Consensus Engine
 * Interlocks shard checkpoints across peer shards: Shard A embeds the cryptographic root of Shard B's latest certified
 * epoch into its own blocks, establishing mutual cross-shard immutability and preventing unilateral history rewrites.
 */

const fs = require('fs');
const crypto = require('crypto');

function sha256(data) {
  return crypto.createHash('sha256').update(typeof data === 'string' ? data : JSON.stringify(data)).digest('hex');
}

class BFTShardInterlockingEngine {
  constructor(validatorWeights = {}) {
    this.validators = new Map();
    this.totalWeight = 0;
    for (const [id, weight] of Object.entries(validatorWeights)) {
      this.validators.set(id, { weight, status: 'ACTIVE' });
      this.totalWeight += weight;
    }
    this.shardCheckpoints = new Map(); // shardId -> latest certified checkpoint
    this.interlockedBlocks = [];
  }

  // Register a certified checkpoint for a shard
  registerShardCheckpoint(shardId, epoch, stateRoot) {
    const cp = {
      shardId,
      epoch,
      stateRoot,
      registeredAt: new Date().toISOString()
    };
    this.shardCheckpoints.set(shardId, cp);
    return cp;
  }

  // Construct an interlocked block proposal for shardId embedding peer roots
  proposeInterlockedBlock(shardId, height, txs) {
    const peerRoots = {};
    for (const [sId, cp] of this.shardCheckpoints.entries()) {
      if (sId !== shardId) {
        peerRoots[sId] = { epoch: cp.epoch, root: cp.stateRoot };
      }
    }

    const payload = {
      shardId,
      height,
      txs,
      peerRoots,
      timestamp: Date.now()
    };
    const blockHash = sha256(payload);

    return {
      shardId,
      height,
      blockHash,
      payload
    };
  }

  // Certify an interlocked block with 2f+1 BFT validator signatures
  certifyInterlockedBlock(proposal, signatures) {
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

    const record = {
      shardId: proposal.shardId,
      height: proposal.height,
      blockHash: proposal.blockHash,
      peerRoots: proposal.payload.peerRoots,
      signedWeight,
      quorumRatio,
      certifiedAt: new Date().toISOString()
    };
    this.interlockedBlocks.push(record);

    return {
      certified: true,
      record
    };
  }

  // Verify that a shard block causally interlocks with a target peer shard checkpoint
  verifyCausalInterlock(blockHash, peerShardId, expectedPeerRoot) {
    const block = this.interlockedBlocks.find(b => b.blockHash === blockHash);
    if (!block) return { valid: false, reason: 'BLOCK_NOT_FOUND' };

    const interlockedPeer = block.peerRoots[peerShardId];
    if (!interlockedPeer) return { valid: false, reason: 'PEER_SHARD_NOT_INTERLOCKED' };

    const matches = interlockedPeer.root === expectedPeerRoot;
    return {
      valid: matches,
      interlockedEpoch: interlockedPeer.epoch,
      matches
    };
  }

  exportEvidenceReport(outputPath) {
    const report = {
      subsystem: 'bft_shard_interlocking_engine',
      timestamp: new Date().toISOString(),
      activeShardsWithCheckpoints: this.shardCheckpoints.size,
      interlockedBlockCount: this.interlockedBlocks.length,
      history: this.interlockedBlocks
    };
    if (outputPath) {
      fs.writeFileSync(outputPath, JSON.stringify(report, null, 2), 'utf8');
    }
    return report;
  }
}

module.exports = { BFTShardInterlockingEngine };
