/**
 * DAG-Rider Asynchronous Consensus Engine
 * Implements the asynchronous Byzantine consensus protocol (Keidar et al.).
 * Operates in Waves of 4 rounds:
 * - Round 4w + 1: Propose
 * - Round 4w + 2: Vote
 * - Round 4w + 3: Certify
 * - Round 4w + 4: Wave Leader Commit & Causal Linearization
 * Optimal resilience (n >= 3f + 1), completely asynchronous (no timeouts, no synchrony assumptions).
 */

const crypto = require('crypto');

function sha256(data) {
  return crypto.createHash('sha256').update(typeof data === 'string' ? data : JSON.stringify(data)).digest('hex');
}

class DAGVertex {
  constructor(author, round, previousVertexIds, payload) {
    this.author = author;
    this.round = round;
    this.previousVertexIds = previousVertexIds; // Causal parents in the DAG
    this.payload = payload;
    this.id = sha256({
      author,
      round,
      parents: previousVertexIds.sort(),
      payload
    });
    this.linearized = false;
  }
}

class DAGRiderConsensusEngine {
  constructor(validators, faultTolerance = 1) {
    this.validators = validators; // ['v0', 'v1', 'v2', 'v3']
    this.n = validators.length;
    this.f = faultTolerance;
    this.quorum = 2 * this.f + 1; // 3 for n=4, f=1

    this.vertices = new Map(); // vertexId -> DAGVertex
    this.roundVertices = new Map(); // round -> vertexId[]

    this.committedLeaders = [];
    this.linearizedTransactions = [];
  }

  addVertex(author, round, previousVertexIds, payload) {
    if (round > 1 && previousVertexIds.length < this.quorum) {
      throw new Error('Vertex in round ' + round + ' must reference at least 2f+1 parents');
    }

    const vertex = new DAGVertex(author, round, previousVertexIds, payload);
    this.vertices.set(vertex.id, vertex);

    if (!this.roundVertices.has(round)) {
      this.roundVertices.set(round, []);
    }
    this.roundVertices.get(round).push(vertex.id);

    return vertex;
  }

  /**
   * Evaluates Wave w (rounds 4w+1 .. 4w+4).
   * Determines if the Wave Leader in round 4w+1 is committed by round 4w+4.
   */
  evaluateWave(waveIndex) {
    const leaderRound = 4 * waveIndex + 1;
    const commitRound = 4 * waveIndex + 4;

    const leaderRoundVertices = this.roundVertices.get(leaderRound) || [];
    if (leaderRoundVertices.length === 0) return null;

    // Deterministic leader election for wave: author = validators[waveIndex % n]
    const designatedAuthor = this.validators[waveIndex % this.n];
    const waveLeaderId = leaderRoundVertices.find(id => this.vertices.get(id).author === designatedAuthor);

    if (!waveLeaderId) return null;
    const leaderVertex = this.vertices.get(waveLeaderId);

    // Commit condition: Leader must be causally reachable by at least 2f+1 vertices in commitRound (4w+4)
    const commitRoundVertices = this.roundVertices.get(commitRound) || [];
    let supportingCount = 0;

    for (const vId of commitRoundVertices) {
      if (this._isCausallyReachable(vId, waveLeaderId)) {
        supportingCount++;
      }
    }

    if (supportingCount >= this.quorum) {
      this.committedLeaders.push(leaderVertex);
      this._linearizeCausalPast(leaderVertex);
      return {
        wave: waveIndex,
        leaderId: waveLeaderId,
        leaderAuthor: designatedAuthor,
        supportingQuorum: supportingCount,
        committed: true
      };
    }

    return {
      wave: waveIndex,
      leaderId: waveLeaderId,
      supportingQuorum: supportingCount,
      committed: false
    };
  }

  _isCausallyReachable(sourceId, targetId, visited = new Set()) {
    if (sourceId === targetId) return true;
    if (visited.has(sourceId)) return false;
    visited.add(sourceId);

    const source = this.vertices.get(sourceId);
    if (!source || source.round <= this.vertices.get(targetId).round) return false;

    for (const parentId of source.previousVertexIds) {
      if (this._isCausallyReachable(parentId, targetId, visited)) {
        return true;
      }
    }
    return false;
  }

  _linearizeCausalPast(vertex) {
    // DFS traversal over causal past to topological sort unlinearized vertices
    for (const parentId of vertex.previousVertexIds) {
      const parent = this.vertices.get(parentId);
      if (parent && !parent.linearized) {
        this._linearizeCausalPast(parent);
      }
    }

    if (!vertex.linearized) {
      vertex.linearized = true;
      if (vertex.payload && vertex.payload.tx) {
        this.linearizedTransactions.push(vertex.payload.tx);
      }
    }
  }

  getLinearizedTransactions() {
    return this.linearizedTransactions;
  }
}

module.exports = { DAGRiderConsensusEngine, DAGVertex };
