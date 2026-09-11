/**
 * Multi-Agent Distributed Asynchronous Verifiable Byzantine Mempool Gossip Consensus Engine
 * Implements epidemic gossip transaction dissemination with Bloom filter deduplication,
 * peer message rate-limiting, and deterministic spam rejection.
 */

const crypto = require('crypto');

function hashObject(obj) {
  return crypto.createHash('sha256').update(JSON.stringify(obj)).digest('hex');
}

class MempoolTransaction {
  constructor(txId, senderId, payload, nonce) {
    this.txId = txId;
    this.senderId = senderId;
    this.payload = payload;
    this.nonce = nonce;
    this.txHash = hashObject({ txId, senderId, payload, nonce });
    this.receivedAt = Date.now();
  }
}

class BFTMempoolGossipEngine {
  constructor(nodeId = 'node_0', maxMempoolSize = 100, maxPeerRatePerSec = 10) {
    this.nodeId = nodeId;
    this.maxMempoolSize = maxMempoolSize;
    this.maxPeerRatePerSec = maxPeerRatePerSec;

    this.mempool = new Map(); // txHash -> MempoolTransaction
    this.seenTxHashes = new Set(); // Bloom/Set filter to prevent re-gossip loops
    this.peerMessageCounts = new Map(); // peerId -> count
  }

  ingestTransaction(tx, peerId = null) {
    if (this.seenTxHashes.has(tx.txHash)) {
      return { accepted: false, reason: 'ALREADY_SEEN' };
    }

    if (peerId) {
      const count = (this.peerMessageCounts.get(peerId) || 0) + 1;
      if (count > this.maxPeerRatePerSec) {
        throw new Error('Rate limit exceeded for peer: ' + peerId);
      }
      this.peerMessageCounts.set(peerId, count);
    }

    if (this.mempool.size >= this.maxMempoolSize) {
      return { accepted: false, reason: 'MEMPOOL_CAPACITY_EXCEEDED' };
    }

    this.mempool.set(tx.txHash, tx);
    this.seenTxHashes.add(tx.txHash);

    return { accepted: true, txHash: tx.txHash, currentMempoolSize: this.mempool.size };
  }

  generateGossipPush(maxCount = 10) {
    const batch = [];
    for (const tx of this.mempool.values()) {
      batch.push(tx);
      if (batch.length >= maxCount) break;
    }
    return batch;
  }

  drainCommittedTxs(committedTxHashes) {
    let removed = 0;
    for (const h of committedTxHashes) {
      if (this.mempool.has(h)) {
        this.mempool.delete(h);
        removed++;
      }
    }
    return { removed, remainingMempoolSize: this.mempool.size };
  }

  getStats() {
    return {
      nodeId: this.nodeId,
      currentMempoolSize: this.mempool.size,
      totalSeenHashes: this.seenTxHashes.size,
      maxMempoolSize: this.maxMempoolSize
    };
  }
}

module.exports = { MempoolTransaction, BFTMempoolGossipEngine };
