/**
 * Context Window Token Cuckoo Hashing Evaluator
 * High-performance hash table guaranteeing strictly O(1) worst-case lookup and deletion.
 * Uses dual hash tables T1 and T2 with eviction chains (cuckoo displacement) and max displacement bounds.
 */

const crypto = require('crypto');

class CuckooHashTable {
  constructor(tableSize = 128, maxDisplacements = 32) {
    this.tableSize = tableSize;
    this.maxDisplacements = maxDisplacements;
    this.t1 = new Array(tableSize).fill(null);
    this.t2 = new Array(tableSize).fill(null);
    this.size = 0;
  }

  _h1(key) {
    const h = crypto.createHash('sha256').update('h1_' + key).digest();
    const val = (h[0] | (h[1] << 8) | (h[2] << 16) | (h[3] << 24)) >>> 0;
    return val % this.tableSize;
  }

  _h2(key) {
    const h = crypto.createHash('sha256').update('h2_' + key).digest();
    const val = (h[0] | (h[1] << 8) | (h[2] << 16) | (h[3] << 24)) >>> 0;
    return val % this.tableSize;
  }

  lookup(key) {
    const idx1 = this._h1(key);
    if (this.t1[idx1] && this.t1[idx1].key === key) {
      return this.t1[idx1].value;
    }
    const idx2 = this._h2(key);
    if (this.t2[idx2] && this.t2[idx2].key === key) {
      return this.t2[idx2].value;
    }
    return null;
  }

  contains(key) {
    return this.lookup(key) !== null;
  }

  insert(key, value) {
    // If key already exists, update in-place
    const idx1 = this._h1(key);
    if (this.t1[idx1] && this.t1[idx1].key === key) {
      this.t1[idx1].value = value;
      return;
    }
    const idx2 = this._h2(key);
    if (this.t2[idx2] && this.t2[idx2].key === key) {
      this.t2[idx2].value = value;
      return;
    }

    let currentItem = { key, value };
    let currentTable = 1;

    for (let count = 0; count < this.maxDisplacements; count++) {
      if (currentTable === 1) {
        const pos = this._h1(currentItem.key);
        if (this.t1[pos] === null) {
          this.t1[pos] = currentItem;
          this.size++;
          return;
        }
        // Evict existing item in T1
        const temp = this.t1[pos];
        this.t1[pos] = currentItem;
        currentItem = temp;
        currentTable = 2;
      } else {
        const pos = this._h2(currentItem.key);
        if (this.t2[pos] === null) {
          this.t2[pos] = currentItem;
          this.size++;
          return;
        }
        // Evict existing item in T2
        const temp = this.t2[pos];
        this.t2[pos] = currentItem;
        currentItem = temp;
        currentTable = 1;
      }
    }

    throw new Error('Cuckoo cycle detected: displacement bound exceeded, table rehash required');
  }

  delete(key) {
    const idx1 = this._h1(key);
    if (this.t1[idx1] && this.t1[idx1].key === key) {
      this.t1[idx1] = null;
      this.size--;
      return true;
    }
    const idx2 = this._h2(key);
    if (this.t2[idx2] && this.t2[idx2].key === key) {
      this.t2[idx2] = null;
      this.size--;
      return true;
    }
    return false;
  }
}

module.exports = { CuckooHashTable };
