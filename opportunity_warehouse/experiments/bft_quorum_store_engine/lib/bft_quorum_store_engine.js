/**
 * Multi-Agent Distributed Asynchronous Verifiable Byzantine Quorum Store & HotStuff Consensus Engine
 * Decouples transaction dissemination and Proof of Availability (PoA) from HotStuff consensus ordering.
 * Quorum store nodes certify batch availability before the consensus leader proposes the batch digest.
 */

const crypto = require('crypto');

function hashObject(obj) {
  return crypto.createHash('sha256').update(JSON.stringify(obj)).digest('hex');
}

class TransactionBatch {
  constructor(batchId, author, txs) {
    this.batchId = batchId;
    this.author = author;
    this.txs = Array.isArray(txs) ? txs : [];
    this.timestamp = Date.now();
    this.batchHash = hashObject({ batchId, author, txs });
  }
}

class ProofOfAvailability {
  constructor(batchId, batchHash, signatures) {
    this.batchId = batchId;
    this.batchHash = batchHash;
    this.signatures = signatures;
    this.poaId = hashObject({ batchId, batchHash, sigs: signatures.map(s => s.nodeId).sort() });
  }
}

class BFTQuorumStoreHotStuffEngine {
  constructor(nodeCount = 4) {
    this.nodeCount = nodeCount;
    this.f = Math.floor((nodeCount - 1) / 3); // f=1
    this.quorumSize = 2 * this.f + 1; // 3

    // Quorum Store storage
    this.batches = new Map(); // batchId -> TransactionBatch
    this.poas = new Map(); // batchId -> ProofOfAvailability
    this.batchSignatures = new Map(); // batchId -> Map of nodeId -> sig

    // HotStuff storage
    this.blocks = new Map();
    this.qcs = new Map();
    this.committedBlocks = [];
    this.committedTxs = [];

    // Genesis Block
    const genesisHash = '0000000000000000000000000000000000000000000000000000000000000000';
    const genesis = { view: 0, parentHash: genesisHash, poaIds: [], blockHash: genesisHash, leaderId: 'GENESIS' };
    this.blocks.set(genesisHash, genesis);
    this.highestQC = { view: 0, blockHash: genesisHash, signatures: [] };
  }

  submitBatch(batchId, author, txs) {
    const batch = new TransactionBatch(batchId, author, txs);
    this.batches.set(batchId, batch);
    this.batchSignatures.set(batchId, new Map());
    return batch;
  }

  signBatchAvailability(batchId, nodeId) {
    const batch = this.batches.get(batchId);
    if (!batch) throw new Error('Batch not found: ' + batchId);

    const sigs = this.batchSignatures.get(batchId);
    if (sigs.has(nodeId)) {
      throw new Error('Node ' + nodeId + ' already signed batch ' + batchId);
    }

    const sig = hashObject({ batchId, batchHash: batch.batchHash, nodeId, role: 'POA_SIGNATURE' });
    sigs.set(nodeId, { nodeId, sig });

    if (sigs.size >= this.quorumSize && !this.poas.has(batchId)) {
      const poa = new ProofOfAvailability(batchId, batch.batchHash, Array.from(sigs.values()).slice(0, this.quorumSize));
      this.poas.set(batchId, poa);
      return { poaCreated: true, poa };
    }

    return { poaCreated: false, currentSignatures: sigs.size };
  }

  proposeConsensusBlock(view, parentHash, poaBatchIds, leaderId) {
    if (!this.blocks.has(parentHash)) {
      throw new Error('Parent block not found: ' + parentHash);
    }

    // Verify all included batch IDs have certified Proofs of Availability
    for (const bId of poaBatchIds) {
      if (!this.poas.has(bId)) {
        throw new Error('Cannot propose block with uncertified batch availability: ' + bId);
      }
    }

    const blockHash = hashObject({ view, parentHash, poaBatchIds, leaderId });
    const block = { view, parentHash, poaBatchIds, leaderId, blockHash };
    this.blocks.set(blockHash, block);
    return block;
  }

  createQC(view, blockHash) {
    const block = this.blocks.get(blockHash);
    if (!block) throw new Error('Block not found for QC: ' + blockHash);

    const signatures = [];
    for (let i = 0; i < this.quorumSize; i++) {
      signatures.push({
        nodeId: 'node_' + i,
        sig: hashObject({ view, blockHash, role: 'QUORUM_STORE_HOTSTUFF_VOTE' })
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
    const b3 = this.blocks.get(b3Hash);
    if (!b3) return null;
    const b2 = this.blocks.get(b3.parentHash);
    if (!b2) return null;
    const b1 = this.blocks.get(b2.parentHash);
    if (!b1) return null;

    if (b3.view === b2.view + 1 && b2.view === b1.view + 1) {
      return this._commitBlock(b1);
    }
    return null;
  }

  _commitBlock(block) {
    if (this.committedBlocks.includes(block.blockHash)) {
      return { committed: false, reason: 'ALREADY_COMMITTED' };
    }

    const committedTxs = [];
    for (const bId of block.poaBatchIds) {
      const batch = this.batches.get(bId);
      if (batch) {
        committedTxs.push(...batch.txs);
      }
    }

    this.committedBlocks.push(block.blockHash);
    this.committedTxs.push(...committedTxs);

    return {
      committed: true,
      mode: 'QUORUM_STORE_HOTSTUFF_3CHAIN_COMMIT',
      view: block.view,
      blockHash: block.blockHash,
      poaBatchIds: block.poaBatchIds,
      committedTxs,
      totalCommittedTxs: this.committedTxs.length
    };
  }

  getStats() {
    return {
      nodeCount: this.nodeCount,
      storedBatches: this.batches.size,
      certifiedPoAs: this.poas.size,
      blocksCount: this.blocks.size,
      committedBlocksCount: this.committedBlocks.length,
      totalCommittedTxs: this.committedTxs.length
    };
  }
}

module.exports = { TransactionBatch, ProofOfAvailability, BFTQuorumStoreHotStuffEngine };
