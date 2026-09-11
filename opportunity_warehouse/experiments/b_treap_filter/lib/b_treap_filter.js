/**
 * B-Treap Priority Search Filter
 * Implements a multi-way balanced Cartesian Treap (B-Treap).
 * Each node stores up to 2B items ordered by search key, while tracking
 * the maximum priority in its subtree for output-sensitive range priority queries.
 */

class BTreapItem {
  constructor(key, priority, data = null) {
    this.key = key;
    this.priority = priority;
    this.data = data;
  }
}

class BTreapNode {
  constructor(isLeaf = true) {
    this.isLeaf = isLeaf;
    this.items = [];
    this.children = [];
    this.maxSubtreePriority = -Infinity;
  }

  updateMaxPriority() {
    let maxP = -Infinity;
    for (const item of this.items) {
      if (item.priority > maxP) maxP = item.priority;
    }
    for (const child of this.children) {
      if (child.maxSubtreePriority > maxP) maxP = child.maxSubtreePriority;
    }
    this.maxSubtreePriority = maxP;
  }
}

class BTreapFilter {
  constructor(B = 2) {
    this.B = B;
    this.maxItems = 2 * B;
    this.root = new BTreapNode(true);
    this.size = 0;
  }

  insert(key, priority, data = null) {
    const item = new BTreapItem(key, priority, data);
    const r = this.root;

    if (r.items.length === this.maxItems) {
      const newRoot = new BTreapNode(false);
      newRoot.children.push(this.root);
      this._splitChild(newRoot, 0, this.root);
      this.root = newRoot;
    }

    this._insertNonFull(this.root, item);
    this.size++;
  }

  _insertNonFull(node, item) {
    let i = node.items.length - 1;

    if (node.isLeaf) {
      while (i >= 0 && node.items[i].key > item.key) {
        i--;
      }
      node.items.splice(i + 1, 0, item);
      node.updateMaxPriority();
    } else {
      while (i >= 0 && node.items[i].key > item.key) {
        i--;
      }
      i++;
      if (node.children[i].items.length === this.maxItems) {
        this._splitChild(node, i, node.children[i]);
        if (item.key > node.items[i].key) {
          i++;
        }
      }
      this._insertNonFull(node.children[i], item);
      node.updateMaxPriority();
    }
  }

  _splitChild(parent, index, child) {
    const midIdx = this.B;
    const medianItem = child.items[midIdx];

    const newNode = new BTreapNode(child.isLeaf);
    newNode.items = child.items.splice(midIdx + 1);

    if (!child.isLeaf) {
      newNode.children = child.children.splice(midIdx + 1);
    }

    child.items.pop();
    child.updateMaxPriority();
    newNode.updateMaxPriority();

    parent.children.splice(index + 1, 0, newNode);
    parent.items.splice(index, 0, medianItem);
    parent.updateMaxPriority();
  }

  rangePriorityQuery(lowKey, highKey, minPriority = -Infinity) {
    const results = [];
    this._search(this.root, lowKey, highKey, minPriority, results);
    return results.sort((a, b) => b.priority - a.priority);
  }

  _search(node, lowKey, highKey, minPriority, results) {
    if (!node || node.maxSubtreePriority < minPriority) {
      return;
    }

    let i = 0;
    while (i < node.items.length && node.items[i].key < lowKey) {
      i++;
    }

    if (!node.isLeaf) {
      this._search(node.children[i], lowKey, highKey, minPriority, results);
    }

    while (i < node.items.length && node.items[i].key <= highKey) {
      if (node.items[i].priority >= minPriority) {
        results.push(node.items[i]);
      }
      if (!node.isLeaf) {
        this._search(node.children[i + 1], lowKey, highKey, minPriority, results);
      }
      i++;
    }
  }

  getMaxPriorityInRange(lowKey, highKey) {
    const items = this.rangePriorityQuery(lowKey, highKey);
    return items.length > 0 ? items[0].priority : null;
  }
}

module.exports = { BTreapFilter, BTreapNode, BTreapItem };
