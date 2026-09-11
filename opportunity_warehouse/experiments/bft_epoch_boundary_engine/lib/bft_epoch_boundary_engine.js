/**
 * Multi-Agent Distributed Asynchronous Verifiable Byzantine Epoch Boundary Consensus Engine
 * Manages seamless transitions between consensus epochs, establishing cryptographic epoch certificates
 * and checkpoint state hashes without stalling in-flight micro-block consensus pipelines.
 */

const crypto = require('crypto');

function hashObject(obj) {
  return crypto.createHash('sha256').update(JSON.stringify(obj)).digest('hex');
}

class EpochBoundaryCertificate {
  constructor(epoch, stateRoot, validatorSet, signatures) {
    this.epoch = epoch;
    this.stateRoot = stateRoot;
    this.validatorSet = validatorSet.slice().sort();
    this.signatures = signatures;
    this.certHash = hashObject({ epoch, stateRoot, validatorSet: this.validatorSet, sigCount: signatures.length });
    this.finalizedAt = Date.now();
  }
}

class BFTEpochBoundaryEngine {
  constructor(initialEpoch = 1, initialValidators = ['node_0', 'node_1', 'node_2', 'node_3']) {
    this.currentEpoch = initialEpoch;
    this.validators = initialValidators.slice().sort();
    this.f = Math.floor((this.validators.length - 1) / 3); // f=1
    this.quorumSize = 2 * this.f + 1; // 3

    this.epochVotes = new Map(); // "epoch:nodeId" -> vote
    this.epochCertificates = new Map(); // epoch -> EpochBoundaryCertificate
    this.epochHistory = [];
  }

  castEpochVote(epoch, stateRoot, voterNodeId) {
    if (epoch !== this.currentEpoch) {
      throw new Error('Epoch mismatch: current epoch ' + this.currentEpoch + ', vote for ' + epoch);
    }
    if (!this.validators.includes(voterNodeId)) {
      throw new Error('Unauthorized voter: ' + voterNodeId);
    }

    const key = epoch + ':' + voterNodeId;
    if (this.epochVotes.has(key)) {
      throw new Error('Double epoch vote from: ' + voterNodeId);
    }

    const vote = {
      epoch,
      stateRoot,
      voterNodeId,
      sig: hashObject({ epoch, stateRoot, voterNodeId, role: 'EPOCH_BOUNDARY_VOTE' })
    };
    this.epochVotes.set(key, vote);
    return vote;
  }

  finalizeEpochTransition(epoch, nextValidators = null) {
    const matchingVotes = [];
    let agreedStateRoot = null;

    for (const [key, v] of this.epochVotes.entries()) {
      if (key.startsWith(epoch + ':')) {
        if (!agreedStateRoot) agreedStateRoot = v.stateRoot;
        if (v.stateRoot === agreedStateRoot) {
          matchingVotes.push(v);
        }
      }
    }

    if (matchingVotes.length < this.quorumSize) {
      throw new Error('Insufficient votes for Epoch Boundary Certificate: ' + matchingVotes.length + ' < ' + this.quorumSize);
    }

    const cert = new EpochBoundaryCertificate(
      epoch,
      agreedStateRoot,
      this.validators,
      matchingVotes.slice(0, this.quorumSize)
    );

    this.epochCertificates.set(epoch, cert);
    this.epochHistory.push(cert);

    // Advance epoch
    this.currentEpoch = epoch + 1;
    if (nextValidators && Array.isArray(nextValidators)) {
      this.validators = nextValidators.slice().sort();
      this.f = Math.floor((this.validators.length - 1) / 3);
      this.quorumSize = 2 * this.f + 1;
    }

    return {
      transitioned: true,
      certifiedEpoch: epoch,
      newEpoch: this.currentEpoch,
      certHash: cert.certHash,
      activeValidators: this.validators
    };
  }

  getStats() {
    return {
      currentEpoch: this.currentEpoch,
      validatorsCount: this.validators.length,
      quorumSize: this.quorumSize,
      certifiedEpochsCount: this.epochCertificates.size
    };
  }
}

module.exports = { EpochBoundaryCertificate, BFTEpochBoundaryEngine };
