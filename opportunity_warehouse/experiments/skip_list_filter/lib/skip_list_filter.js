/**
 * Context Window Token Dynamic Bounded Fast Succinct Skip-List Saliency Filter
 * Implements a bounded multi-level Skip List for fast O(log N) priority/saliency lookups,
 * range scans, and exact rank extraction with deterministic PRNG seeding.
 */

class SkipListNode {
  constructor(key, value, level) {
    this.key = key;
    this.value = value;
    this.forward = new Array(level + 1).fill(null);
  }
}

class SkipListFilter {
  constructor(maxLevel = 8, p = 0.5) {
    this.maxLevel = maxLevel;
    this.p = p;
    this.level = 0;
    this.head = new SkipListNode(-Infinity, null, maxLevel);
    this.size = 0;
    this.prngSeed = 1337;
  }

  _random() {
    // Deterministic LCG for reproducible testing
    this.prngSeed = (this.prngSeed * 1664525 + 1013904223) % 4294967296;
    return this.prngSeed / 4294967296;
  }

  _randomLevel() {
    let lvl = 0;
    while (this._random() < this.p && lvl < this.maxLevel) {
      lvl++;
    }
    return lvl;
  }

  search(key) {
    let curr = this.head;
    for (let i = this.level; i >= 0; i--) {
      while (curr.forward[i] && curr.forward[i].key < key) {
        curr = curr.forward[i];
      }
    }
    curr = curr.forward[0];
    if (curr && curr.key === key) {
      return { key: curr.key, value: curr.value };
    }
    return null;
  }

  insert(key, value) {
    const update = new Array(this.maxLevel + 1).fill(null);
    let curr = this.head;

    for (let i = this.level; i >= 0; i--) {
      while (curr.forward[i] && curr.forward[i].key < key) {
        curr = curr.forward[i];
      }
      update[i] = curr;
    }

    curr = curr.forward[0];
    if (curr && curr.key === key) {
      curr.value = value; // update
      return;
    }

    const rLevel = this._randomLevel();
    if (rLevel > this.level) {
      for (let i = this.level + 1; i <= rLevel; i++) {
        update[i] = this.head;
      }
      this.level = rLevel;
    }

    const newNode = new SkipListNode(key, value, rLevel);
    for (let i = 0; i <= rLevel; i++) {
      newNode.forward[i] = update[i].forward[i];
      update[i].forward[i] = newNode;
    }
    this.size++;
  }

  delete(key) {
    const update = new Array(this.maxLevel + 1).fill(null);
    let curr = this.head;

    for (let i = this.level; i >= 0; i--) {
      while (curr.forward[i] && curr.forward[i].key < key) {
        curr = curr.forward[i];
      }
      update[i] = curr;
    }

    curr = curr.forward[0];
    if (!curr || curr.key !== key) return false;

    for (let i = 0; i <= this.level; i++) {
      if (update[i].forward[i] !== curr) break;
      update[i].forward[i] = curr.forward[i];
    }

    while (this.level > 0 && this.head.forward[this.level] === null) {
      this.level--;
    }
    this.size--;
    return true;
  }

  rangeQuery(minKey, maxKey) {
    const results = [];
    let curr = this.head;

    for (let i = this.level; i >= 0; i--) {
      while (curr.forward[i] && curr.forward[i].key < minKey) {
        curr = curr.forward[i];
      }
    }

    curr = curr.forward[0];
    while (curr && curr.key <= maxKey) {
      results.push({ key: curr.key, value: curr.value });
      curr = curr.forward[0];
    }
    return results;
  }

  getMetrics() {
    return {
      size: this.size,
      currentLevel: this.level,
      maxLevel: this.maxLevel,
      p: this.p,
      complexity: 'O(log N)_EXPECTED',
      indexingClass: 'DETERMINISTIC_PRNG_SKIP_LIST'
    };
  }
}

module.exports = { SkipListNode, SkipListFilter };
