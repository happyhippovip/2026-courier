/**
 * Multi-Agent Distributed Scuttlebutt Gossip Protocol Engine
 * Implements epidemic peer-to-peer reconciliation using per-feed sequence numbers
 * and delta digests for bandwidth-optimal state synchronization.
 */

class ScuttlebuttFeed {
  constructor(feedId) {
    this.feedId = feedId;
    this.messages = []; // Array of { seq, data, timestamp }
  }

  append(data) {
    const seq = this.messages.length + 1;
    const msg = { seq, data, timestamp: Date.now() };
    this.messages.push(msg);
    return msg;
  }

  latestSeq() {
    return this.messages.length;
  }

  getMessagesFrom(seq) {
    return this.messages.filter(m => m.seq > seq);
  }
}

class ScuttlebuttNode {
  constructor(nodeId) {
    this.nodeId = nodeId;
    this.feeds = new Map(); // feedId -> ScuttlebuttFeed
    this.feeds.set(nodeId, new ScuttlebuttFeed(nodeId));
  }

  publish(data) {
    return this.feeds.get(this.nodeId).append(data);
  }

  // Create digest of highest sequence known for each feed
  getDigest() {
    const digest = {};
    for (const [feedId, feed] of this.feeds.entries()) {
      digest[feedId] = feed.latestSeq();
    }
    return digest;
  }

  // Compute messages to send given a peer's digest
  createDelta(peerDigest) {
    const delta = {};
    for (const [feedId, feed] of this.feeds.entries()) {
      const peerSeq = peerDigest[feedId] || 0;
      const msgs = feed.getMessagesFrom(peerSeq);
      if (msgs.length > 0) {
        delta[feedId] = msgs;
      }
    }
    return delta;
  }

  // Apply received delta
  applyDelta(delta) {
    let applied = 0;
    for (const [feedId, msgs] of Object.entries(delta)) {
      if (!this.feeds.has(feedId)) {
        this.feeds.set(feedId, new ScuttlebuttFeed(feedId));
      }
      const feed = this.feeds.get(feedId);
      for (const m of msgs) {
        if (m.seq === feed.latestSeq() + 1) {
          feed.messages.push(m);
          applied++;
        }
      }
    }
    return applied;
  }

  // Full two-way sync
  syncWith(peer) {
    const digA = this.getDigest();
    const deltaForA = peer.createDelta(digA);
    this.applyDelta(deltaForA);

    const digB = peer.getDigest();
    const deltaForB = this.createDelta(digB);
    peer.applyDelta(deltaForB);

    return {
      syncedFeeds: this.feeds.size,
      itemsToA: Object.values(deltaForA).reduce((acc, m) => acc + m.length, 0),
      itemsToB: Object.values(deltaForB).reduce((acc, m) => acc + m.length, 0)
    };
  }
}

module.exports = { ScuttlebuttNode, ScuttlebuttFeed };
