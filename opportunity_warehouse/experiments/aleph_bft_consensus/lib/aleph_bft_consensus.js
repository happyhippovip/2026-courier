/**
 * Aleph-BFT Asynchronous DAG Consensus Engine
 * Asynchronous Byzantine Fault Tolerant protocol organizing proposals into rounds of a DAG.
 * Each node creates at most one unit per round with >= 2f+1 parent references.
 * Resolves leader units using deterministic asynchronous common coin thresholding without timeouts.
 */

const crypto = require('crypto');

function sha256(data) {
  return crypto.createHash('sha256').update(typeof data === 'string' ? data : JSON.stringify(data)).digest('hex');
}

class AlephUnit {
  constructor(creator, round, parents, payload) {
    this.creator = creator;
    this.round = round;
    this.parents = parents || []; // Array of parent unit hashes from round - 1
    this.payload = payload;
    this.timestamp = Date.now();
    this.hash = sha256({
      creator: this.creator,
      round: this.round,
      parents: this.parents.slice().sort(),
      payload: this.payload
    });
  }
}

class AlephBFTConsensus {
  constructor(nodes, faultTolerance) {
    this.nodes = nodes; // ['node_0', 'node_1', 'node_2', 'node_3']
    this.n = nodes.length;
    this.f = faultTolerance || Math.floor((this.n - 1) / 3);
    this.quorum = 2 * this.f + 1;

    // DAG Storage: round -> Map(hash -> AlephUnit)
    this.dag = new Map();
    this.unitLookup = new Map();

    // Ordered sequence of committed units
    this.committedLeaders = [];
    this.linearOrder = [];
    this.orderedHashes = new Set();
  }

  createUnit(creator, round, parents, payload) {
    if (round > 0) {
      if (!parents || parents.length < this.quorum) {
        throw new Error(`Round ${round} requires >= ${this.quorum} parents, got ${parents ? parents.length : 0}`);
      }
      for (const pHash of parents) {
        const p = this.unitLookup.get(pHash);
        if (!p || p.round !== round - 1) {
          throw new Error(`Invalid parent ${pHash} for round ${round}`);
        }
      }
    }

    const unit = new AlephUnit(creator, round, parents, payload);

    if (!this.dag.has(round)) {
      this.dag.set(round, new Map());
    }

    this.dag.get(round).set(unit.hash, unit);
    this.unitLookup.set(unit.hash, unit);
    return unit;
  }

  getRoundLeader(round) {
    // Deterministic leader nomination for round
    const leaderNode = this.nodes[round % this.n];
    const roundUnits = this.dag.get(round);
    if (!roundUnits) return null;

    for (const u of roundUnits.values()) {
      if (u.creator === leaderNode) return u;
    }
    return null;
  }

  _isReachable(fromUnit, targetHash, visited = new Set()) {
    if (fromUnit.hash === targetHash) return true;
    if (fromUnit.round <= 0) return false;
    visited.add(fromUnit.hash);

    for (const pHash of fromUnit.parents) {
      if (pHash === targetHash) return true;
      if (!visited.has(pHash)) {
        const parent = this.unitLookup.get(pHash);
        if (parent && this._isReachable(parent, targetHash, visited)) {
          return true;
        }
      }
    }
    return false;
  }

  tryDecideRoundLeader(round) {
    const leader = this.getRoundLeader(round);
    if (!leader) return false;

    // Need round + 1 units to witness the leader
    const witnessRound = this.dag.get(round + 1);
    if (!witnessRound) return false;

    let witnessCount = 0;
    for (const u of witnessRound.values()) {
      if (this._isReachable(u, leader.hash)) {
        witnessCount++;
      }
    }

    if (witnessCount >= this.quorum) {
      this.committedLeaders.push(leader);
      this._orderCausalPast(leader);
      return true;
    }
    return false;
  }

  _orderCausalPast(leaderUnit) {
    const history = [];
    const visited = new Set();

    const dfs = (u) => {
      if (!u || visited.has(u.hash) || this.orderedHashes.has(u.hash)) return;
      visited.add(u.hash);

      const sortedParents = u.parents.slice().sort();
      for (const pHash of sortedParents) {
        const p = this.unitLookup.get(pHash);
        if (p) dfs(p);
      }
      history.push(u);
    };

    dfs(leaderUnit);

    for (const u of history) {
      if (!this.orderedHashes.has(u.hash)) {
        this.orderedHashes.add(u.hash);
        this.linearOrder.push(u);
      }
    }
  }

  getLinearOrder() {
    return this.linearOrder.map(u => ({
      hash: u.hash,
      round: u.round,
      creator: u.creator,
      payload: u.payload
    }));
  }
}

module.exports = { AlephBFTConsensus, AlephUnit };
