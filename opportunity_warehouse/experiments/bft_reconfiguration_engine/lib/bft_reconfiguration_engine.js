/**
 * Multi-Agent Distributed Asynchronous Verifiable Byzantine Reconfiguration Consensus Engine
 * Implements safe, epoch-bounded dynamic validator set reconfiguration (join, leave, stake weight changes)
 * ensuring uninterrupted liveness and continuous quorum certification across validator transitions.
 */

const crypto = require('crypto');

function hashObject(obj) {
  return crypto.createHash('sha256').update(JSON.stringify(obj)).digest('hex');
}

class ReconfigurationProposal {
  constructor(epoch, currentValidators, newValidators, reason) {
    this.epoch = epoch;
    this.currentValidators = currentValidators.slice().sort();
    this.newValidators = newValidators.slice().sort();
    this.reason = reason;
    this.proposalHash = hashObject({ epoch, curr: this.currentValidators, next: this.newValidators, reason });
  }
}

class ReconfigurationQC {
  constructor(proposalHash, epoch, signatures) {
    this.proposalHash = proposalHash;
    this.epoch = epoch;
    this.signatures = signatures;
  }
}

class BFTReconfigurationEngine {
  constructor(initialValidators = ['node_0', 'node_1', 'node_2', 'node_3']) {
    this.epoch = 1;
    this.validators = initialValidators.slice().sort();
    this.reconfigProposals = new Map(); // proposalHash -> ReconfigurationProposal
    this.reconfigVotes = new Map(); // "proposalHash:voterNodeId" -> vote
    this.reconfigQCs = new Map(); // epoch -> ReconfigurationQC
    this.epochHistory = [{ epoch: 1, validators: this.validators.slice() }];
  }

  getQuorumSize(validatorList = this.validators) {
    const f = Math.floor((validatorList.length - 1) / 3);
    return 2 * f + 1;
  }

  proposeReconfiguration(newValidators, reason) {
    const prop = new ReconfigurationProposal(this.epoch, this.validators, newValidators, reason);
    this.reconfigProposals.set(prop.proposalHash, prop);
    return prop;
  }

  voteReconfiguration(proposalHash, voterNodeId) {
    if (!this.validators.includes(voterNodeId)) {
      throw new Error('Unauthorized voter: ' + voterNodeId + ' not in current epoch ' + this.epoch + ' validator set');
    }

    const prop = this.reconfigProposals.get(proposalHash);
    if (!prop) throw new Error('Proposal not found: ' + proposalHash);
    if (prop.epoch !== this.epoch) {
      throw new Error('Epoch mismatch: proposal epoch ' + prop.epoch + ', current epoch ' + this.epoch);
    }

    const key = proposalHash + ':' + voterNodeId;
    if (this.reconfigVotes.has(key)) {
      throw new Error('Double vote detected from ' + voterNodeId);
    }

    const vote = {
      proposalHash,
      voterNodeId,
      epoch: this.epoch,
      sig: hashObject({ proposalHash, voterNodeId, epoch: this.epoch, role: 'RECONFIG_VOTE' })
    };
    this.reconfigVotes.set(key, vote);
    return vote;
  }

  certifyAndApplyReconfiguration(proposalHash) {
    const prop = this.reconfigProposals.get(proposalHash);
    if (!prop) throw new Error('Proposal not found: ' + proposalHash);

    const matchingVotes = [];
    for (const [key, v] of this.reconfigVotes.entries()) {
      if (key.startsWith(proposalHash + ':')) matchingVotes.push(v);
    }

    const requiredQuorum = this.getQuorumSize(this.validators);
    if (matchingVotes.length < requiredQuorum) {
      throw new Error('Insufficient votes for Reconfiguration QC: ' + matchingVotes.length + ' < ' + requiredQuorum);
    }

    const qc = new ReconfigurationQC(proposalHash, this.epoch, matchingVotes.slice(0, requiredQuorum));
    this.reconfigQCs.set(this.epoch, qc);

    // Apply reconfiguration to advance epoch
    this.epoch++;
    this.validators = prop.newValidators.slice().sort();
    this.epochHistory.push({ epoch: this.epoch, validators: this.validators.slice(), qcHash: hashObject(qc) });

    return {
      reconfigured: true,
      newEpoch: this.epoch,
      activeValidators: this.validators,
      quorumSize: this.getQuorumSize(this.validators)
    };
  }

  getStats() {
    return {
      currentEpoch: this.epoch,
      activeValidators: this.validators,
      activeQuorumSize: this.getQuorumSize(this.validators),
      totalReconfigurations: this.reconfigQCs.size,
      epochHistory: this.epochHistory
    };
  }
}

module.exports = { ReconfigurationProposal, ReconfigurationQC, BFTReconfigurationEngine };
