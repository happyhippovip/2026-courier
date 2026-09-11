/**
 * Bullshark Asynchronous DAG-BFT Consensus Engine
 * Implements high-throughput, low-latency DAG-based BFT consensus for multi-agent clusters.
 * Nodes propose vertices containing payloads and references to >= 2f + 1 vertices from round r-1.
 * Even rounds designate deterministic leader anchors; vertices in leader's causal history are totally ordered.
 */

const crypto = require('crypto');

function computeHash(data) {
  return crypto.createHash('sha256').update(typeof data === 'string' ? data : JSON.stringify(data)).digest('hex');
}

class DAGVertex {
  constructor(nodeId, round, payload, parentHashes) {
    this.nodeId = nodeId;
    this.round = round;
    this.payload = payload;
    this.parentHashes = parentHashes || []; // Hashes of round r-1 vertices
    this.timestamp = Date.now();
    this.hash = computeHash({
      nodeId: this.nodeId,
      round: this.round,
      payload: this.payload,
      parentHashes: this.parentHashes.slice().sort()
    });
  }
}

class BullsharkDAGBFT {
  constructor(nodeCount, faultTolerance) {
    this.n = nodeCount; // Total nodes
    this.f = faultTolerance || Math.floor((nodeCount - 1) / 3);
    this.quorum = 2 * this.f + 1;

    // DAG Storage: round -> Map(hash -> DAGVertex)
    this.dag = new Map();
    // Hash -> DAGVertex lookup
    this.vertexIndex = new Map();

    // Committed leaders and linear total order
    this.committedLeaders = [];
    this.orderedVertices = [];
    this.orderedHashes = new Set();
  }

  addVertex(nodeId, round, payload, parentHashes) {
    // Round 0 vertices do not require parents
    if (round > 0) {
      if (!parentHashes || parentHashes.length < this.quorum) {
        throw new Error(`Vertex round ${round} must have at least ${this.quorum} parent references, got ${parentHashes ? parentHashes.length : 0}`);
      }
      // Ensure all parents exist in round r-1
      for (const pHash of parentHashes) {
        const parent = this.vertexIndex.get(pHash);
        if (!parent || parent.round !== round - 1) {
          throw new Error(`Parent hash ${pHash} not found in round ${round - 1}`);
        }
      }
    }

    const vertex = new DAGVertex(nodeId, round, payload, parentHashes);
    if (!this.dag.has(round)) {
      this.dag.set(round, new Map());
    }

    this.dag.get(round).set(vertex.hash, vertex);
    this.vertexIndex.set(vertex.hash, vertex);

    return vertex;
  }

  getLeaderForRound(round) {
    // In Bullshark, odd rounds designate leaders (or every round in pipelined mode)
    // Deterministic round-robin leader selection among node IDs
    const leaderIndex = round % this.n;
    const roundVertices = this.dag.get(round);
    if (!roundVertices) return null;

    for (const v of roundVertices.values()) {
      if (parseInt(v.nodeId.replace(/\D/g, ''), 10) % this.n === leaderIndex || v.nodeId === `node_${leaderIndex}`) {
        return v;
      }
    }
    return null;
  }

  _isReachable(fromVertex, targetHash, visited = new Set()) {
    if (fromVertex.hash === targetHash) return true;
    if (fromVertex.round <= 0) return false;
    visited.add(fromVertex.hash);

    for (const pHash of fromVertex.parentHashes) {
      if (pHash === targetHash) return true;
      if (!visited.has(pHash)) {
        const parent = this.vertexIndex.get(pHash);
        if (parent && this._isReachable(parent, targetHash, visited)) {
          return true;
        }
      }
    }
    return false;
  }

  commitLeader(leaderRound) {
    const leader = this.getLeaderForRound(leaderRound);
    if (!leader) return false;

    // Check if a quorum of vertices in round (leaderRound + 1) reference/reach the leader
    const nextRound = this.dag.get(leaderRound + 1);
    if (!nextRound) return false;

    let supportingQuorum = 0;
    for (const voter of nextRound.values()) {
      if (this._isReachable(voter, leader.hash)) {
        supportingQuorum++;
      }
    }

    if (supportingQuorum >= this.quorum) {
      this.committedLeaders.push(leader);
      this._orderCausalPast(leader);
      return true;
    }
    return false;
  }

  _orderCausalPast(vertex) {
    // Topological sort of uncommitted causal history
    const history = [];
    const visited = new Set();

    const dfs = (v) => {
      if (!v || visited.has(v.hash) || this.orderedHashes.has(v.hash)) return;
      visited.add(v.hash);

      // Visit parents in deterministic order (sorted by hash)
      const sortedParents = v.parentHashes.slice().sort();
      for (const pHash of sortedParents) {
        const p = this.vertexIndex.get(pHash);
        if (p) dfs(p);
      }
      history.push(v);
    };

    dfs(vertex);

    for (const v of history) {
      if (!this.orderedHashes.has(v.hash)) {
        this.orderedHashes.add(v.hash);
        this.orderedVertices.push(v);
      }
    }
  }

  getTotalOrder() {
    return this.orderedVertices.map(v => ({
      hash: v.hash,
      round: v.round,
      nodeId: v.nodeId,
      payload: v.payload
    }));
  }
}

module.exports = { BullsharkDAGBFT, DAGVertex, computeHash };
