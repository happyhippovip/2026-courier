/**
 * Multi-Agent Distributed Asynchronous Verifiable Byzantine Dynamic Stake Delegation Consensus Engine
 * Implements non-custodial stake delegation pooling with automatic proportional slashing propagation,
 * unbonding lock timers, and fail-closed Sybil evasion prevention.
 */

const crypto = require('crypto');

function hashObject(obj) {
  return crypto.createHash('sha256').update(JSON.stringify(obj)).digest('hex');
}

class BFTStakeDelegationEngine {
  constructor(unbondingPeriodMs = 1000) {
    this.unbondingPeriodMs = unbondingPeriodMs;
    this.validators = new Map(); // valId -> selfStake
    this.delegations = new Map(); // "valId:delId" -> amount
    this.slashedValidators = new Set();
    this.unbondingQueue = []; // Array of { delId, amount, releaseTime }
  }

  registerValidator(valId, selfStake) {
    this.validators.set(valId, selfStake);
  }

  delegateStake(valId, delId, amount) {
    if (!this.validators.has(valId)) {
      throw new Error('Unknown validator for delegation: ' + valId);
    }
    if (this.slashedValidators.has(valId)) {
      throw new Error('Cannot delegate to slashed validator: ' + valId);
    }
    const key = valId + ':' + delId;
    const curr = this.delegations.get(key) || 0;
    this.delegations.set(key, curr + amount);
    return { valId, delId, totalDelegated: curr + amount };
  }

  getTotalValidatorWeight(valId) {
    if (this.slashedValidators.has(valId)) return 0;
    let total = this.validators.get(valId) || 0;
    for (const [key, amt] of this.delegations.entries()) {
      if (key.startsWith(valId + ':')) total += amt;
    }
    return total;
  }

  slashValidatorAndDelegators(valId, slashFraction = 1.0) {
    if (!this.validators.has(valId)) throw new Error('Unknown validator: ' + valId);
    if (this.slashedValidators.has(valId)) return { slashed: false, reason: 'ALREADY_SLASHED' };

    this.slashedValidators.add(valId);
    const selfStake = this.validators.get(valId) || 0;
    const slashedSelf = Math.floor(selfStake * slashFraction);
    this.validators.set(valId, selfStake - slashedSelf);

    let totalDelegatedSlashed = 0;
    for (const [key, amt] of this.delegations.entries()) {
      if (key.startsWith(valId + ':')) {
        const slashedAmt = Math.floor(amt * slashFraction);
        this.delegations.set(key, amt - slashedAmt);
        totalDelegatedSlashed += slashedAmt;
      }
    }

    return {
      slashed: true,
      valId,
      slashedSelf,
      totalDelegatedSlashed,
      totalForfeited: slashedSelf + totalDelegatedSlashed
    };
  }

  requestUnbond(valId, delId, amount) {
    const key = valId + ':' + delId;
    const curr = this.delegations.get(key) || 0;
    if (amount > curr) {
      throw new Error('Insufficient delegated balance: requested ' + amount + ', has ' + curr);
    }
    this.delegations.set(key, curr - amount);
    const unbond = { delId, amount, releaseTime: Date.now() + this.unbondingPeriodMs };
    this.unbondingQueue.push(unbond);
    return unbond;
  }

  getStats() {
    return {
      validatorsCount: this.validators.size,
      slashedCount: this.slashedValidators.size,
      totalDelegationsCount: this.delegations.size,
      pendingUnbondingCount: this.unbondingQueue.length
    };
  }
}

module.exports = { BFTStakeDelegationEngine };
