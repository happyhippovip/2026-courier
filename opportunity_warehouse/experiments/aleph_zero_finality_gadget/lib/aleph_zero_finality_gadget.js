/**
 * Aleph-Zero Asynchronous Finality Gadget Consensus Engine
 * Decouples optimistic block authoring from deterministic finality.
 * Authors produce blocks rapidly; the finality gadget runs independent rounds
 * collecting justifications (>= 2f + 1 precommits) to freeze finalized ledger heights.
 */

const crypto = require('crypto');

function sha256(data) {
  return crypto.createHash('sha256').update(typeof data === 'string' ? data : JSON.stringify(data)).digest('hex');
}

class BlockProposal {
  constructor(author, height, parentHash, data) {
    this.author = author;
    this.height = height;
    this.parentHash = parentHash;
    this.data = data;
    this.hash = sha256({ author, height, parentHash, data });
  }
}

class FinalityJustification {
  constructor(blockHash, height, round, signatures) {
    this.blockHash = blockHash;
    this.height = height;
    this.round = round;
    this.signatures = signatures; // Map(node -> sig)
    this.justificationId = sha256({ blockHash, height, round, signers: Object.keys(signatures).sort() });
  }
}

class AlephZeroFinalityGadget {
  constructor(nodes, faultTolerance = 1) {
    this.nodes = nodes; // ['node_0', 'node_1', 'node_2', 'node_3']
    this.n = nodes.length;
    this.f = faultTolerance;
    this.quorum = 2 * this.f + 1;

    this.chain = []; // Array of BlockProposal
    this.finalizedHeight = 0;
    this.justifications = new Map(); // height -> FinalityJustification
  }

  authorBlock(author, data) {
    const parentHash = this.chain.length > 0 ? this.chain[this.chain.length - 1].hash : 'GENESIS';
    const height = this.chain.length + 1;
    const block = new BlockProposal(author, height, parentHash, data);
    this.chain.push(block);
    return block;
  }

  finalizeBlock(height, round = 1) {
    if (height <= this.finalizedHeight) {
      throw new Error('Height already finalized: ' + height);
    }
    if (height > this.chain.length) {
      throw new Error('Block at height ' + height + ' not authored yet');
    }

    const block = this.chain[height - 1];

    // Collect quorum justifications
    const signatures = {};
    for (let i = 0; i < this.quorum; i++) {
      const node = this.nodes[i];
      signatures[node] = sha256(`${node}_finalize_${block.hash}_h${height}`);
    }

    const justification = new FinalityJustification(block.hash, height, round, signatures);
    this.justifications.set(height, justification);
    this.finalizedHeight = height;

    return justification;
  }

  isFinalized(height) {
    return height <= this.finalizedHeight;
  }

  getFinalizedHead() {
    if (this.finalizedHeight === 0) return null;
    return this.chain[this.finalizedHeight - 1];
  }
}

module.exports = { AlephZeroFinalityGadget, BlockProposal, FinalityJustification };
