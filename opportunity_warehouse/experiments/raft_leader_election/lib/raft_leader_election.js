/**
 * Multi-Agent Raft Consensus Leader Election Engine
 * Implements deterministic Raft consensus state machine (Follower, Candidate, Leader)
 * with term tracking, vote request arbitration, and majority quorum validation.
 */

class RaftNode {
  constructor(nodeId, cluster) {
    this.nodeId = nodeId;
    this.cluster = cluster; // Map of nodeId -> RaftNode
    this.currentTerm = 0;
    this.votedFor = null;
    this.state = 'FOLLOWER'; // 'FOLLOWER' | 'CANDIDATE' | 'LEADER'
    this.log = [];
    this.votesReceived = 0;
  }

  // Handle timeout triggering a candidate election
  startElection() {
    this.state = 'CANDIDATE';
    this.currentTerm++;
    this.votedFor = this.nodeId;
    this.votesReceived = 1; // Vote for self

    const peers = Array.from(this.cluster.keys()).filter(id => id !== this.nodeId);
    const majority = Math.floor(this.cluster.size / 2) + 1;

    if (this.votesReceived >= majority) {
      this.state = 'LEADER';
      return;
    }

    for (const peerId of peers) {
      const peer = this.cluster.get(peerId);
      const voteGranted = peer.handleRequestVote({
        term: this.currentTerm,
        candidateId: this.nodeId,
        lastLogIndex: this.log.length - 1,
        lastLogTerm: this.log.length > 0 ? this.log[this.log.length - 1].term : 0
      });

      if (voteGranted) {
        this.votesReceived++;
        if (this.votesReceived >= majority && this.state === 'CANDIDATE') {
          this.state = 'LEADER';
        }
      }
    }
  }

  // Handle RequestVote RPC
  handleRequestVote(req) {
    if (req.term > this.currentTerm) {
      this.currentTerm = req.term;
      this.state = 'FOLLOWER';
      this.votedFor = null;
    }

    if (req.term === this.currentTerm && (this.votedFor === null || this.votedFor === req.candidateId)) {
      this.votedFor = req.candidateId;
      return true;
    }

    return false;
  }

  // Send AppendEntries heartbeat from leader
  sendHeartbeat() {
    if (this.state !== 'LEADER') return;

    const peers = Array.from(this.cluster.keys()).filter(id => id !== this.nodeId);
    for (const peerId of peers) {
      const peer = this.cluster.get(peerId);
      peer.handleAppendEntries({
        term: this.currentTerm,
        leaderId: this.nodeId
      });
    }
  }

  // Handle AppendEntries RPC
  handleAppendEntries(req) {
    if (req.term >= this.currentTerm) {
      this.currentTerm = req.term;
      this.state = 'FOLLOWER';
      return true;
    }
    return false;
  }
}

module.exports = { RaftNode };
