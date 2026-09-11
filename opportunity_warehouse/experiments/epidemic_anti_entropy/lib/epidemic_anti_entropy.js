/**
 * Multi-Agent Distributed Epidemic Anti-Entropy Sync Engine
 * Implements Scuttlebutt / Merkle digest reconciliation for eventual consistency
 * across distributed agent caches with delta-only transmission.
 */

class AntiEntropyNode {
  constructor(nodeId) {
    this.nodeId = nodeId;
    this.store = new Map(); // key -> { value, version, origin }
    this.maxVersion = 0;
  }

  put(key, value) {
    this.maxVersion++;
    this.store.set(key, { value, version: this.maxVersion, origin: this.nodeId });
  }

  get(key) {
    const entry = this.store.get(key);
    return entry ? entry.value : null;
  }

  // Generate digest of highest version known for each key
  getDigest() {
    const digest = {};
    for (const [key, entry] of this.store.entries()) {
      digest[key] = entry.version;
    }
    return digest;
  }

  // Compare incoming peer digest and compute delta (entries peer needs)
  computeDelta(peerDigest) {
    const delta = [];
    for (const [key, entry] of this.store.entries()) {
      const peerVersion = peerDigest[key] || 0;
      if (entry.version > peerVersion) {
        delta.push({ key, ...entry });
      }
    }
    return delta;
  }

  // Apply received delta from peer
  applyDelta(delta) {
    let appliedCount = 0;
    for (const item of delta) {
      const current = this.store.get(item.key);
      if (!current || item.version > current.version) {
        this.store.set(item.key, {
          value: item.value,
          version: item.version,
          origin: item.origin
        });
        if (item.version > this.maxVersion) {
          this.maxVersion = item.version;
        }
        appliedCount++;
      }
    }
    return appliedCount;
  }

  // Perform full anti-entropy sync turn with peer
  syncWith(peer) {
    // 1. Peer A sends digest to Peer B; B sends delta to A
    const digestA = this.getDigest();
    const deltaFromB = peer.computeDelta(digestA);
    this.applyDelta(deltaFromB);

    // 2. Peer B sends digest to Peer A; A sends delta to B
    const digestB = peer.getDigest();
    const deltaFromA = this.computeDelta(digestB);
    peer.applyDelta(deltaFromA);

    return {
      syncedKeys: this.store.size,
      itemsToA: deltaFromB.length,
      itemsToB: deltaFromA.length
    };
  }
}

module.exports = { AntiEntropyNode };
