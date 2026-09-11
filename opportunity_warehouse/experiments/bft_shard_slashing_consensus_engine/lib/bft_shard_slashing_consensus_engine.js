/**
 * BFT Shard Slashing Consensus Engine
 * Detects Byzantine double-voting / equivocation across shard epochs and executes deterministic stake slashing.
 */

const crypto = require('crypto');

class BftShardSlashingConsensusEngine {
  constructor() {
    this.slashedValidators = new Map(); // valId -> slashRecord
    this.observedVotes = new Map(); // `valId:epoch` -> array of voteRecords
  }

  recordVote(validatorId, epoch, blockHash, signature) {
    const key = `${validatorId}:${epoch}`;
    if (!this.observedVotes.has(key)) {
      this.observedVotes.set(key, []);
    }
    const votes = this.observedVotes.get(key);

    // Check for equivocation (different blockHash in same epoch)
    const equivocation = votes.find(v => v.blockHash !== blockHash);
    if (equivocation) {
      // Byzantine double-vote detected! Execute immediate slashing
      const slashRecord = {
        validatorId,
        epoch,
        offense: 'EQUIVOCATION_DOUBLE_VOTE',
        evidence: [
          { blockHash: equivocation.blockHash, signature: equivocation.signature },
          { blockHash, signature }
        ],
        slashedStakePercent: 100,
        slashedAt: new Date().toISOString(),
        slashingProofHash: crypto.createHash('sha256').update(`SLASH:${validatorId}:${epoch}`).digest('hex')
      };
      this.slashedValidators.set(validatorId, slashRecord);
      return { accepted: false, slashed: true, slashRecord };
    }

    votes.push({ blockHash, signature, timestamp: new Date().toISOString() });
    return { accepted: true, slashed: false };
  }

  isSlashed(validatorId) {
    return this.slashedValidators.has(validatorId);
  }

  getSlashingRecord(validatorId) {
    return this.slashedValidators.get(validatorId) || null;
  }
}

module.exports = { BftShardSlashingConsensusEngine };
