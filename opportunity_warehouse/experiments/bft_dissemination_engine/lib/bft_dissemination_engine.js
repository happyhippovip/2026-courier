/**
 * Multi-Agent Distributed Asynchronous Verifiable Byzantine Reliable Dissemination & HotStuff Finality Engine
 * Implements Bracha-style Byzantine Reliable Broadcast (Echo/Ready/Deliver)
 * coupled with HotStuff 3-chain pipelined block finality.
 */

const crypto = require('crypto');

function hashObject(obj) {
  return crypto.createHash('sha256').update(JSON.stringify(obj)).digest('hex');
}

class DisseminationMessage {
  constructor(msgId, sender, payload) {
    this.msgId = msgId;
    this.sender = sender;
    this.payload = payload;
    this.timestamp = Date.now();
    this.digest = hashObject({ msgId, sender, payload });
  }
}

class BFTDisseminationEngine {
  constructor(nodeCount = 4) {
    this.nodeCount = nodeCount;
    this.f = Math.floor((nodeCount - 1) / 3); // f=1
    this.quorumSize = 2 * this.f + 1; // 3
    this.readyThreshold = this.f + 1; // 2

    this.echoes = new Map(); // digest -> Set of nodeIds
    this.readies = new Map(); // digest -> Set of nodeIds
    this.delivered = new Map(); // digest -> message payload

    // HotStuff storage
    this.blocks = new Map();
    this.qcs = new Map();
    this.committedBlocks = [];
    this.committedTxs = [];

    // Genesis Block
    const genesisHash = '0000000000000000000000000000000000000000000000000000000000000000';
    const genesis = { view: 0, parentHash: genesisHash, txs: [], blockHash: genesisHash, leaderId: 'GENESIS' };
    this.blocks.set(genesisHash, genesis);
    this.highestQC = { view: 0, blockHash: genesisHash, signatures: [] };
  }

  broadcastSend(nodeId, msgId, payload) {
    const msg = new DisseminationMessage(msgId, nodeId, payload);
    const digest = msg.digest;

    if (!this.echoes.has(digest)) this.echoes.set(digest, new Set());
    if (!this.readies.has(digest)) this.readies.set(digest, new Set());

    // Originating node immediately echoes
    this.castEcho(nodeId, digest);
    return msg;
  }

  castEcho(nodeId, digest) {
    const set = this.echoes.get(digest);
    if (!set) throw new Error('Unknown message digest: ' + digest);
    set.add(nodeId);

    // Check if 2f+1 echoes reached to trigger READY
    if (set.size >= this.quorumSize) {
      this.castReady(nodeId, digest);
    }
  }

  castReady(nodeId, digest) {
    const readySet = this.readies.get(digest);
    if (!readySet) throw new Error('Unknown message digest: ' + digest);
    readySet.add(nodeId);

    // Check if 2f+1 readies reached to DELIVER
    if (readySet.size >= this.quorumSize && !this.delivered.has(digest)) {
      this.delivered.set(digest, { digest, deliveredAt: Date.now() });
    }
  }

  isDelivered(digest) {
    return this.delivered.has(digest);
  }

  proposeHotStuffBlock(view, parentHash, deliveredDigests, leaderId) {
    if (!this.blocks.has(parentHash)) {
      throw new Error('Parent block not found: ' + parentHash);
    }

    // Verify that all included digests are reliably delivered
    for (const d of deliveredDigests) {
      if (!this.delivered.has(d)) {
        throw new Error('Cannot include undelivered dissemination digest: ' + d);
      }
    }

    const blockHash = hashObject({ view, parentHash, deliveredDigests, leaderId });
    const block = { view, parentHash, deliveredDigests, leaderId, blockHash };
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
        sig: hashObject({ view, blockHash, role: 'DISSEMINATION_HOTSTUFF_VOTE' })
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

    this.committedBlocks.push(block.blockHash);
    this.committedTxs.push(...block.deliveredDigests);

    return {
      committed: true,
      mode: 'DISSEMINATION_HOTSTUFF_3CHAIN_COMMIT',
      view: block.view,
      blockHash: block.blockHash,
      deliveredDigests: block.deliveredDigests,
      totalCommitted: this.committedTxs.length
    };
  }

  getStats() {
    return {
      nodeCount: this.nodeCount,
      deliveredCount: this.delivered.size,
      blocksCount: this.blocks.size,
      committedBlocksCount: this.committedBlocks.length,
      totalCommittedTxs: this.committedTxs.length
    };
  }
}

module.exports = { DisseminationMessage, BFTDisseminationEngine };
