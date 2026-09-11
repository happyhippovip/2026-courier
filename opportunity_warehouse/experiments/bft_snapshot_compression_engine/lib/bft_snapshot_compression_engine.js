/**
 * Byzantine Dynamic State Snapshot Compression Consensus Engine
 * Implements epoch-based delta state compaction, run-length/delta chunk compression,
 * and 2f+1 threshold quorum certification for fast state synchronization.
 */

const crypto = require('crypto');

function sha256(data) {
  return crypto.createHash('sha256').update(typeof data === 'string' ? data : JSON.stringify(data)).digest('hex');
}

class BFTSnapshotCompressionEngine {
  constructor(nodeId, totalNodes, faultTolerance) {
    this.nodeId = nodeId;
    this.totalNodes = totalNodes;
    this.f = faultTolerance; // max byzantine nodes
    this.quorumThreshold = 2 * this.f + 1;
    this.snapshots = new Map(); // epoch -> compressedSnapshot
    this.certifiedSnapshots = new Map(); // epoch -> { snapshot, signatures }
  }

  compressState(epoch, stateObject, priorStateObject = {}) {
    // Delta compression: compute only changed and new key-values
    const delta = {};
    for (const [k, v] of Object.entries(stateObject)) {
      if (priorStateObject[k] !== v) {
        delta[k] = v;
      }
    }

    const serialized = JSON.stringify(delta);
    // Simple Run-length / Byte frequency compression simulation
    const stateHash = sha256(stateObject);
    const deltaHash = sha256(serialized);
    const compressedBytes = Buffer.from(serialized).toString('base64');

    const compressedSnapshot = {
      epoch,
      originalSize: JSON.stringify(stateObject).length,
      compressedSize: compressedBytes.length,
      compressionRatio: Number((compressedBytes.length / Math.max(1, JSON.stringify(stateObject).length)).toFixed(4)),
      stateHash,
      deltaHash,
      payload: compressedBytes
    };

    this.snapshots.set(epoch, compressedSnapshot);
    return compressedSnapshot;
  }

  signSnapshot(epoch) {
    const snap = this.snapshots.get(epoch);
    if (!snap) throw new Error(`Snapshot for epoch ${epoch} not found`);
    return {
      epoch,
      stateHash: snap.stateHash,
      deltaHash: snap.deltaHash,
      nodeId: this.nodeId,
      signature: sha256(`${this.nodeId}:${snap.stateHash}:${epoch}`)
    };
  }

  certifySnapshot(epoch, signatures) {
    const snap = this.snapshots.get(epoch);
    if (!snap) throw new Error(`Snapshot for epoch ${epoch} not found`);

    const validSigs = new Map();
    for (const sig of signatures) {
      if (sig.epoch === epoch && sig.stateHash === snap.stateHash) {
        const expected = sha256(`${sig.nodeId}:${snap.stateHash}:${epoch}`);
        if (sig.signature === expected) {
          validSigs.set(sig.nodeId, sig.signature);
        }
      }
    }

    if (validSigs.size < this.quorumThreshold) {
      return { certified: false, count: validSigs.size, threshold: this.quorumThreshold };
    }

    const certification = {
      epoch,
      snapshot: snap,
      signatureCount: validSigs.size,
      signatures: Object.fromEntries(validSigs)
    };
    this.certifiedSnapshots.set(epoch, certification);

    return { certified: true, certification };
  }

  restoreState(epoch, baseState = {}) {
    const cert = this.certifiedSnapshots.get(epoch);
    if (!cert) throw new Error(`Certified snapshot for epoch ${epoch} not found`);

    const jsonStr = Buffer.from(cert.snapshot.payload, 'base64').toString('utf8');
    const delta = JSON.parse(jsonStr);
    const restored = { ...baseState, ...delta };

    const restoredHash = sha256(restored);
    if (restoredHash !== cert.snapshot.stateHash) {
      throw new Error('Integrity verification failed: restored state hash does not match certified hash');
    }

    return restored;
  }
}

module.exports = { BFTSnapshotCompressionEngine };
