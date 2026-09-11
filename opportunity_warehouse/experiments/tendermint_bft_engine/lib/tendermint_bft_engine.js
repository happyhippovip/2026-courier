/**
 * Multi-Agent Distributed Tendermint-Style BFT Consensus Engine
 * 2-step voting (Prevote, Precommit) with 2/3+ quorum thresholds
 * and Polka locking mechanism to guarantee Byzantine safety.
 */

class BFTValidator {
  constructor(id, votingPower = 1) {
    this.id = id;
    this.votingPower = votingPower;
    this.lockedBlock = null;
    this.lockedRound = -1;
    this.state = 'INIT'; // 'INIT' | 'PREVOTED' | 'PRECOMMITTED' | 'COMMITTED'
  }

  prevote(round, block) {
    // If locked on another block in higher round, prevote locked
    if (this.lockedBlock && this.lockedRound > round) {
      return { id: this.id, round, voteType: 'PREVOTE', block: this.lockedBlock };
    }
    this.state = 'PREVOTED';
    return { id: this.id, round, voteType: 'PREVOTE', block };
  }

  precommit(round, block, hasPolka) {
    if (hasPolka) {
      this.lockedBlock = block;
      this.lockedRound = round;
      this.state = 'PRECOMMITTED';
      return { id: this.id, round, voteType: 'PRECOMMIT', block };
    }
    return { id: this.id, round, voteType: 'PRECOMMIT', block: null };
  }

  commit(block) {
    this.state = 'COMMITTED';
    return { status: 'BLOCK_COMMITTED', id: this.id, block };
  }
}

class TendermintBFTCoordinator {
  constructor(validators) {
    this.validators = validators;
    this.totalPower = validators.reduce((acc, v) => acc + v.votingPower, 0);
    this.twoThirdsThreshold = Math.floor((2 * this.totalPower) / 3) + 1;
  }

  executeConsensus(round, proposedBlock) {
    // Step 1: Prevote broadcast
    const prevotes = [];
    for (const v of this.validators) {
      prevotes.push(v.prevote(round, proposedBlock));
    }

    const prevotePower = prevotes
      .filter(p => p.block === proposedBlock)
      .reduce((acc, p) => acc + (this.validators.find(v => v.id === p.id).votingPower), 0);

    const hasPolka = prevotePower >= this.twoThirdsThreshold;

    // Step 2: Precommit broadcast
    const precommits = [];
    for (const v of this.validators) {
      precommits.push(v.precommit(round, proposedBlock, hasPolka));
    }

    const precommitPower = precommits
      .filter(p => p.block === proposedBlock)
      .reduce((acc, p) => acc + (this.validators.find(v => v.id === p.id).votingPower), 0);

    const isCommitted = precommitPower >= this.twoThirdsThreshold;

    if (isCommitted) {
      for (const v of this.validators) {
        v.commit(proposedBlock);
      }
      return {
        status: 'CONSENSUS_COMMITTED',
        round,
        block: proposedBlock,
        prevotePower,
        precommitPower,
        twoThirdsThreshold: this.twoThirdsThreshold
      };
    }

    return { status: 'CONSENSUS_FAILED', round, precommitPower, needed: this.twoThirdsThreshold };
  }
}

module.exports = { BFTValidator, TendermintBFTCoordinator };
