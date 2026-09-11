/**
 * BFT Shard Dynamic Slashing & Jail Consensus Engine
 * Detects double-signing/equivocation evidence, slashes validator stake, and enforces jail duration epochs.
 */

const crypto = require('crypto');

class BFTShardSlashingJailEngine {
  constructor(options = {}) {
    this.slashPenaltyFraction = options.slashPenaltyFraction || 0.2; // 20% slash
    this.defaultJailDurationEpochs = options.defaultJailDurationEpochs || 5;
    this.validators = new Map(); // validatorId -> { stake, jailedUntilEpoch, slashedStakeTotal }
    this.slashingIncidents = [];
    this.currentEpoch = 0;
  }

  registerValidator(validatorId, initialStake) {
    this.validators.set(validatorId, {
      stake: initialStake,
      jailedUntilEpoch: 0,
      slashedStakeTotal: 0
    });
  }

  advanceEpoch(newEpoch) {
    this.currentEpoch = newEpoch;
  }

  isEligible(validatorId) {
    const v = this.validators.get(validatorId);
    if (!v) return false;
    if (v.stake <= 0) return false;
    return this.currentEpoch >= v.jailedUntilEpoch;
  }

  processEquivocationEvidence(evidence) {
    // evidence: { validatorId, view, blockA, blockB, sigA, sigB }
    const { validatorId, view, blockA, blockB } = evidence;
    const v = this.validators.get(validatorId);
    if (!v) throw new Error('Unknown validator: ' + validatorId);

    if (blockA.hash === blockB.hash) {
      throw new Error('Evidence rejected: identical block hashes do not constitute equivocation');
    }

    const slashAmount = Math.round(v.stake * this.slashPenaltyFraction);
    v.stake -= slashAmount;
    v.slashedStakeTotal += slashAmount;
    v.jailedUntilEpoch = this.currentEpoch + this.defaultJailDurationEpochs;

    const incident = {
      incidentId: 'INC-' + (this.slashingIncidents.length + 1),
      validatorId: validatorId,
      view: view,
      slashedAmount: slashAmount,
      remainingStake: v.stake,
      jailedUntilEpoch: v.jailedUntilEpoch,
      timestamp: new Date().toISOString()
    };

    this.slashingIncidents.push(incident);
    return incident;
  }
}

module.exports = { BFTShardSlashingJailEngine };
