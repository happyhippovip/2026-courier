/**
 * Context Window Token Dynamic Bounded Fast Succinct 2-3-4 Tree Filter
 * Implements a balanced 2-3-4 Tree (order-4 B-Tree) where nodes hold 1, 2, or 3 keys,
 * guaranteeing strict O(log N) worst-case height and deterministic range reporting.
 */

class TTFNode {
  constructor(keys = [], values = [], children = []) {
    this.keys = keys.slice();
    this.values = values.slice();
    this.children = children.slice(); // empty for leaf
  }

  isLeaf() {
    return this.children.length === 0;
  }
}

class TwoThreeFourTreeFilter {
  constructor() {
    this.root = new TTFNode();
    this.size = 0;
  }

  search(key, node = this.root) {
    if (!node) return null;

    let i = 0;
    while (i < node.keys.length && key > node.keys[i]) {
      i++;
    }

    if (i < node.keys.length && key === node.keys[i]) {
      return { key: node.keys[i], value: node.values[i] };
    }

    if (node.isLeaf()) return null;
    return this.search(key, node.children[i]);
  }

  insert(key, value) {
    // If root is full (3 keys), split root first (top-down 2-3-4 insertion)
    if (this.root.keys.length === 3) {
      const [leftNode, midKey, midVal, rightNode] = this._splitFullNode(this.root);
      this.root = new TTFNode([midKey], [midVal], [leftNode, rightNode]);
    }

    this._insertNonFull(this.root, key, value);
    this.size++;
  }

  _splitFullNode(node) {
    const leftNode = new TTFNode(
      [node.keys[0]],
      [node.values[0]],
      node.isLeaf() ? [] : [node.children[0], node.children[1]]
    );
    const midKey = node.keys[1];
    const midVal = node.values[1];
    const rightNode = new TTFNode(
      [node.keys[2]],
      [node.values[2]],
      node.isLeaf() ? [] : [node.children[2], node.children[3]]
    );
    return [leftNode, midKey, midVal, rightNode];
  }

  _insertNonFull(node, key, value) {
    let i = node.keys.length - 1;

    if (node.isLeaf()) {
      while (i >= 0 && key < node.keys[i]) {
        i--;
      }
      if (i >= 0 && node.keys[i] === key) {
        node.values[i] = value; // update
        return;
      }
      node.keys.splice(i + 1, 0, key);
      node.values.splice(i + 1, 0, value);
    } else {
      while (i >= 0 && key < node.keys[i]) {
        i--;
      }
      i++;

      // If child is full, split child before descending
      if (node.children[i].keys.length === 3) {
        const [leftNode, midKey, midVal, rightNode] = this._splitFullNode(node.children[i]);
        node.keys.splice(i, 0, midKey);
        node.values.splice(i, 0, midVal);
        node.children.splice(i, 1, leftNode, rightNode);

        if (key > midKey) {
          i++;
        }
      }

      this._insertNonFull(node.children[i], key, value);
    }
  }

  rangeQuery(minKey, maxKey, node = this.root) {
    const results = [];
    function traverse(curr) {
      if (!curr) return;
      let i = 0;
      for (i = 0; i < curr.keys.length; i++) {
        if (!curr.isLeaf() && curr.keys[i] >= minKey) {
          traverse(curr.children[i]);
        }
        if (curr.keys[i] >= minKey && curr.keys[i] <= maxKey) {
          results.push({ key: curr.keys[i], value: curr.values[i] });
        }
      }
      if (!curr.isLeaf() && (curr.keys.length === 0 || curr.keys[curr.keys.length - 1] <= maxKey)) {
        traverse(curr.children[curr.children.length - 1]);
      }
    }
    traverse(node);
    return results;
  }

  getMetrics() {
    return {
      size: this.size,
      maxKeysPerNode: 3,
      branchingFactor: 4,
      complexity: 'O(log N)_WORST_CASE_STRICT',
      balancingInvariant: 'PERFECT_HEIGHT_EQUILIBRIUM_2_3_4'
    };
  }
}

module.exports = { TTFNode, TwoThreeFourTreeFilter };
