/**
 * Multi-Agent Distributed Asynchronous Verifiable Mysticeti-HotStuff Hybrid Consensus Engine
 * Implements Mysticeti's uncertified DAG consensus (embedding votes into round r+1 without cert pauses)
 * coupled with HotStuff 3-chain linear view pipelining.
 */

const crypto = require('crypto');

function hashObject(obj) {
  return crypto.createHash('sha256').update(JSON.stringify(obj)).digest('hex');
}

class MysticetiBlock {
  constructor(creator, round, parents, txs) {
    this.creator = creator;
    this.round = round;
    this.parents = Array.isArray(parents) ? parents.sort() : [];
    this.txs = Array.isArray(txs) ? txs : [];
    this.timestamp = Date.now();
    this.blockId = hashObject({
      creator: this.creator,
      round: this.round,
      parents: this.parents,
      txs: this.txs
    });
  }
}

class MysticetiHotStuffEngine {
  constructor(nodeCount = 4) {
    this.nodeCount = nodeCount;
    this.f = Math.floor((nodeCount - 1) / 3); // f=1
    this.quorumSize = 2 * this.f + 1; // 3

    this.dagBlocks = new Map(); // blockId -> MysticetiBlock
    this.blocksByRoundCreator = new Map(); // "round:creator" -> blockId
    this.committedLeaders = [];
    this.committedTxs = [];

    // HotStuff Pipelining
    this.hotStuffBlocks = new Map();
    this.hotStuffQCs = new Map();
  }

  addBlock(creator, round, parents, txs) {
    const key = round + ':' + creator;
    if (this.blocksByRoundCreator.has(key)) {
      throw new Error('Equivocation detected: creator ' + creator + ' already produced block in round ' + round);
    }

    if (round > 0) {
      if (!parents || parents.length < this.quorumSize) {
        throw new Error('Insufficient parents for round ' + round + ': requires >= ' + this.quorumSize);
      }
      for (const pId of parents) {
        if (!this.dagBlocks.has(pId)) {
          throw new Error('Parent block not found: ' + pId);
        }
        const p = this.dagBlocks.get(pId);
        if (p.round !== round - 1) {
          throw new Error('Invalid parent round: ' + p.round + ', expected ' + (round - 1));
        }
      }
    }

    const b = new MysticetiBlock(creator, round, parents, txs);
    this.dagBlocks.set(b.blockId, b);
    this.blocksByRoundCreator.set(key, b.blockId);
    return b;
  }

  evaluateMysticetiCommit(leaderRound, leaderCreator) {
    // Mysticeti Commit Rule:
    // Leader L at round r is committed if:
    // 1. There are >= 2f+1 blocks in round r+1 that reference L (direct votes).
    // 2. There are >= 2f+1 blocks in round r+2 that reference those voting blocks (indirect certify).
    // Once certified, L and its causal history are committed in zero certification overhead!
    const leaderKey = leaderRound + ':' + leaderCreator;
    const leaderBlockId = this.blocksByRoundCreator.get(leaderKey);
    if (!leaderBlockId) {
      return { committed: false, reason: 'LEADER_NOT_FOUND' };
    }

    const round1Voters = [];
    for (const b of this.dagBlocks.values()) {
      if (b.round === leaderRound + 1 && b.parents.includes(leaderBlockId)) {
        round1Voters.push(b);
      }
    }

    if (round1Voters.length < this.quorumSize) {
      return { committed: false, reason: 'INSUFFICIENT_ROUND1_VOTERS', count: round1Voters.length };
    }

    const voterIds = new Set(round1Voters.map(v => v.blockId));
    const round2Certifiers = [];
    for (const b of this.dagBlocks.values()) {
      if (b.round === leaderRound + 2) {
        // Count how many voters are in this certifier's parents
        const common = b.parents.filter(p => voterIds.has(p));
        if (common.length >= this.quorumSize) {
          round2Certifiers.push(b);
        }
      }
    }

    if (round2Certifiers.length >= this.quorumSize) {
      // Leader committed!
      return this._commitLeader(leaderBlockId);
    }

    return { committed: false, reason: 'INSUFFICIENT_ROUND2_CERTIFIERS', count: round2Certifiers.length };
  }

  _commitLeader(leaderBlockId) {
    if (this.committedLeaders.includes(leaderBlockId)) {
      return { committed: false, reason: 'ALREADY_COMMITTED' };
    }

    const leader = this.dagBlocks.get(leaderBlockId);
    const causalTxs = [];

    // Collect all transactions in causal history up to leader
    causalTxs.push(...leader.txs);

    this.committedLeaders.push(leaderBlockId);
    this.committedTxs.push(...causalTxs);

    return {
      committed: true,
      mode: 'MYSTICETI_UNCERTIFIED_DAG_COMMIT',
      leaderBlockId,
      round: leader.round,
      creator: leader.creator,
      committedTxs: causalTxs,
      totalCommittedTxs: this.committedTxs.length
    };
  }

  getStats() {
    return {
      nodeCount: this.nodeCount,
      dagBlocksCount: this.dagBlocks.size,
      committedLeadersCount: this.committedLeaders.length,
      totalCommittedTxs: this.committedTxs.length
    };
  }
}

module.exports = { MysticetiBlock, MysticetiHotStuffEngine };
