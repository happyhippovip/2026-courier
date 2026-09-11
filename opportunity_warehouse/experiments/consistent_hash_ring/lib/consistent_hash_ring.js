/**
 * Multi-Agent Distributed Consistent Hash Ring & Partition Rebalancer
 * Distributes context partitions across a cluster of agent nodes using virtual replicas
 * and minimizes partition reassignment churn upon node topology changes.
 */

const crypto = require('crypto');

class ConsistentHashRing {
  constructor(replicas = 32) {
    this.replicas = replicas;
    this.ring = []; // Array of { hash, nodeId }
    this.nodes = new Set();
  }

  hash(key) {
    const hashHex = crypto.createHash('sha256').update(key).digest('hex');
    return parseInt(hashHex.substring(0, 8), 16);
  }

  addNode(nodeId) {
    this.nodes.add(nodeId);
    for (let i = 0; i < this.replicas; i++) {
      const vNodeKey = nodeId + '#vnode-' + i;
      const vNodeHash = this.hash(vNodeKey);
      this.ring.push({ hash: vNodeHash, nodeId });
    }
    this.ring.sort((a, b) => a.hash - b.hash);
  }

  removeNode(nodeId) {
    this.nodes.delete(nodeId);
    this.ring = this.ring.filter(item => item.nodeId !== nodeId);
  }

  getNode(key) {
    if (this.ring.length === 0) return null;
    const h = this.hash(key);

    // Binary search for first node with hash >= h
    let low = 0;
    let high = this.ring.length - 1;
    while (low <= high) {
      const mid = Math.floor((low + high) / 2);
      if (this.ring[mid].hash >= h) {
        high = mid - 1;
      } else {
        low = mid + 1;
      }
    }

    const index = (low < this.ring.length) ? low : 0;
    return this.ring[index].nodeId;
  }
}

module.exports = { ConsistentHashRing };
