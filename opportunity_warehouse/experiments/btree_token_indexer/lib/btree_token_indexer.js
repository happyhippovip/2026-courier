/**
 * Context Window Token B-Tree Range Search & Saliency Indexer
 * Implements a balanced B-Tree (order M=4) indexing tokens by saliency score
 * enabling range queries [sMin, sMax] and sorted token traversal.
 */

class BTreeNode {
  constructor(isLeaf = true) {
    this.isLeaf = isLeaf;
    this.keys = []; // Array of { score, token, position }
    this.children = [];
  }
}

class BTreeTokenIndexer {
  constructor(order = 4) {
    this.order = order;
    this.root = new BTreeNode(true);
    this.totalTokens = 0;
  }

  insert(score, token, position) {
    this.totalTokens++;
    const root = this.root;
    if (root.keys.length === this.order - 1) {
      const newRoot = new BTreeNode(false);
      newRoot.children.push(this.root);
      this.splitChild(newRoot, 0, this.root);
      this.root = newRoot;
    }
    this.insertNonFull(this.root, { score, token, position });
  }

  splitChild(parent, index, child) {
    const mid = Math.floor((this.order - 1) / 2);
    const sibling = new BTreeNode(child.isLeaf);
    const midKey = child.keys[mid];

    sibling.keys = child.keys.slice(mid + 1);
    child.keys = child.keys.slice(0, mid);

    if (!child.isLeaf) {
      sibling.children = child.children.slice(mid + 1);
      child.children = child.children.slice(0, mid + 1);
    }

    parent.children.splice(index + 1, 0, sibling);
    parent.keys.splice(index, 0, midKey);
  }

  insertNonFull(node, entry) {
    let i = node.keys.length - 1;
    if (node.isLeaf) {
      while (i >= 0 && entry.score < node.keys[i].score) {
        i--;
      }
      node.keys.splice(i + 1, 0, entry);
    } else {
      while (i >= 0 && entry.score < node.keys[i].score) {
        i--;
      }
      i++;
      if (node.children[i].keys.length === this.order - 1) {
        this.splitChild(node, i, node.children[i]);
        if (entry.score > node.keys[i].score) {
          i++;
        }
      }
      this.insertNonFull(node.children[i], entry);
    }
  }

  // In-order traversal collecting all entries with score in [sMin, sMax]
  rangeSearch(sMin, sMax) {
    const results = [];
    this.traverseRange(this.root, sMin, sMax, results);
    return results;
  }

  traverseRange(node, sMin, sMax, results) {
    let i = 0;
    while (i < node.keys.length) {
      if (!node.isLeaf && (i === 0 || sMin <= node.keys[i].score)) {
        this.traverseRange(node.children[i], sMin, sMax, results);
      }
      if (node.keys[i].score >= sMin && node.keys[i].score <= sMax) {
        results.push(node.keys[i]);
      }
      i++;
    }
    if (!node.isLeaf) {
      this.traverseRange(node.children[i], sMin, sMax, results);
    }
  }
}

module.exports = { BTreeTokenIndexer, BTreeNode };
