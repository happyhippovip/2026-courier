/**
 * Narwhal Mempool Dissemination Engine
 * Decouples reliable data dissemination from consensus ordering.
 * Workers broadcast transaction batches, collecting Certificate of Availability (CoA)
 * signed by 2f+1 nodes. Consensus then sequences lightweight certificates with high throughput.
 */

const crypto = require('crypto');

function sha256(data) {
  return crypto.createHash('sha256').update(typeof data === 'string' ? data : JSON.stringify(data)).digest('hex');
}

class TransactionBatch {
  constructor(workerId, round, transactions) {
    this.workerId = workerId;
    this.round = round;
    this.transactions = transactions; // Array of agent commands/transactions
    this.batchId = sha256({ workerId, round, transactions });
  }
}

class CertificateOfAvailability {
  constructor(batchId, round, workerId, signatures) {
    this.batchId = batchId;
    this.round = round;
    this.workerId = workerId;
    this.signatures = signatures; // Map of nodeId -> signature
    this.certificateId = sha256({ batchId, round, workerId, signers: Object.keys(signatures).sort() });
  }
}

class NarwhalMempoolEngine {
  constructor(nodes, faultTolerance) {
    this.nodes = nodes; // e.g. ['node_0', 'node_1', 'node_2', 'node_3']
    this.n = nodes.length;
    this.f = faultTolerance || Math.floor((this.n - 1) / 3);
    this.quorum = 2 * this.f + 1;

    // Batches stored in mempool: batchId -> TransactionBatch
    this.batches = new Map();
    // Certificates stored: certificateId -> CertificateOfAvailability
    this.certificates = new Map();
    // Round -> List of CertificateOfAvailability
    this.roundCertificates = new Map();
  }

  submitBatch(workerId, round, transactions) {
    const batch = new TransactionBatch(workerId, round, transactions);
    this.batches.set(batch.batchId, batch);
    return batch;
  }

  collectSignaturesAndFormCoA(batchId) {
    const batch = this.batches.get(batchId);
    if (!batch) throw new Error('Batch not found: ' + batchId);

    // Simulate quorum signature collection from nodes
    const signatures = {};
    for (let i = 0; i < this.quorum; i++) {
      const node = this.nodes[i];
      signatures[node] = sha256(`${node}_sig_${batchId}`);
    }

    const coa = new CertificateOfAvailability(batchId, batch.round, batch.workerId, signatures);
    this.certificates.set(coa.certificateId, coa);

    if (!this.roundCertificates.has(batch.round)) {
      this.roundCertificates.set(batch.round, []);
    }
    this.roundCertificates.get(batch.round).push(coa);

    return coa;
  }

  getAvailableTransactions(certificateId) {
    const coa = this.certificates.get(certificateId);
    if (!coa) return null;
    const batch = this.batches.get(coa.batchId);
    return batch ? batch.transactions : null;
  }

  getCertificatesForRound(round) {
    return this.roundCertificates.get(round) || [];
  }
}

module.exports = { NarwhalMempoolEngine, TransactionBatch, CertificateOfAvailability };
