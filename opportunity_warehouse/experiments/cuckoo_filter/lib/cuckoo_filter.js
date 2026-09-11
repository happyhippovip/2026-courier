/**
 * Streaming Context Token Cuckoo Filter & Dynamic Deletion
 * Probabilistic set membership supporting dynamic insertions, lookups, and deletions
 * using Cuckoo Hashing with 1-byte fingerprints and bucket kicks.
 */

class CuckooFilter {
  constructor(numBuckets = 128, bucketSize = 4, maxKicks = 50) {
    this.numBuckets = numBuckets;
    this.bucketSize = bucketSize;
    this.maxKicks = maxKicks;
    this.buckets = Array.from({ length: numBuckets }, () => []);
    this.count = 0;
  }

  hash(str, seed = 0) {
    let h = 0x811c9dc5 ^ seed;
    for (let i = 0; i < str.length; i++) {
      h ^= str.charCodeAt(i);
      h = Math.imul(h, 0x01000193);
    }
    return Math.abs(h);
  }

  fingerprint(str) {
    let fp = (this.hash(str, 12345) % 255) + 1; // 1..255 (non-zero 8-bit)
    return fp;
  }

  getIndices(str, fp) {
    const i1 = this.hash(str, 0) % this.numBuckets;
    const i2 = (i1 ^ (this.hash(fp.toString(), 54321) % this.numBuckets)) % this.numBuckets;
    return [i1, i2];
  }

  insert(item) {
    const fp = this.fingerprint(item);
    const [i1, i2] = this.getIndices(item, fp);

    if (this.buckets[i1].length < this.bucketSize) {
      this.buckets[i1].push(fp);
      this.count++;
      return true;
    }

    if (this.buckets[i2].length < this.bucketSize) {
      this.buckets[i2].push(fp);
      this.count++;
      return true;
    }

    // Must kick an existing fingerprint
    let currIdx = Math.random() < 0.5 ? i1 : i2;
    let currFp = fp;

    for (let kick = 0; kick < this.maxKicks; kick++) {
      const slot = Math.floor(Math.random() * this.bucketSize);
      const kickedFp = this.buckets[currIdx][slot];
      this.buckets[currIdx][slot] = currFp;

      currFp = kickedFp;
      currIdx = (currIdx ^ (this.hash(currFp.toString(), 54321) % this.numBuckets)) % this.numBuckets;

      if (this.buckets[currIdx].length < this.bucketSize) {
        this.buckets[currIdx].push(currFp);
        this.count++;
        return true;
      }
    }

    return false; // Filter is full
  }

  has(item) {
    const fp = this.fingerprint(item);
    const [i1, i2] = this.getIndices(item, fp);
    return this.buckets[i1].includes(fp) || this.buckets[i2].includes(fp);
  }

  delete(item) {
    const fp = this.fingerprint(item);
    const [i1, i2] = this.getIndices(item, fp);

    const idx1 = this.buckets[i1].indexOf(fp);
    if (idx1 !== -1) {
      this.buckets[i1].splice(idx1, 1);
      this.count--;
      return true;
    }

    const idx2 = this.buckets[i2].indexOf(fp);
    if (idx2 !== -1) {
      this.buckets[i2].splice(idx2, 1);
      this.count--;
      return true;
    }

    return false;
  }
}

module.exports = { CuckooFilter };
