/**
 * Tusk-HotStuff Hybrid BFT Consensus Engine
 * Merges high-throughput DAG mempool dissemination with chained HotStuff pipelining.
 * Disseminates large payloads across asynchronous DAG rounds, while a lightweight
 * HotStuff consensus chain sequences DAG batch certificates with linear message complexity.
 */

const crypto = require('crypto');

function sha256(data) {
  return crypto.createHash('sha256').update(typeof data === 'string' ? data : JSON.stringify(data)).digest('hex');
}

class CertificateOfAvailability {
  constructor(batchId, round, workerId, signatures) {
    this.batchId = batchId;
    this.round = round;
    this.workerId = workerId;
    this.signatures = signatures;
    this.coaId = sha256({ batchId, round, workerId, signers: Object.keys(signatures).sort() });
  }
}

class HotStuffChainedNode {
  constructor(view, coaRef, parentQC) {
    this.view = view;
    this.coaRef = coaRef; // References Narwhal/Tusk CoA
    this.parentQC = parentQC;
    this.hash = sha256({ view, coaRef, parentQc: parentQC ? parentQC.qcId : 'GENESIS' });
  }
}

class TuskHotStuffEngine {
  constructor(nodes, faultTolerance = 1) {
    this.nodes = nodes; // ['node_0', 'node_1', 'node_2', 'node_3']
    this.n = nodes.length;
    this.f = faultTolerance;
    this.quorum = 2 * this.f + 1;

    this.currentView = 1;
    this.coas = new Map(); // coaId -> CertificateOfAvailability
    this.chain = new Map(); // hash -> HotStuffChainedNode
    this.committedCoas = [];

    this.genesisQC = { qcId: 'GENESIS_QC', blockHash: 'GENESIS_BLOCK', view: 0 };
    this.highQC = this.genesisQC;
  }

  publishCoA(batchId, round, workerId) {
    const signatures = {};
    for (let i = 0; i < this.quorum; i++) {
      const node = this.nodes[i];
      signatures[node] = sha256(`${node}_coa_${batchId}`);
    }
    const coa = new CertificateOfAvailability(batchId, round, workerId, signatures);
    this.coas.set(coa.coaId, coa);
    return coa;
  }

  proposeNode(coaRef) {
    if (!this.coas.has(coaRef)) {
      throw new Error('Cannot propose block referencing unknown CoA: ' + coaRef);
    }
    const node = new HotStuffChainedNode(this.currentView, coaRef, this.highQC);
    this.chain.set(node.hash, node);
    return node;
  }

  voteAndFormQC(blockHash) {
    const node = this.chain.get(blockHash);
    if (!node) throw new Error('Block not found: ' + blockHash);

    const signatures = {};
    for (let i = 0; i < this.quorum; i++) {
      const vNode = this.nodes[i];
      signatures[vNode] = sha256(`${vNode}_hs_vote_${blockHash}`);
    }

    const qc = {
      qcId: sha256({ blockHash, view: node.view, signers: Object.keys(signatures).sort() }),
      blockHash,
      view: node.view,
      signatures
    };

    this.highQC = qc;

    // HotStuff 2-chain / 3-chain commit rule
    if (node.parentQC && node.parentQC.blockHash !== 'GENESIS_BLOCK') {
      const parentNode = this.chain.get(node.parentQC.blockHash);
      if (parentNode && !this.committedCoas.includes(parentNode.coaRef)) {
        this.committedCoas.push(parentNode.coaRef);
      }
    }

    this.currentView++;
    return qc;
  }

  getCommittedCoas() {
    return this.committedCoas;
  }
}

module.exports = { TuskHotStuffEngine, CertificateOfAvailability, HotStuffChainedNode };
