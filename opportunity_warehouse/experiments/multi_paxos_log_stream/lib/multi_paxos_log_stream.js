/**
 * Multi-Agent Distributed Multi-Paxos Consensus Log Stream Engine
 * Amortizes Phase 1 (Prepare/Promise) across multiple log instances,
 * enabling single round-trip consensus (Phase 2 Accept/Accepted) for streaming logs.
 */

class MultiPaxosAcceptor {
  constructor(id) {
    this.id = id;
    this.promisedBallot = -1;
    this.log = new Map(); // slotIndex -> { acceptedBallot, acceptedValue }
  }

  handlePrepare(ballot) {
    if (ballot > this.promisedBallot) {
      this.promisedBallot = ballot;
      const acceptedSlots = {};
      for (const [slot, entry] of this.log.entries()) {
        acceptedSlots[slot] = { ...entry };
      }
      return { status: 'PROMISE', ballot, acceptedSlots };
    }
    return { status: 'REJECT', currentBallot: this.promisedBallot };
  }

  handleAccept(ballot, slot, value) {
    if (ballot >= this.promisedBallot) {
      this.promisedBallot = ballot;
      this.log.set(slot, { acceptedBallot: ballot, value });
      return { status: 'ACCEPTED', ballot, slot, value };
    }
    return { status: 'REJECT', currentBallot: this.promisedBallot };
  }
}

class MultiPaxosLeader {
  constructor(leaderId, acceptors) {
    this.leaderId = leaderId;
    this.acceptors = acceptors; // Array of MultiPaxosAcceptor
    this.ballot = 0;
    this.isLeaderActive = false;
    this.nextSlot = 0;
    this.majority = Math.floor(acceptors.length / 2) + 1;
  }

  // Phase 1: Prepare whole log stream once
  acquireLeadership(ballot) {
    this.ballot = ballot;
    let promises = 0;

    for (const acc of this.acceptors) {
      const resp = acc.handlePrepare(ballot);
      if (resp.status === 'PROMISE') {
        promises++;
      }
    }

    if (promises >= this.majority) {
      this.isLeaderActive = true;
      return { status: 'LEADER_ESTABLISHED', ballot, promises };
    }

    return { status: 'ELECTION_FAILED', promises, needed: this.majority };
  }

  // Phase 2: Streaming append with 1 RTT per slot
  appendStreamEntry(value) {
    if (!this.isLeaderActive) {
      throw new Error('Cannot append: leadership not established in Phase 1');
    }

    const slot = this.nextSlot++;
    let accepts = 0;

    for (const acc of this.acceptors) {
      const resp = acc.handleAccept(this.ballot, slot, value);
      if (resp.status === 'ACCEPTED') {
        accepts++;
      }
    }

    if (accepts >= this.majority) {
      return { status: 'COMMITTED', slot, value, roundtrips: 1 };
    }

    return { status: 'COMMIT_FAILED', slot, accepts, needed: this.majority };
  }
}

module.exports = { MultiPaxosAcceptor, MultiPaxosLeader };
