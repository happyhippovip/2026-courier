/**
 * Multi-Agent Distributed Asynchronous Verifiable Bullshark-HotStuff Hybrid Consensus Engine
 * Implements Bullshark's zero-overhead optimistic fast-path DAG ordering
 * paired with HotStuff linear view-based pipelining fallback.
 */

const crypto = require('crypto');

function hashObject(obj) {
  return crypto.createHash('sha256').update(JSON.stringify(obj)).digest('hex');
}

class BullsharkVertex {
  constructor(creator, round, parents, txs) {
    this.creator = creator;
    this.round = round;
    this.parents = Array.isArray(parents) ? parents.sort() : [];
    this.txs = Array.isArray(txs) ? txs : [];
    this.timestamp = Date.now();
    this.vertexId = hashObject({
      creator: this.creator,
      round: this.round,
      parents: this.parents,
      txs: this.txs
    });
  }
}

class BullsharkWaveCertificate {
  constructor(waveIndex, anchorLeaderVertexId, round, supportedVertices) {
    this.waveIndex = waveIndex;
    this.anchorLeaderVertexId = anchorLeaderVertexId;
    this.round = round;
    this.supportedVertices = supportedVertices;
    this.certId = hashObject({
      waveIndex: this.waveIndex,
      anchorLeaderVertexId: this.anchorLeaderVertexId,
      round: this.round,
      supportedVertices: this.supportedVertices.map(v => v.vertexId).sort()
    });
  }
}

class BullsharkHotStuffEngine {
  constructor(nodeCount = 4) {
    this.nodeCount = nodeCount;
    this.f = Math.floor((nodeCount - 1) / 3); // f=1
    this.quorumSize = 2 * this.f + 1; // 3

    this.vertices = new Map(); // vertexId -> BullsharkVertex
    this.vertexByRoundCreator = new Map(); // "round:creator" -> vertexId
    this.waveCertificates = new Map(); // waveIndex -> BullsharkWaveCertificate
    this.committedWaves = [];
    this.committedTxs = [];

    // Fallback HotStuff Block & QC storage
    this.blocks = new Map();
    this.qcs = new Map();
    this.currentView = 0;
  }

  addVertex(creator, round, parents, txs) {
    const key = round + ':' + creator;
    if (this.vertexByRoundCreator.has(key)) {
      throw new Error('Equivocation detected: creator ' + creator + ' already produced vertex in round ' + round);
    }

    if (round > 0) {
      if (!parents || parents.length < this.quorumSize) {
        throw new Error('Insufficient parents for round ' + round + ': requires >= ' + this.quorumSize);
      }
      for (const pId of parents) {
        if (!this.vertices.has(pId)) {
          throw new Error('Parent vertex not found: ' + pId);
        }
        const p = this.vertices.get(pId);
        if (p.round !== round - 1) {
          throw new Error('Invalid parent round: ' + p.round + ', expected ' + (round - 1));
        }
      }
    }

    const v = new BullsharkVertex(creator, round, parents, txs);
    this.vertices.set(v.vertexId, v);
    this.vertexByRoundCreator.set(key, v.vertexId);
    return v;
  }

  evaluateFastPathCommit(waveIndex, leaderRound) {
    // In Bullshark: Wave leader is elected at even round 2*w
    // Next round (2*w + 1) votes by referencing the leader vertex as a parent.
    // If >= 2f+1 nodes in round 2*w + 1 reference the round 2*w leader,
    // the leader vertex is committed immediately on the FAST PATH without timeouts!
    const leaderCreator = 'node_' + (waveIndex % this.nodeCount);
    const leaderKey = leaderRound + ':' + leaderCreator;
    const leaderVertexId = this.vertexByRoundCreator.get(leaderKey);
    if (!leaderVertexId) {
      return { committed: false, reason: 'LEADER_VERTEX_MISSING' };
    }

    const votingRound = leaderRound + 1;
    const votingVertices = [];
    for (const v of this.vertices.values()) {
      if (v.round === votingRound && v.parents.includes(leaderVertexId)) {
        votingVertices.push(v);
      }
    }

    if (votingVertices.length >= this.quorumSize) {
      // Fast path succeeded!
      const supported = [this.vertices.get(leaderVertexId), ...votingVertices];
      const cert = new BullsharkWaveCertificate(waveIndex, leaderVertexId, leaderRound, supported);
      this.waveCertificates.set(waveIndex, cert);

      return this._commitWave(cert, 'BULLSHARK_FAST_PATH');
    }

    return { committed: false, reason: 'QUORUM_VOTES_NOT_REACHED', votes: votingVertices.length };
  }

  proposeHotStuffFallbackBlock(view, parentHash, waveIndex, leaderId) {
    // If fast path timed out or had missing quorum, HotStuff fallback block commits the wave
    const waveCert = this.waveCertificates.get(waveIndex);
    if (!waveCert) {
      throw new Error('Wave certificate missing for waveIndex: ' + waveIndex);
    }

    const blockHash = hashObject({ view, parentHash, waveCertId: waveCert.certId, leaderId });
    const block = { view, parentHash, waveCert, leaderId, blockHash };
    this.blocks.set(blockHash, block);
    return block;
  }

  commitHotStuffFallback(blockHash) {
    const block = this.blocks.get(blockHash);
    if (!block) throw new Error('Block not found: ' + blockHash);
    return this._commitWave(block.waveCert, 'HOTSTUFF_FALLBACK');
  }

  _commitWave(waveCert, mode) {
    if (this.committedWaves.includes(waveCert.waveIndex)) {
      return { committed: false, reason: 'WAVE_ALREADY_COMMITTED' };
    }

    // Deterministically order transactions in the wave:
    // 1. Leader vertex txs first
    // 2. Voting vertices ordered by creator ID ascending
    const orderedTxs = [];
    const leaderVertex = this.vertices.get(waveCert.anchorLeaderVertexId);
    if (leaderVertex) {
      orderedTxs.push(...leaderVertex.txs);
    }

    const votingVertices = waveCert.supportedVertices
      .filter(v => v.vertexId !== waveCert.anchorLeaderVertexId)
      .sort((a, b) => a.creator.localeCompare(b.creator));

    for (const v of votingVertices) {
      orderedTxs.push(...v.txs);
    }

    this.committedWaves.push(waveCert.waveIndex);
    this.committedTxs.push(...orderedTxs);

    return {
      committed: true,
      mode,
      waveIndex: waveCert.waveIndex,
      leaderVertexId: waveCert.anchorLeaderVertexId,
      totalCommittedTxs: this.committedTxs.length,
      waveTxs: orderedTxs
    };
  }

  getStats() {
    return {
      nodeCount: this.nodeCount,
      vertexCount: this.vertices.size,
      waveCertsCount: this.waveCertificates.size,
      committedWaves: this.committedWaves,
      totalCommittedTxs: this.committedTxs.length
    };
  }
}

module.exports = { BullsharkVertex, BullsharkWaveCertificate, BullsharkHotStuffEngine };
