/**
 * Context Window Token 2D KD-Tree Partitioner
 * Partitions tokens in 2D space: Dim 0 = Recency (position), Dim 1 = Saliency (score)
 * enabling orthogonal 2D bounding box searches and nearest-neighbor context retrieval.
 */

class KDNode {
  constructor(point, token, axis = 0) {
    this.point = point; // [recency, saliency]
    this.token = token;
    this.axis = axis;   // 0 (recency) or 1 (saliency)
    this.left = null;
    this.right = null;
  }
}

class KDTreeContextPartitioner {
  constructor() {
    this.root = null;
    this.size = 0;
  }

  insert(point, token) {
    this.root = this.insertNode(this.root, point, token, 0);
    this.size++;
  }

  insertNode(node, point, token, depth) {
    if (!node) {
      return new KDNode(point, token, depth % 2);
    }

    const axis = depth % 2;
    if (point[axis] < node.point[axis]) {
      node.left = this.insertNode(node.left, point, token, depth + 1);
    } else {
      node.right = this.insertNode(node.right, point, token, depth + 1);
    }

    return node;
  }

  // 2D Range Search: point[0] in [rMin, rMax] and point[1] in [sMin, sMax]
  rangeSearch(rMin, rMax, sMin, sMax) {
    const results = [];
    this.searchRange(this.root, rMin, rMax, sMin, sMax, results);
    return results;
  }

  searchRange(node, rMin, rMax, sMin, sMax, results) {
    if (!node) return;

    const [r, s] = node.point;
    if (r >= rMin && r <= rMax && s >= sMin && s <= sMax) {
      results.push({ point: node.point, token: node.token });
    }

    const axis = node.axis;
    const minVal = axis === 0 ? rMin : sMin;
    const maxVal = axis === 0 ? rMax : sMax;

    if (minVal <= node.point[axis]) {
      this.searchRange(node.left, rMin, rMax, sMin, sMax, results);
    }
    if (maxVal >= node.point[axis]) {
      this.searchRange(node.right, rMin, rMax, sMin, sMax, results);
    }
  }
}

module.exports = { KDTreeContextPartitioner, KDNode };
