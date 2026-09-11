/**
 * Corda-Lite Asynchronous Notary Cluster Engine
 * Implements a Byzantine-fault-tolerant Notary service for stateful UTXO multi-agent systems.
 * Provides deterministic double-spend prevention and atomic consumption certification
 * across distributed notary nodes without requiring global blockchain consensus.
 */

const crypto = require('crypto');

function sha256(data) {
  return crypto.createHash('sha256').update(typeof data === 'string' ? data : JSON.stringify(data)).digest('hex');
}

class StateRef {
  constructor(txHash, index) {
    this.txHash = txHash;
    this.index = index;
    this.id = `${txHash}:${index}`;
  }
}

class NotarizationRequest {
  constructor(txHash, inputs, outputs, timeWindowEnd) {
    this.txHash = txHash;
    this.inputs = inputs; // Array of StateRef
    this.outputs = outputs; // Array of payload objects
    this.timeWindowEnd = timeWindowEnd;
  }
}

class NotaryNode {
  constructor(nodeId) {
    this.nodeId = nodeId;
    // spendRegistry maps stateRefId -> { consumingTxHash, timestamp }
    this.spendRegistry = new Map();
  }

  validateAndSign(request, currentTime) {
    if (currentTime > request.timeWindowEnd) {
      return { status: 'REJECTED', reason: 'TIME_WINDOW_EXPIRED', nodeId: this.nodeId };
    }

    // Check for double-spends
    const conflicts = [];
    for (const ref of request.inputs) {
      if (this.spendRegistry.has(ref.id)) {
        conflicts.push({
          stateRef: ref.id,
          consumedBy: this.spendRegistry.get(ref.id).consumingTxHash
        });
      }
    }

    if (conflicts.length > 0) {
      return {
        status: 'DOUBLE_SPEND_CONFLICT',
        conflicts,
        nodeId: this.nodeId
      };
    }

    // Speculatively sign approval
    const sig = sha256(`${this.nodeId}_notarize_${request.txHash}`);
    return {
      status: 'APPROVED',
      signature: sig,
      nodeId: this.nodeId
    };
  }

  commitSpend(request, currentTime) {
    for (const ref of request.inputs) {
      this.spendRegistry.set(ref.id, {
        consumingTxHash: request.txHash,
        timestamp: currentTime
      });
    }
  }
}

class CordaLiteNotaryCluster {
  constructor(notaryNodeIds, faultTolerance = 1) {
    this.nodeIds = notaryNodeIds; // ['notary_0', 'notary_1', 'notary_2', 'notary_3']
    this.n = notaryNodeIds.length;
    this.f = faultTolerance;
    this.quorum = 2 * this.f + 1; // 3 for n=4

    this.nodes = notaryNodeIds.map(id => new NotaryNode(id));
    this.notarizedCertificates = new Map(); // txHash -> Certificate
  }

  notarizeTransaction(request, currentTime = Date.now()) {
    const approvals = [];
    const conflicts = [];

    for (const node of this.nodes) {
      const res = node.validateAndSign(request, currentTime);
      if (res.status === 'APPROVED') {
        approvals.push(res);
      } else {
        conflicts.push(res);
      }
    }

    // Need 2f+1 approvals to finalize notarization
    if (approvals.length >= this.quorum) {
      // Commit state consumption across all nodes
      for (const node of this.nodes) {
        node.commitSpend(request, currentTime);
      }

      const certificate = {
        txHash: request.txHash,
        timestamp: currentTime,
        consumedInputs: request.inputs.map(r => r.id),
        signatures: approvals.map(a => ({ nodeId: a.nodeId, signature: a.signature })),
        certId: sha256({
          txHash: request.txHash,
          inputs: request.inputs.map(r => r.id).sort(),
          signers: approvals.map(a => a.nodeId).sort()
        })
      };

      this.notarizedCertificates.set(request.txHash, certificate);
      return { success: true, certificate };
    }

    return {
      success: false,
      error: 'QUORUM_REJECTED',
      details: conflicts
    };
  }

  isStateConsumed(stateRefId) {
    return this.nodes[0].spendRegistry.has(stateRefId);
  }
}

module.exports = { CordaLiteNotaryCluster, StateRef, NotarizationRequest };
