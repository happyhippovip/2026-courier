/**
 * Pipelined HotStuff Consensus Engine
 * Implements pipelined BFT state machine replication (DiemBFT / Pipelined HotStuff).
 * Chains Prepare, Pre-commit, and Commit phases into consecutive proposals.
 * Uses the 3-Chain Rule to commit a block when 3 consecutive descendant blocks receive QCs.
 */

const crypto = require('crypto');

function sha256(data) {
  return crypto.createHash('sha256').update(typeof data === 'string' ? data : JSON.stringify(data)).digest('hex');
}

class PipelinedQC {
  constructor(blockHash, view, signatures) {
    this.blockHash = blockHash;
    this.view = view;
    this.signatures = signatures;
    this.qcId = sha256({ blockHash, view, signers: Object.keys(signatures).sort() });
  }
}

class PipelinedBlock {
  constructor(proposer, view, parentHash, justifyQC, payload) {
    this.proposer = proposer;
    this.view = view;
    this.parentHash = parentHash;
    this.justifyQC = justifyQC; // QC of parent or highQC
    this.payload = payload;
    this.hash = sha256({
      proposer,
      view,
      parentHash,
      justifyQcId: justifyQC ? justifyQC.qcId : 'GENESIS',
      payload
    });
  }
}

class PipelinedHotStuffEngine {
  constructor(nodes, faultTolerance = 1) {
    this.nodes = nodes; // ['n0', 'n1', 'n2', 'n3']
    this.n = nodes.length;
    this.f = faultTolerance;
    this.quorum = 2 * this.f + 1; // 3

    this.currentView = 1;
    this.blocks = new Map(); // blockHash -> PipelinedBlock
    this.committedBlocks = [];

    this.genesisQC = new PipelinedQC('GENESIS_BLOCK', 0, { genesis: 'sig' });
    this.highQC = this.genesisQC;
  }

  propose(proposer, payload) {
    const parentHash = this.highQC.blockHash;
    const block = new PipelinedBlock(proposer, this.currentView, parentHash, this.highQC, payload);
    this.blocks.set(block.hash, block);
    return block;
  }

  voteAndCreateQC(blockHash) {
    const block = this.blocks.get(blockHash);
    if (!block) throw new Error('Block not found: ' + blockHash);

    // Collect 2f+1 signatures
    const signatures = {};
    for (let i = 0; i < this.quorum; i++) {
      const node = this.nodes[i];
      signatures[node] = sha256(`${node}_phs_vote_${blockHash}`);
    }

    const qc = new PipelinedQC(blockHash, block.view, signatures);
    this.highQC = qc;

    // Check Pipelined 3-Chain Commit Rule:
    // If b3 -> b2 -> b1 has 3 direct parent links with consecutive views, commit b1!
    this._checkCommitRule(block);

    this.currentView++;
    return qc;
  }

  _checkCommitRule(b3) {
    const b2 = this.blocks.get(b3.parentHash);
    if (!b2) return;

    const b1 = this.blocks.get(b2.parentHash);
    if (!b1) return;

    // Consecutive direct 3-chain: b3.view === b2.view + 1 && b2.view === b1.view + 1
    if (b3.view === b2.view + 1 && b2.view === b1.view + 1) {
      if (b1.hash !== 'GENESIS_BLOCK' && !this.committedBlocks.includes(b1)) {
        this.committedBlocks.push(b1);
      }
    }
  }

  getCommittedBlocks() {
    return this.committedBlocks;
  }
}

module.exports = { PipelinedHotStuffEngine, PipelinedBlock, PipelinedQC };
