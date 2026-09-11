/**
 * Bullshark Fast-Path Consensus Engine
 * Implements an optimistic 2-round fast-path commit rule over DAG mempools.
 * Under normal synchrony without faults, leaders with a fast quorum (3f + 1 / full consensus)
 * commit in 2 rounds rather than 3, slashing commit latency by 33%.
 */

const crypto = require('crypto');

function sha256(data) {
  return crypto.createHash('sha256').update(typeof data === 'string' ? data : JSON.stringify(data)).digest('hex');
}

class FastPathVertex {
  constructor(nodeId, round, payload, parents) {
    this.nodeId = nodeId;
    this.round = round;
    this.payload = payload;
    this.parents = parents || [];
    this.hash = sha256({ nodeId, round, payload, parents: this.parents.slice().sort() });
  }
}

class BullsharkFastPath {
  constructor(nodes, faultTolerance) {
    this.nodes = nodes; // ['node_0', 'node_1', 'node_2', 'node_3']
    this.n = nodes.length;
    this.f = faultTolerance || Math.floor((this.n - 1) / 3);
    this.slowQuorum = 2 * this.f + 1; // 3
    this.fastQuorum = this.n; // 4 (all honest in fast-path)

    this.dag = new Map(); // round -> Map(hash -> FastPathVertex)
    this.vertexIndex = new Map();
    this.committedLeaders = [];
    this.linearOrder = [];
    this.orderedHashes = new Set();
  }

  addVertex(nodeId, round, payload, parents) {
    if (round > 0) {
      if (!parents || parents.length < this.slowQuorum) {
        throw new Error(`Round ${round} requires at least ${this.slowQuorum} parents`);
      }
    }
    const vertex = new FastPathVertex(nodeId, round, payload, parents);
    if (!this.dag.has(round)) {
      this.dag.set(round, new Map());
    }
    this.dag.get(round).set(vertex.hash, vertex);
    this.vertexIndex.set(vertex.hash, vertex);
    return vertex;
  }

  getRoundLeader(round) {
    const leaderNode = this.nodes[round % this.n];
    const roundMap = this.dag.get(round);
    if (!roundMap) return null;
    for (const v of roundMap.values()) {
      if (v.nodeId === leaderNode) return v;
    }
    return null;
  }

  _isReachable(fromVertex, targetHash, visited = new Set()) {
    if (fromVertex.hash === targetHash) return true;
    if (fromVertex.round <= 0) return false;
    visited.add(fromVertex.hash);

    for (const pHash of fromVertex.parents) {
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

  tryFastPathCommit(leaderRound) {
    const leader = this.getRoundLeader(leaderRound);
    if (!leader) return false;

    // Fast path: all n nodes in round (leaderRound + 1) directly reference leader
    const nextRound = this.dag.get(leaderRound + 1);
    if (!nextRound) return false;

    let fastCount = 0;
    for (const voter of nextRound.values()) {
      if (this._isReachable(voter, leader.hash)) {
        fastCount++;
      }
    }

    if (fastCount >= this.fastQuorum) {
      this.committedLeaders.push({ leader, path: 'FAST_PATH_2_ROUNDS' });
      this._orderCausalPast(leader);
      return true;
    }
    return false;
  }

  _orderCausalPast(leaderVertex) {
    const history = [];
    const visited = new Set();

    const dfs = (v) => {
      if (!v || visited.has(v.hash) || this.orderedHashes.has(v.hash)) return;
      visited.add(v.hash);

      const sortedParents = v.parents.slice().sort();
      for (const pHash of sortedParents) {
        const p = this.vertexIndex.get(pHash);
        if (p) dfs(p);
      }
      history.push(v);
    };

    dfs(leaderVertex);

    for (const v of history) {
      if (!this.orderedHashes.has(v.hash)) {
        this.orderedHashes.add(v.hash);
        this.linearOrder.push(v);
      }
    }
  }

  getLinearOrder() {
    return this.linearOrder.map(v => ({
      hash: v.hash,
      round: v.round,
      nodeId: v.nodeId,
      payload: v.payload
    }));
  }
}

module.exports = { BullsharkFastPath, FastPathVertex };
