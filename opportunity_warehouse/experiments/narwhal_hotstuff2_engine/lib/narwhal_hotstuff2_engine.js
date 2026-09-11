/**
 * Narwhal-HotStuff-2 Hybrid Consensus Engine
 * Decouples mempool data dissemination (Narwhal DAG) from consensus sequencing (HotStuff-2).
 * Narwhal guarantees Data Availability through Certificate of Availability (CoA) DAGs.
 * HotStuff-2 linearly sequences CoAs with optimal 2-chain responsiveness and minimal latency.
 */

const crypto = require('crypto');

function sha256(data) {
  return crypto.createHash('sha256').update(typeof data === 'string' ? data : JSON.stringify(data)).digest('hex');
}

class NarwhalBatch {
  constructor(author, round, previousCertificateIds, transactions) {
    this.author = author;
    this.round = round;
    this.previousCertificateIds = previousCertificateIds; // Causal DAG dependencies
    this.transactions = transactions;
    this.digest = sha256({
      author,
      round,
      prev: previousCertificateIds.sort(),
      txs: transactions
    });
  }
}

class CertificateOfAvailability {
  constructor(batch, signatures) {
    this.batch = batch;
    this.signatures = signatures; // Quorum 2f+1 signatures from validators
    this.id = sha256({
      batchDigest: batch.digest,
      round: batch.round,
      signers: Object.keys(signatures).sort()
    });
  }
}

class HotStuff2Block {
  constructor(proposer, view, justifyQcId, batchCertificates) {
    this.proposer = proposer;
    this.view = view;
    this.justifyQcId = justifyQcId;
    this.batchCertificates = batchCertificates; // Array of Narwhal CertificateOfAvailability
    this.hash = sha256({
      proposer,
      view,
      justifyQcId,
      certs: batchCertificates.map(c => c.id)
    });
  }
}

class NarwhalHotStuff2Engine {
  constructor(validators, faultTolerance = 1) {
    this.validators = validators; // ['val_0', 'val_1', 'val_2', 'val_3']
    this.n = validators.length;
    this.f = faultTolerance;
    this.quorum = 2 * this.f + 1;

    // Narwhal DAG state
    this.certificates = new Map(); // certId -> CertificateOfAvailability
    this.roundCertificates = new Map(); // round -> certId[]

    // HotStuff-2 Consensus state
    this.currentView = 1;
    this.blocks = new Map(); // blockHash -> HotStuff2Block
    this.highQC = { blockHash: 'GENESIS', view: 0, qcId: 'GENESIS_QC' };
    this.committedBlocks = [];
    this.orderedTransactions = [];
  }

  // --- Narwhal Layer: Disseminate and Certify ---
  createBatchAndCertificate(author, round, prevCertIds, transactions) {
    const batch = new NarwhalBatch(author, round, prevCertIds, transactions);
    
    // Simulate quorum collection (2f+1 signatures)
    const signatures = {};
    for (let i = 0; i < this.quorum; i++) {
      const val = this.validators[i];
      signatures[val] = sha256(`${val}_sig_${batch.digest}`);
    }

    const cert = new CertificateOfAvailability(batch, signatures);
    this.certificates.set(cert.id, cert);

    if (!this.roundCertificates.has(round)) {
      this.roundCertificates.set(round, []);
    }
    this.roundCertificates.get(round).push(cert.id);

    return cert;
  }

  // --- HotStuff-2 Layer: Propose and Vote ---
  propose(proposer, batchCertificates) {
    const block = new HotStuff2Block(proposer, this.currentView, this.highQC.qcId, batchCertificates);
    this.blocks.set(block.hash, block);
    return block;
  }

  voteAndCreateQC(blockHash) {
    const block = this.blocks.get(blockHash);
    if (!block) throw new Error('Block not found: ' + blockHash);

    const signatures = {};
    for (let i = 0; i < this.quorum; i++) {
      const val = this.validators[i];
      signatures[val] = sha256(`${val}_vote_${blockHash}`);
    }

    const qc = {
      blockHash,
      view: block.view,
      qcId: sha256({ blockHash, view: block.view, signers: Object.keys(signatures).sort() })
    };

    // HotStuff-2 2-chain rule:
    // If this block's justifyQc points to an uncommitted block, commit it!
    if (block.justifyQcId && block.justifyQcId !== 'GENESIS_QC') {
      // Find parent block
      for (const [hash, b] of this.blocks.entries()) {
        const potentialQcId = sha256({ blockHash: hash, view: b.view, signers: Object.keys(signatures).sort() });
        // Match parent
        if (b.view === block.view - 1 && !this.committedBlocks.includes(b)) {
          this.commitBlock(b);
          break;
        }
      }
    }

    this.highQC = qc;
    this.currentView++;
    return qc;
  }

  commitBlock(block) {
    this.committedBlocks.push(block);
    // Linearize causal history of certificates in topological order
    for (const cert of block.batchCertificates) {
      this.linearizeCertificate(cert);
    }
  }

  linearizeCertificate(cert) {
    // DFS / causal past resolution
    for (const prevId of cert.batch.previousCertificateIds) {
      const prevCert = this.certificates.get(prevId);
      if (prevCert && !prevCert.linearized) {
        this.linearizeCertificate(prevCert);
      }
    }

    if (!cert.linearized) {
      cert.linearized = true;
      this.orderedTransactions.push(...cert.batch.transactions);
    }
  }

  getOrderedTransactions() {
    return this.orderedTransactions;
  }
}

module.exports = { NarwhalHotStuff2Engine, NarwhalBatch, CertificateOfAvailability, HotStuff2Block };
