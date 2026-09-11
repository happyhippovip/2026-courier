/**
 * BFT Shard Committee Re-Sampling Consensus Engine
 * Implements deterministic epoch-driven VRF validator committee re-sampling across dynamic shards.
 */

const crypto = require('crypto');

class BftShardCommitteeResamplingEngine {
  constructor(options = {}) {
    this.committeeSize = options.committeeSize || 4;
    this.activeValidators = options.validators || ['val-A', 'val-B', 'val-C', 'val-D', 'val-E', 'val-F', 'val-G', 'val-H'];
    this.epochCommittees = new Map();
  }

  sampleCommitteeForEpoch(epoch, randomnessBeaconSeed) {
    if (this.epochCommittees.has(epoch)) {
      return this.epochCommittees.get(epoch);
    }

    // Deterministic pseudo-random permutation derived from VRF beacon seed
    const scored = this.activeValidators.map(v => {
      const hash = crypto.createHash('sha256').update(`${v}:${epoch}:${randomnessBeaconSeed}`).digest('hex');
      return { validatorId: v, score: hash };
    });

    scored.sort((a, b) => a.score.localeCompare(b.score));
    const selected = scored.slice(0, this.committeeSize).map(s => s.validatorId);

    const record = {
      epoch,
      beaconSeed: randomnessBeaconSeed,
      committee: selected,
      sampledAt: new Date().toISOString()
    };

    this.epochCommittees.set(epoch, record);
    return record;
  }

  isValidatorInCommittee(epoch, validatorId) {
    const record = this.epochCommittees.get(epoch);
    if (!record) return false;
    return record.committee.includes(validatorId);
  }
}

module.exports = { BftShardCommitteeResamplingEngine };
