/**
 * Multi-Agent Distributed Asynchronous Verifiable Aleph-HotStuff Hybrid Consensus Engine
 * Combines Aleph (asynchronous DAG-based wave unit creation with threshold coin round witnesses)
 * with HotStuff linear view-based pipelining for deterministic, high-throughput commercial state commitment.
 */

const crypto = require('crypto');

function hashObject(obj) {
  return crypto.createHash('sha256').update(JSON.stringify(obj)).digest('hex');
}

class AlephDAGUnit {
  constructor(creator, round, parents, txs) {
    this.creator = creator;
    this.round = round;
    this.parents = Array.isArray(parents) ? parents.sort() : [];
    this.txs = Array.isArray(txs) ? txs : [];
    this.timestamp = Date.now();
    this.unitId = hashObject({
      creator: this.creator,
      round: this.round,
      parents: this.parents,
      txs: this.txs
    });
  }
}

class AlephWaveCertificate {
  constructor(waveIndex, round, units, quorumSignatures) {
    this.waveIndex = waveIndex;
    this.round = round;
    this.units = units;
    this.quorumSignatures = quorumSignatures;
    this.certId = hashObject({
      waveIndex: this.waveIndex,
      round: this.round,
      units: this.units.map(u => u.unitId).sort()
    });
  }
}

class HotStuffBlock {
  constructor(view, parentHash, waveCert, leaderId) {
    this.view = view;
    this.parentHash = parentHash;
    this.waveCert = waveCert;
    this.leaderId = leaderId;
    this.blockHash = hashObject({
      view: this.view,
      parentHash: this.parentHash,
      waveCertId: this.waveCert ? this.waveCert.certId : null,
      leaderId: this.leaderId
    });
  }
}

class AlephHotStuffEngine {
  constructor(nodeCount = 4) {
    this.nodeCount = nodeCount;
    this.f = Math.floor((nodeCount - 1) / 3); // Byzantine tolerance f=1 for N=4
    this.quorumSize = 2 * this.f + 1; // 3 for N=4

    // Aleph DAG storage: map unitId -> unit
    this.dagUnits = new Map();
    // Units per round per creator to detect equivocation
    this.unitsByRoundCreator = new Map(); // "round:creator" -> unitId
    this.waveCertificates = new Map(); // waveIndex -> AlephWaveCertificate

    // HotStuff storage
    this.blocks = new Map(); // blockHash -> HotStuffBlock
    this.qcs = new Map(); // view -> QC
    this.committedWaves = [];
    this.committedTxs = [];

    // Initialize Genesis Block (view 0)
    const genesis = new HotStuffBlock(0, '0000000000000000000000000000000000000000000000000000000000000000', null, 'GENESIS');
    this.blocks.set(genesis.blockHash, genesis);
    this.highestQC = { view: 0, blockHash: genesis.blockHash, signatures: [] };
    this.qcs.set(0, this.highestQC);
  }

  addDAGUnit(creator, round, parents, txs) {
    const key = round + ':' + creator;
    if (this.unitsByRoundCreator.has(key)) {
      throw new Error('Equivocation detected: creator ' + creator + ' already produced unit in round ' + round);
    }

    if (round > 0) {
      if (!parents || parents.length < this.quorumSize) {
        throw new Error('Insufficient parents for round ' + round + ': requires at least ' + this.quorumSize);
      }
      for (const pId of parents) {
        if (!this.dagUnits.has(pId)) {
          throw new Error('Unknown parent unit: ' + pId);
        }
        const parentUnit = this.dagUnits.get(pId);
        if (parentUnit.round !== round - 1) {
          throw new Error('Invalid parent round: parent ' + pId + ' is round ' + parentUnit.round + ', expected ' + (round - 1));
        }
      }
    }

    const unit = new AlephDAGUnit(creator, round, parents, txs);
    this.dagUnits.set(unit.unitId, unit);
    this.unitsByRoundCreator.set(key, unit.unitId);
    return unit;
  }

  certifyWave(waveIndex, round) {
    // Gather all units from this round
    const roundUnits = [];
    for (const [id, unit] of this.dagUnits.entries()) {
      if (unit.round === round) {
        roundUnits.push(unit);
      }
    }

    if (roundUnits.length < this.quorumSize) {
      throw new Error('Cannot certify wave ' + waveIndex + ': round ' + round + ' has ' + roundUnits.length + ' units, quorum requires ' + this.quorumSize);
    }

    const quorumSignatures = roundUnits.slice(0, this.quorumSize).map(u => ({
      creator: u.creator,
      sig: hashObject({ unitId: u.unitId, certRole: 'ALEPH_WAVE_WITNESS' })
    }));

    const cert = new AlephWaveCertificate(waveIndex, round, roundUnits, quorumSignatures);
    this.waveCertificates.set(waveIndex, cert);
    return cert;
  }

  proposeBlock(view, parentHash, waveIndex, leaderId) {
    const parentBlock = this.blocks.get(parentHash);
    if (!parentBlock) {
      throw new Error('Parent block not found: ' + parentHash);
    }

    let waveCert = null;
    if (waveIndex !== null && waveIndex !== undefined) {
      waveCert = this.waveCertificates.get(waveIndex);
      if (!waveCert) {
        throw new Error('Wave certificate not found for waveIndex: ' + waveIndex);
      }
    }

    const block = new HotStuffBlock(view, parentHash, waveCert, leaderId);
    this.blocks.set(block.blockHash, block);
    return block;
  }

  createQC(view, blockHash) {
    const block = this.blocks.get(blockHash);
    if (!block) throw new Error('Cannot create QC for non-existent block: ' + blockHash);

    const signatures = [];
    for (let i = 0; i < this.quorumSize; i++) {
      signatures.push({
        nodeId: 'node_' + i,
        sig: hashObject({ view, blockHash, role: 'VOTE' })
      });
    }

    const qc = { view, blockHash, signatures };
    this.qcs.set(view, qc);
    if (view > this.highestQC.view) {
      this.highestQC = qc;
    }
    return qc;
  }

  evaluate3ChainCommit(b3Hash) {
    // HotStuff 3-Chain Rule:
    // B3 -> B2 -> B1 -> B0
    // If B3, B2, B1 form direct consecutive views (v3 = v2 + 1, v2 = v1 + 1)
    // then B1 is committed!
    const b3 = this.blocks.get(b3Hash);
    if (!b3) return null;

    const b2 = this.blocks.get(b3.parentHash);
    if (!b2) return null;

    const b1 = this.blocks.get(b2.parentHash);
    if (!b1) return null;

    if (b3.view === b2.view + 1 && b2.view === b1.view + 1) {
      // Commit B1
      return this._commitBlock(b1);
    }

    return null;
  }

  _commitBlock(block) {
    if (!block.waveCert) {
      return { committed: false, reason: 'NO_WAVE_CERT_IN_BLOCK' };
    }

    const waveCert = block.waveCert;
    if (this.committedWaves.includes(waveCert.waveIndex)) {
      return { committed: false, reason: 'WAVE_ALREADY_COMMITTED' };
    }

    // Deterministically order transactions within the wave:
    // Order units by creator ID ascending, then collect txs
    const sortedUnits = [...waveCert.units].sort((a, b) => a.creator.localeCompare(b.creator));
    const waveTxs = [];
    for (const u of sortedUnits) {
      waveTxs.push(...u.txs);
    }

    this.committedWaves.push(waveCert.waveIndex);
    this.committedTxs.push(...waveTxs);

    return {
      committed: true,
      committedBlockView: block.view,
      committedBlockHash: block.blockHash,
      waveIndex: waveCert.waveIndex,
      totalCommittedTxs: this.committedTxs.length,
      waveTxs
    };
  }

  getEngineStats() {
    return {
      nodeCount: this.nodeCount,
      dagUnitsCount: this.dagUnits.size,
      certifiedWavesCount: this.waveCertificates.size,
      blocksCount: this.blocks.size,
      committedWaves: this.committedWaves,
      totalCommittedTxs: this.committedTxs.length
    };
  }
}

module.exports = { AlephDAGUnit, AlephWaveCertificate, HotStuffBlock, AlephHotStuffEngine };
