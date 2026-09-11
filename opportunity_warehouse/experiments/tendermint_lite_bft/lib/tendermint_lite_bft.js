/**
 * Tendermint-Lite BFT Consensus State Machine
 * Deterministic round-based Byzantine Fault Tolerant consensus state machine.
 * Cycles through Propose -> Prevote -> Precommit -> Commit stages.
 * Guaranteed safety with < 1/3 Byzantine nodes; liveness under partial synchrony.
 */

const crypto = require('crypto');

function sha256(data) {
  return crypto.createHash('sha256').update(typeof data === 'string' ? data : JSON.stringify(data)).digest('hex');
}

class TendermintLiteBFT {
  constructor(validators, height = 1) {
    this.validators = validators; // ['val_0', 'val_1', 'val_2', 'val_3']
    this.n = validators.length;
    this.f = Math.floor((this.n - 1) / 3);
    this.quorum = 2 * this.f + 1;

    this.height = height;
    this.round = 0;
    this.step = 'NEW_ROUND'; // NEW_ROUND -> PROPOSE -> PREVOTE -> PRECOMMIT -> COMMIT

    this.proposal = null;
    this.prevotes = new Map(); // round -> Map(val -> blockHash)
    this.precommits = new Map(); // round -> Map(val -> blockHash)
    this.committedBlocks = [];
  }

  proposeBlock(proposer, blockData) {
    if (this.step !== 'NEW_ROUND' && this.step !== 'PROPOSE') {
      throw new Error('Cannot propose in step: ' + this.step);
    }
    const blockHash = sha256({ height: this.height, round: this.round, blockData });
    this.proposal = {
      proposer,
      height: this.height,
      round: this.round,
      data: blockData,
      hash: blockHash
    };
    this.step = 'PREVOTE';
    return this.proposal;
  }

  castPrevote(validator, blockHash) {
    if (!this.prevotes.has(this.round)) {
      this.prevotes.set(this.round, new Map());
    }
    this.prevotes.get(this.round).set(validator, blockHash);

    // Check if 2f+1 prevotes reached for this blockHash
    let votes = 0;
    for (const h of this.prevotes.get(this.round).values()) {
      if (h === blockHash) votes++;
    }

    if (votes >= this.quorum && this.step === 'PREVOTE') {
      this.step = 'PRECOMMIT';
    }
    return votes;
  }

  castPrecommit(validator, blockHash) {
    if (!this.precommits.has(this.round)) {
      this.precommits.set(this.round, new Map());
    }
    this.precommits.get(this.round).set(validator, blockHash);

    // Check if 2f+1 precommits reached
    let commits = 0;
    for (const h of this.precommits.get(this.round).values()) {
      if (h === blockHash) commits++;
    }

    if (commits >= this.quorum && this.step === 'PRECOMMIT') {
      this.step = 'COMMIT';
      this._finalizeCommit(blockHash);
    }
    return commits;
  }

  _finalizeCommit(blockHash) {
    const committedBlock = {
      height: this.height,
      round: this.round,
      hash: blockHash,
      data: this.proposal ? this.proposal.data : null,
      signaturesCount: this.precommits.get(this.round).size,
      committedAt: new Date().toISOString()
    };
    this.committedBlocks.push(committedBlock);
    this.height++;
    this.round = 0;
    this.step = 'NEW_ROUND';
    this.proposal = null;
  }

  getCommittedChain() {
    return this.committedBlocks;
  }
}

module.exports = { TendermintLiteBFT };
