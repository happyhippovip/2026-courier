/**
 * Multi-Agent Distributed Hash Table (Kademlia DHT) Routing Engine
 * Implements XOR metric distance routing, k-buckets, and node lookup
 * for decentralized multi-agent context key-value discovery with O(log N) hops.
 */

class KademliaNode {
  constructor(nodeIdHex, k = 4) {
    this.nodeIdHex = nodeIdHex;
    this.nodeIdInt = parseInt(nodeIdHex, 16);
    this.k = k;
    this.buckets = Array.from({ length: 16 }, () => []); // 16-bit space for simulation
    this.storage = new Map();
  }

  // XOR distance metric
  distance(otherIdHex) {
    const otherInt = parseInt(otherIdHex, 16);
    return this.nodeIdInt ^ otherInt;
  }

  // Determine bucket index (leading zeros of XOR distance)
  getBucketIndex(distance) {
    if (distance === 0) return 0;
    return Math.min(15, Math.floor(Math.log2(distance)));
  }

  // Add contact to routing table
  addContact(contactIdHex) {
    if (contactIdHex === this.nodeIdHex) return;
    const dist = this.distance(contactIdHex);
    const bIdx = this.getBucketIndex(dist);
    const bucket = this.buckets[bIdx];

    const existingIdx = bucket.indexOf(contactIdHex);
    if (existingIdx !== -1) {
      // Move to tail (most recently seen)
      bucket.splice(existingIdx, 1);
      bucket.push(contactIdHex);
    } else if (bucket.length < this.k) {
      bucket.push(contactIdHex);
    }
  }

  // Find k closest contacts to target key
  findClosestNodes(targetKeyHex) {
    const allContacts = [];
    for (const b of this.buckets) {
      allContacts.push(...b);
    }

    allContacts.sort((a, b) => {
      const distA = parseInt(a, 16) ^ parseInt(targetKeyHex, 16);
      const distB = parseInt(b, 16) ^ parseInt(targetKeyHex, 16);
      return distA - distB;
    });

    return allContacts.slice(0, this.k);
  }

  // Store key-value in local DHT slice
  putValue(key, value) {
    this.storage.set(key, value);
  }

  getValue(key) {
    return this.storage.get(key) || null;
  }
}

module.exports = { KademliaNode };
