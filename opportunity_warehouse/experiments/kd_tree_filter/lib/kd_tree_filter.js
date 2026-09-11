/**
 * Context Window Token Dynamic Bounded Fast Succinct 2D KD-Tree Orthogonal Spatial Filter
 * Implements a 2-dimensional KD-Tree for indexing (token_index, embedding_proj) points
 * with cycling dimension splits, orthogonal bounding box queries, and nearest neighbor search.
 */

class KDNode {
  constructor(point, left = null, right = null, axis = 0) {
    this.point = point; // [x, y, data]
    this.left = left;
    this.right = right;
    this.axis = axis;
  }
}

class KDTreeFilter {
  constructor() {
    this.root = null;
    this.size = 0;
  }

  build(points) {
    this.size = points.length;
    this.root = this._buildRecursive(points.slice(), 0);
  }

  _buildRecursive(pts, depth) {
    if (!pts || pts.length === 0) return null;

    const axis = depth % 2; // 0 for x, 1 for y
    pts.sort((a, b) => a[axis] - b[axis]);

    const mid = Math.floor(pts.length / 2);
    const node = new KDNode(pts[mid], null, null, axis);

    node.left = this._buildRecursive(pts.slice(0, mid), depth + 1);
    node.right = this._buildRecursive(pts.slice(mid + 1), depth + 1);

    return node;
  }

  rangeQuery(xMin, xMax, yMin, yMax, node = this.root) {
    if (!node) return [];

    const results = [];
    const [x, y, data] = node.point;

    if (x >= xMin && x <= xMax && y >= yMin && y <= yMax) {
      results.push({ x, y, data });
    }

    const axis = node.axis;
    const val = axis === 0 ? x : y;
    const minVal = axis === 0 ? xMin : yMin;
    const maxVal = axis === 0 ? xMax : yMax;

    if (minVal <= val && node.left) {
      results.push(...this.rangeQuery(xMin, xMax, yMin, yMax, node.left));
    }
    if (maxVal >= val && node.right) {
      results.push(...this.rangeQuery(xMin, xMax, yMin, yMax, node.right));
    }

    return results;
  }

  nearestNeighbor(targetX, targetY) {
    if (!this.root) return null;

    let bestPoint = null;
    let bestDistSq = Infinity;

    function search(node) {
      if (!node) return;

      const [x, y, data] = node.point;
      const dSq = (x - targetX) ** 2 + (y - targetY) ** 2;

      if (dSq < bestDistSq) {
        bestDistSq = dSq;
        bestPoint = { x, y, data, distance: Math.sqrt(dSq) };
      }

      const axis = node.axis;
      const targetVal = axis === 0 ? targetX : targetY;
      const nodeVal = axis === 0 ? x : y;

      const nearNode = targetVal < nodeVal ? node.left : node.right;
      const farNode = targetVal < nodeVal ? node.right : node.left;

      search(nearNode);

      // Check whether far plane could contain a closer point
      if ((targetVal - nodeVal) ** 2 < bestDistSq) {
        search(farNode);
      }
    }

    search(this.root);
    return bestPoint;
  }

  getMetrics() {
    return {
      size: this.size,
      dimensions: 2,
      complexity: {
        rangeQuery: 'O(sqrt(N) + k)',
        nearestNeighbor: 'O(log N)_AVERAGE'
      },
      partitionModel: 'CYCLING_AXIS_MEDIAN_SPLIT'
    };
  }
}

module.exports = { KDNode, KDTreeFilter };
