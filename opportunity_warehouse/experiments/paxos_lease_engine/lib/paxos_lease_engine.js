/**
 * Multi-Agent Distributed Paxos Consensus & Lease Management Engine
 * Implements Classic Single-Decree Paxos with Prepare/Promise, Accept/Accepted,
 * and time-bounded exclusive lease acquisition for critical resources.
 */

class PaxosAcceptor {
  constructor(acceptorId) {
    this.acceptorId = acceptorId;
    this.promisedRound = -1;
    this.acceptedRound = -1;
    this.acceptedValue = null;
  }

  // Phase 1b: Promise
  handlePrepare(round) {
    if (round > this.promisedRound) {
      this.promisedRound = round;
      return {
        status: 'PROMISE',
        promisedRound: round,
        acceptedRound: this.acceptedRound,
        acceptedValue: this.acceptedValue
      };
    }
    return { status: 'REJECT', currentPromised: this.promisedRound };
  }

  // Phase 2b: Accepted
  handleAccept(round, value) {
    if (round >= this.promisedRound) {
      this.promisedRound = round;
      this.acceptedRound = round;
      this.acceptedValue = value;
      return { status: 'ACCEPTED', round, value };
    }
    return { status: 'REJECT', currentPromised: this.promisedRound };
  }
}

class PaxosProposer {
  constructor(proposerId, acceptors) {
    this.proposerId = proposerId;
    this.acceptors = acceptors; // Array of PaxosAcceptor
    this.majority = Math.floor(acceptors.length / 2) + 1;
  }

  proposeLease(round, leaseHolderId, durationMs) {
    const value = { leaseHolderId, durationMs, grantedAt: Date.now() };

    // Phase 1a: Broadcast Prepare
    let promises = 0;
    let highestAcceptedRound = -1;
    let proposedValue = value;

    for (const acc of this.acceptors) {
      const resp = acc.handlePrepare(round);
      if (resp.status === 'PROMISE') {
        promises++;
        if (resp.acceptedRound > highestAcceptedRound && resp.acceptedValue !== null) {
          highestAcceptedRound = resp.acceptedRound;
          proposedValue = resp.acceptedValue;
        }
      }
    }

    if (promises < this.majority) {
      return { status: 'PREPARE_FAILED', promises, needed: this.majority };
    }

    // Phase 2a: Broadcast Accept
    let accepts = 0;
    for (const acc of this.acceptors) {
      const resp = acc.handleAccept(round, proposedValue);
      if (resp.status === 'ACCEPTED') {
        accepts++;
      }
    }

    if (accepts >= this.majority) {
      return { status: 'LEASE_GRANTED', value: proposedValue, accepts, round };
    }

    return { status: 'ACCEPT_FAILED', accepts, needed: this.majority };
  }
}

module.exports = { PaxosAcceptor, PaxosProposer };
