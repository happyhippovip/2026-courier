/**
 * Context Window Token Dynamic Bounded Fast Succinct Double-Array Trie Filter
 * Implements a Double-Array Trie (Aoe 1989) using two flat 1D arrays: BASE and CHECK.
 * Guarantees O(1) state transition time per token with cache-friendly contiguous layout.
 */

class DoubleArrayTrieFilter {
  constructor(initialCapacity = 256) {
    this.capacity = initialCapacity;
    this.base = new Int32Array(this.capacity).fill(0);
    this.check = new Int32Array(this.capacity).fill(-1);
    this.values = new Map(); // stateIndex -> value
    this.base[0] = 1; // root state
    this.check[0] = 0;
    this.size = 0;
  }

  _ensureCapacity(neededIndex) {
    if (neededIndex < this.capacity) return;
    let newCap = this.capacity;
    while (newCap <= neededIndex) newCap *= 2;

    const newBase = new Int32Array(newCap).fill(0);
    const newCheck = new Int32Array(newCap).fill(-1);
    newBase.set(this.base);
    newCheck.set(this.check);

    this.base = newBase;
    this.check = newCheck;
    this.capacity = newCap;
  }

  _charToCode(char) {
    return (typeof char === 'number' ? char : String(char).charCodeAt(0)) + 1;
  }

  insert(key, value) {
    const codes = Array.from(key).map(c => this._charToCode(c));
    codes.push(0); // terminal sentinel

    let s = 0; // start at root
    for (let i = 0; i < codes.length; i++) {
      const c = codes[i];
      let t = this.base[s] + c;
      this._ensureCapacity(t);

      if (this.check[t] === -1) {
        // Free slot: occupy
        this.check[t] = s;
        if (this.base[t] === 0) this.base[t] = t + 1;
        s = t;
      } else if (this.check[t] === s) {
        // Already transitions from s
        s = t;
      } else {
        // Collision: conflict resolution by reallocating base[s]
        const oldBase = this.base[s];
        // Find existing branches from s
        const branches = [];
        for (let code = 0; code < 128; code++) {
          const idx = oldBase + code;
          if (idx < this.capacity && this.check[idx] === s) {
            branches.push(code);
          }
        }
        branches.push(c);

        // Find new base for s
        let newBaseCandidate = 1;
        let found = false;
        while (!found) {
          found = true;
          for (const b of branches) {
            const pos = newBaseCandidate + b;
            this._ensureCapacity(pos);
            if (this.check[pos] !== -1 && this.check[pos] !== s) {
              found = false;
              newBaseCandidate++;
              break;
            }
          }
        }

        // Relocate old branches
        for (const b of branches) {
          if (b !== c) {
            const oldPos = oldBase + b;
            const newPos = newBaseCandidate + b;
            this._ensureCapacity(newPos);
            this.base[newPos] = this.base[oldPos];
            this.check[newPos] = s;

            // Relocate children of oldPos
            for (let sub = 0; sub < 128; sub++) {
              const childPos = this.base[oldPos] + sub;
              if (childPos < this.capacity && this.check[childPos] === oldPos) {
                this.check[childPos] = newPos;
              }
            }

            this.base[oldPos] = 0;
            this.check[oldPos] = -1;
          }
        }

        this.base[s] = newBaseCandidate;
        t = newBaseCandidate + c;
        this._ensureCapacity(t);
        this.check[t] = s;
        if (this.base[t] === 0) this.base[t] = t + 1;
        s = t;
      }
    }

    this.values.set(s, value);
    this.size++;
  }

  search(key) {
    const codes = Array.from(key).map(c => this._charToCode(c));
    codes.push(0); // terminal sentinel

    let s = 0;
    for (let i = 0; i < codes.length; i++) {
      const c = codes[i];
      const t = this.base[s] + c;
      if (t >= this.capacity || this.check[t] !== s) {
        return null;
      }
      s = t;
    }
    return this.values.has(s) ? this.values.get(s) : null;
  }

  getMetrics() {
    let occupied = 0;
    for (let i = 0; i < this.capacity; i++) {
      if (this.check[i] !== -1) occupied++;
    }
    return {
      capacity: this.capacity,
      occupiedSlots: occupied,
      loadFactor: Number((occupied / this.capacity).toFixed(4)),
      storedKeys: this.size
    };
  }
}

module.exports = { DoubleArrayTrieFilter };
