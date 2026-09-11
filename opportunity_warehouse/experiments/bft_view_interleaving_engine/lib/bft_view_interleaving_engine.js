/**
 * Byzantine View-Interleaving Consensus Engine
 * Enables concurrent multi-lane proposal pipelines across distinct validator views,
 * preventing leader bottleneck stalls and enforcing deterministic barrier linearization.
 */

const crypto = require('crypto');

function sha256(data) {
  return crypto.createHash('sha256').update(typeof data === 'string' ? data : JSON.stringify(data)).digest('hex');
}

class BFTViewInterleavingEngine {
  constructor(nodeId, totalNodes, faultTolerance) {
    this.nodeId = nodeId;
    this.totalNodes = totalNodes;
    this.f = faultTolerance;
    this.quorumThreshold = 2 * this.f + 1;
    this.lanes = new Map(); // laneId -> array of blocks
    this.interleavedCommitted = [];
  }

  proposeInLane(laneId, viewNumber, txPayload) {
    if (!this.lanes.has(laneId)) {
      this.lanes.set(laneId, []);
    }
    const lane = this.lanes.get(laneId);
    const prevHash = lane.length > 0 ? lane[lane.length - 1].hash : 'GENESIS';

    const block = {
      laneId,
      viewNumber,
      txPayload,
      prevHash,
      proposer: this.nodeId,
      timestamp: Date.now(),
      hash: ''
    };
    block.hash = sha256(block);
    lane.push(block);
    return block;
  }

  certifyInterleavedEpoch(barrierEpoch, laneBlockHashes, signatures) {
    // Check that we have valid signatures from quorum
    const validSigs = new Set();
    const payloadToSign = sha256({ barrierEpoch, laneBlockHashes });

    for (const sig of signatures) {
      const expected = sha256(`${sig.nodeId}:${payloadToSign}`);
      if (sig.signature === expected) {
        validSigs.add(sig.nodeId);
      }
    }

    if (validSigs.size < this.quorumThreshold) {
      return { committed: false, validSignatures: validSigs.size, required: this.quorumThreshold };
    }

    // Deterministic round-robin / priority interleaving across active lanes
    const laneKeys = Array.from(this.lanes.keys()).sort();
    let maxDepth = 0;
    for (const lk of laneKeys) {
      maxDepth = Math.max(maxDepth, this.lanes.get(lk).length);
    }

    const epochCommitSequence = [];
    for (let depth = 0; depth < maxDepth; depth++) {
      for (const lk of laneKeys) {
        const blk = this.lanes.get(lk)[depth];
        if (blk && laneBlockHashes.includes(blk.hash)) {
          epochCommitSequence.push(blk);
        }
      }
    }

    this.interleavedCommitted.push({
      barrierEpoch,
      blocks: epochCommitSequence,
      quorumCert: {
        hash: payloadToSign,
        signers: Array.from(validSigs)
      }
    });

    return { committed: true, totalCommitted: epochCommitSequence.length, blocks: epochCommitSequence };
  }
}

module.exports = { BFTViewInterleavingEngine };
