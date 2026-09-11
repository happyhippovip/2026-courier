/**
 * Byzantine Dynamic Epoch State Re-anchoring Consensus Engine
 * Establishes cryptographic anchor points (Merkle root + 2f+1 signatures)
 * allowing nodes to prune past blocks safely and fast-forward state synchronization.
 */

const crypto = require('crypto');

function sha256(data) {
  return crypto.createHash('sha256').update(typeof data === 'string' ? data : JSON.stringify(data)).digest('hex');
}

class BFTReanchoringEngine {
  constructor(nodeId, totalNodes, faultTolerance) {
    this.nodeId = nodeId;
    this.totalNodes = totalNodes;
    this.f = faultTolerance;
    this.quorumThreshold = 2 * this.f + 1;
    this.anchors = new Map(); // epoch -> CertifiedAnchor
    this.prunedBeforeEpoch = 0;
  }

  proposeAnchor(epoch, stateRoot, validatorSetHash) {
    const anchorData = {
      epoch,
      stateRoot,
      validatorSetHash,
      timestamp: Date.now()
    };
    const anchorHash = sha256(anchorData);
    return {
      ...anchorData,
      anchorHash,
      proposer: this.nodeId
    };
  }

  signAnchor(anchor) {
    return {
      epoch: anchor.epoch,
      anchorHash: anchor.anchorHash,
      nodeId: this.nodeId,
      signature: sha256(`${this.nodeId}:${anchor.anchorHash}:${anchor.epoch}`)
    };
  }

  certifyAnchor(anchor, signatures) {
    const validSignatures = new Map();

    for (const sig of signatures) {
      if (sig.epoch === anchor.epoch && sig.anchorHash === anchor.anchorHash) {
        const expected = sha256(`${sig.nodeId}:${anchor.anchorHash}:${anchor.epoch}`);
        if (sig.signature === expected) {
          validSignatures.set(sig.nodeId, sig.signature);
        }
      }
    }

    if (validSignatures.size < this.quorumThreshold) {
      return { certified: false, validSignatures: validSignatures.size, required: this.quorumThreshold };
    }

    const certifiedAnchor = {
      anchor,
      quorumCert: {
        signatures: Object.fromEntries(validSignatures),
        count: validSignatures.size
      },
      certifiedAt: Date.now()
    };

    this.anchors.set(anchor.epoch, certifiedAnchor);
    return { certified: true, certifiedAnchor };
  }

  pruneHistory(upToEpoch) {
    if (!this.anchors.has(upToEpoch)) {
      throw new Error(`Cannot prune history: Epoch ${upToEpoch} has no certified anchor`);
    }
    this.prunedBeforeEpoch = upToEpoch;
    return { prunedUpTo: upToEpoch, activeAnchorEpoch: upToEpoch };
  }

  verifyBootstrappedNode(epoch, stateRoot) {
    const cert = this.anchors.get(epoch);
    if (!cert) return false;
    return cert.anchor.stateRoot === stateRoot && cert.quorumCert.count >= this.quorumThreshold;
  }
}

module.exports = { BFTReanchoringEngine };
