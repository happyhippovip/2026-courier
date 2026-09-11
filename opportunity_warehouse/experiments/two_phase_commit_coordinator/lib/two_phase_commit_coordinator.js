/**
 * Multi-Agent Distributed Two-Phase Commit (2PC) Coordinator Engine
 * Coordinates atomic multi-agent state transactions across distributed context nodes
 * with strict Phase 1 (Prepare/Vote) and Phase 2 (Commit/Abort) semantics.
 */

class ParticipantNode {
  constructor(nodeId, shouldVoteCommit = true) {
    this.nodeId = nodeId;
    this.shouldVoteCommit = shouldVoteCommit;
    this.state = 'IDLE'; // 'IDLE' | 'PREPARED' | 'COMMITTED' | 'ABORTED'
    this.txLog = [];
  }

  prepare(txId, data) {
    if (this.shouldVoteCommit) {
      this.state = 'PREPARED';
      this.txLog.push({ txId, data, state: 'PREPARED' });
      return { nodeId: this.nodeId, vote: 'COMMIT' };
    } else {
      this.state = 'ABORTED';
      this.txLog.push({ txId, data, state: 'ABORTED' });
      return { nodeId: this.nodeId, vote: 'ABORT' };
    }
  }

  commit(txId) {
    this.state = 'COMMITTED';
    this.txLog.push({ txId, state: 'COMMITTED' });
    return { nodeId: this.nodeId, status: 'COMMITTED' };
  }

  abort(txId) {
    this.state = 'ABORTED';
    this.txLog.push({ txId, state: 'ABORTED' });
    return { nodeId: this.nodeId, status: 'ABORTED' };
  }
}

class TwoPhaseCommitCoordinator {
  constructor(participants) {
    this.participants = participants; // Array of ParticipantNode
    this.history = [];
  }

  executeTransaction(txId, data) {
    // Phase 1: Prepare
    const votes = [];
    for (const participant of this.participants) {
      const vote = participant.prepare(txId, data);
      votes.push(vote);
    }

    const allVoteCommit = votes.every(v => v.vote === 'COMMIT');

    // Phase 2: Commit or Abort
    if (allVoteCommit) {
      for (const participant of this.participants) {
        participant.commit(txId);
      }
      const record = { txId, status: 'COMMITTED', votes };
      this.history.push(record);
      return record;
    } else {
      for (const participant of this.participants) {
        participant.abort(txId);
      }
      const record = { txId, status: 'ABORTED', votes };
      this.history.push(record);
      return record;
    }
  }
}

module.exports = { TwoPhaseCommitCoordinator, ParticipantNode };
