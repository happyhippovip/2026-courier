/**
 * Context Window Token Dynamic Bounded Fast Succinct Rank-Pairing Heap Priority Filter
 * Implements a type-1 rank-pairing heap (rp-heap) combining Fibonacci heap efficiency
 * with half-tree structural simplicity for token saliency priority queues.
 */

class RPNode {
  constructor(key, value) {
    this.key = key;
    this.value = value;
    this.rank = 0;
    this.left = null;   // Left child
    this.right = null;  // Right sibling or half-tree spine
    this.parent = null;
  }
}

class RankPairingHeapFilter {
  constructor() {
    this.roots = []; // List of root half-trees
    this.minNode = null;
    this.count = 0;
  }

  insert(key, value) {
    const node = new RPNode(key, value);
    this.roots.push(node);
    if (!this.minNode || node.key < this.minNode.key) {
      this.minNode = node;
    }
    this.count++;
    return node;
  }

  findMin() {
    if (!this.minNode) return null;
    return { key: this.minNode.key, value: this.minNode.value, node: this.minNode };
  }

  _link(r1, r2) {
    // Links two half-trees of rank r into a half-tree of rank r + 1
    if (r1.key > r2.key) {
      const temp = r1;
      r1 = r2;
      r2 = temp;
    }
    // r1 is winner (smaller key)
    r2.right = r1.left;
    if (r1.left) r1.left.parent = r2;
    r1.left = r2;
    r2.parent = r1;
    r1.rank++;
    return r1;
  }

  deleteMin() {
    if (!this.minNode) return null;
    const min = this.minNode;

    // Remove min from roots
    const rootIdx = this.roots.indexOf(min);
    if (rootIdx !== -1) {
      this.roots.splice(rootIdx, 1);
    }

    // Disassemble children of min (spine of half-trees) into roots
    let child = min.left;
    while (child) {
      const nextChild = child.right;
      child.parent = null;
      child.right = null;
      this.roots.push(child);
      child = nextChild;
    }

    this.count--;

    if (this.roots.length === 0) {
      this.minNode = null;
      return { key: min.key, value: min.value };
    }

    // Pairwise consolidation by rank using bucket array
    const maxRank = 64;
    const buckets = new Array(maxRank).fill(null);

    for (let i = 0; i < this.roots.length; i++) {
      let curr = this.roots[i];
      let r = curr.rank;
      while (buckets[r]) {
        curr = this._link(curr, buckets[r]);
        buckets[r] = null;
        r = curr.rank;
      }
      buckets[r] = curr;
    }

    this.roots = [];
    this.minNode = null;
    for (let r = 0; r < maxRank; r++) {
      if (buckets[r]) {
        this.roots.push(buckets[r]);
        if (!this.minNode || buckets[r].key < this.minNode.key) {
          this.minNode = buckets[r];
        }
      }
    }

    return { key: min.key, value: min.value };
  }

  decreaseKey(node, newKey) {
    if (!node || newKey > node.key) {
      throw new Error('New key must be strictly smaller than current key');
    }
    node.key = newKey;

    if (!node.parent) {
      // Already a root
      if (node.key < this.minNode.key) {
        this.minNode = node;
      }
      return;
    }

    // Cut from parent and attach to roots list
    const p = node.parent;
    if (p.left === node) {
      p.left = node.right;
      if (node.right) node.right.parent = p;
    } else if (p.right === node) {
      p.right = node.right;
      if (node.right) node.right.parent = p;
    }

    node.parent = null;
    node.right = null;
    this.roots.push(node);

    if (node.key < this.minNode.key) {
      this.minNode = node;
    }
  }

  extractSorted() {
    const result = [];
    while (this.count > 0) {
      result.push(this.deleteMin());
    }
    return result;
  }

  getMetrics() {
    return {
      elementCount: this.count,
      rootTreesCount: this.roots.length,
      currentMinKey: this.minNode ? this.minNode.key : null,
      amortizedComplexity: 'O(1)_DECREASE_KEY_O_LOG_N_DELETE_MIN'
    };
  }
}

module.exports = { RPNode, RankPairingHeapFilter };
