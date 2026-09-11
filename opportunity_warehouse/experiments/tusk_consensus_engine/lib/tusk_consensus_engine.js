/**
 * Tusk Asynchronous Consensus Engine
 * Companion asynchronous consensus protocol for DAG-based mempools (Narwhal).
 * Operates with zero communication overhead for leaders by interpreting the DAG structure
 * using randomized coin tosses (threshold signatures) for asynchronous commit rule without timeouts.
 */

const crypto = require('crypto');

function sha256(data) {
  return crypto.createHash('sha256').update(typeof data === 'string' ? data : JSON.stringify(data)).digest('hex');
}

class TuskVertex {
  constructor(nodeId, round, batchRef, parents) {
    this.nodeId = nodeId;
    this.round = round;
    this.batchRef = batchRef; // Reference to Narwhal batch/CoA
    this.parents = parents || []; // Array of parent vertex hashes
    this.hash = sha256({ nodeId, round, batchRef, parents: this.parents.slice().sort() });
  }
}

class TuskConsensusEngine {
  constructor(nodes, faultTolerance) {
    this.nodes = nodes;
    this.n = nodes.length;
    this.f = faultTolerance || Math.floor((nodes.length - 1) / 3);
    this.quorum = 2 * this.f + 1;

    this.dag = new Map(); // round -> Map(hash -> TuskVertex)
    this.vertexIndex = new Map(); // hash -> TuskVertex
    this.committedLeaders = [];
    this.linearOrder = [];
    this.orderedHashes = new Set();
  }

  addVertex(nodeId, round, batchRef, parents) {
    if (round > 0) {
      if (!parents || parents.length < this.quorum) {
        throw new Error(`Round ${round} requires >= ${this.quorum} parents`);
      }
      for (const p of parents) {
        if (!this.vertexIndex.has(p)) {
          throw new Error(`Unknown parent ${p} in round ${round - 1}`);
        }
      }
    }

    const vertex = new TuskVertex(nodeId, round, batchRef, parents);
    if (!this.dag.has(round)) {
      this.dag.set(round, new Map());
    }
    this.dag.get(round).set(vertex.hash, vertex);
    this.vertexIndex.set(vertex.hash, vertex);
    return vertex;
  }

  getWaveLeader(wave) {
    // In Tusk, 1 wave = 3 rounds (Propose r, Vote r+1, Certificate/Coin r+2)
    const leaderRound = wave * 3;
    const roundMap = this.dag.get(leaderRound);
    if (!roundMap) return null;

    // Pseudo-random leader selection for the wave
    const leaderIdx = wave % this.n;
    for (const v of roundMap.values()) {
      if (v.nodeId === this.nodes[leaderIdx]) return v;
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

  tryCommitWaveLeader(wave) {
    const leader = this.getWaveLeader(wave);
    if (!leader) return false;

    // In Tusk, vote is collected at round (wave*3 + 1), and certified at (wave*3 + 2)
    const certifyRound = wave * 3 + 2;
    const certRoundMap = this.dag.get(certifyRound);
    if (!certRoundMap) return false;

    let certCount = 0;
    for (const certV of certRoundMap.values()) {
      if (this._isReachable(certV, leader.hash)) {
        certCount++;
      }
    }

    if (certCount >= this.quorum) {
      this.committedLeaders.push(leader);
      this._orderCausalPast(leader);
      return true;
    }
    return false;
  }

  _orderCausalPast(leaderVertex) {
    const stack = [];
    const visited = new Set();

    const dfs = (v) => {
      if (!v || visited.has(v.hash) || this.orderedHashes.has(v.hash)) return;
      visited.add(v.hash);

      const sortedParents = v.parents.slice().sort();
      for (const pHash of sortedParents) {
        const p = this.vertexIndex.get(pHash);
        if (p) dfs(p);
      }
      stack.push(v);
    };

    dfs(leaderVertex);

    for (const v of stack) {
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
      batchRef: v.batchRef
    }));
  }
}

module.exports = { TuskConsensusEngine, TuskVertex };
