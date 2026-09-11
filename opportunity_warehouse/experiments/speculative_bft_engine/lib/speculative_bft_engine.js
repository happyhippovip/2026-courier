/**
 * Speculative BFT Consensus Engine
 * Implements optimistic fast-path BFT consensus (Zyzzyva-style).
 * In the optimistic fault-free path, replicas speculatively execute and return responses directly.
 * - 3f+1 unanimous matching responses -> FAST-PATH COMMIT in 1 network round-trip (1 Delta).
 * - 2f+1 matching responses -> TWO-PHASE FALLBACK COMMIT in 2 round-trips.
 */

const crypto = require('crypto');

function sha256(data) {
  return crypto.createHash('sha256').update(typeof data === 'string' ? data : JSON.stringify(data)).digest('hex');
}

class ReplicaNode {
  constructor(nodeId, view = 1) {
    this.nodeId = nodeId;
    this.view = view;
    this.history = []; // Array of executed requests
    this.state = {};
  }

  speculativelyExecute(orderRequest) {
    // Execute state transition
    if (orderRequest.type === 'SET') {
      this.state[orderRequest.key] = orderRequest.value;
    }

    const stateDigest = sha256(this.state);
    const specResponse = {
      view: this.view,
      seq: orderRequest.seq,
      stateDigest,
      nodeId: this.nodeId,
      sig: sha256(`${this.nodeId}_spec_${this.view}_${orderRequest.seq}_${stateDigest}`)
    };

    this.history.push({ request: orderRequest, specResponse });
    return specResponse;
  }
}

class SpeculativeBFTEngine {
  constructor(replicas, faultTolerance = 1) {
    this.replicas = replicas; // ['r0', 'r1', 'r2', 'r3']
    this.n = replicas.length;
    this.f = faultTolerance;
    this.unanimousQuorum = 3 * this.f + 1; // 4 for f=1 (Fast Path)
    this.standardQuorum = 2 * this.f + 1; // 3 for f=1 (Two-Phase Path)

    this.nodes = replicas.map(id => new ReplicaNode(id));
    this.committedRequests = [];
    this.currentSeq = 1;
  }

  submitRequest(key, value) {
    const orderRequest = {
      seq: this.currentSeq++,
      key,
      value,
      timestamp: Date.now()
    };

    const responses = [];
    for (const node of this.nodes) {
      const res = node.speculativelyExecute(orderRequest);
      responses.push(res);
    }

    // Check if unanimous (3f+1) matching responses
    const firstDigest = responses[0].stateDigest;
    const matchingFastPath = responses.filter(r => r.stateDigest === firstDigest);

    if (matchingFastPath.length >= this.unanimousQuorum) {
      // FAST-PATH COMMIT! (1 RTT)
      const commitRecord = {
        path: 'FAST_PATH_UNANIMOUS',
        latencyRTT: 1,
        seq: orderRequest.seq,
        key,
        value,
        matchingResponses: matchingFastPath.length,
        certificate: sha256(matchingFastPath.map(r => r.sig).sort())
      };
      this.committedRequests.push(commitRecord);
      return { success: true, commitRecord };
    }

    // Check if standard quorum (2f+1) matching responses
    if (matchingFastPath.length >= this.standardQuorum) {
      // TWO-PHASE FALLBACK COMMIT (2 RTT)
      const commitRecord = {
        path: 'TWO_PHASE_FALLBACK',
        latencyRTT: 2,
        seq: orderRequest.seq,
        key,
        value,
        matchingResponses: matchingFastPath.length,
        certificate: sha256(matchingFastPath.slice(0, this.standardQuorum).map(r => r.sig).sort())
      };
      this.committedRequests.push(commitRecord);
      return { success: true, commitRecord };
    }

    return { success: false, reason: 'QUORUM_FAILED' };
  }

  getCommittedRequests() {
    return this.committedRequests;
  }
}

module.exports = { SpeculativeBFTEngine, ReplicaNode };
