/**
 * Fast-HotStuff Pipelined BFT Consensus Engine
 * Implements leader-driven pipelined BFT consensus with linear O(n) message complexity
 * and chained commit rules. Nodes vote with threshold signatures forming Quorum Certificates (QCs).
 * A block is committed when a three-chain of consecutive QCs is formed.
 */

const crypto = require('crypto');

function sha256(data) {
  return crypto.createHash('sha256').update(typeof data === 'string' ? data : JSON.stringify(data)).digest('hex');
}

class QuorumCertificate {
  constructor(blockHash, viewNumber, signatures) {
    this.blockHash = blockHash;
    this.viewNumber = viewNumber;
    this.signatures = signatures; // Map of node -> sig
    this.qcId = sha256({ blockHash, viewNumber, signers: Object.keys(signatures).sort() });
  }
}

class HotStuffBlock {
  constructor(proposer, viewNumber, parentQC, payload) {
    this.proposer = proposer;
    this.viewNumber = viewNumber;
    this.parentQC = parentQC; // QC of parent block
    this.payload = payload;
    this.hash = sha256({
      proposer,
      viewNumber,
      parentQcId: parentQC ? parentQC.qcId : 'GENESIS',
      payload
    });
  }
}

class FastHotStuffBFT {
  constructor(nodes, faultTolerance) {
    this.nodes = nodes; // ['node_0', 'node_1', 'node_2', 'node_3']
    this.n = nodes.length;
    this.f = faultTolerance || Math.floor((this.n - 1) / 3);
    this.quorum = 2 * this.f + 1;

    this.currentView = 1;
    this.blocks = new Map(); // blockHash -> HotStuffBlock
    this.qcs = new Map(); // qcId -> QuorumCertificate
    this.committedBlocks = [];

    // Initialize genesis QC
    this.genesisQC = new QuorumCertificate('GENESIS_BLOCK', 0, { genesis: 'sig' });
    this.highQC = this.genesisQC;
  }

  proposeBlock(proposer, payload) {
    const block = new HotStuffBlock(proposer, this.currentView, this.highQC, payload);
    this.blocks.set(block.hash, block);
    return block;
  }

  formQC(blockHash) {
    const block = this.blocks.get(blockHash);
    if (!block) throw new Error('Block not found: ' + blockHash);

    // Collect quorum signatures from nodes
    const signatures = {};
    for (let i = 0; i < this.quorum; i++) {
      const node = this.nodes[i];
      signatures[node] = sha256(`${node}_vote_${blockHash}`);
    }

    const qc = new QuorumCertificate(blockHash, block.viewNumber, signatures);
    this.qcs.set(qc.qcId, qc);
    this.highQC = qc;

    // Check three-chain commit rule:
    // If b* <- b'' <- b' where b' has QC, b'' has QC, b* is committed
    this._checkThreeChainCommit(block);

    this.currentView++;
    return qc;
  }

  _checkThreeChainCommit(currentBlock) {
    // Current block is b'
    if (!currentBlock.parentQC) return;
    const bDoublePrime = this.blocks.get(currentBlock.parentQC.blockHash);
    if (!bDoublePrime || !bDoublePrime.parentQC) return;

    const bStar = this.blocks.get(bDoublePrime.parentQC.blockHash);
    if (bStar && !this.committedBlocks.includes(bStar)) {
      this.committedBlocks.push(bStar);
    }
  }

  getCommittedBlocks() {
    return this.committedBlocks;
  }
}

module.exports = { FastHotStuffBFT, HotStuffBlock, QuorumCertificate };
