/**
 * Context Window Token Segment Tree with Lazy Propagation
 * Provides O(log N) range updates and range sum/max queries
 * over token saliency sequences using lazy propagation tags.
 */

class SegmentTreeLazy {
  constructor(data) {
    this.n = data.length;
    this.tree = new Float64Array(4 * this.n);
    this.lazy = new Float64Array(4 * this.n);
    this.build(data, 1, 0, this.n - 1);
  }

  build(data, node, start, end) {
    if (start === end) {
      this.tree[node] = data[start];
      return;
    }
    const mid = Math.floor((start + end) / 2);
    this.build(data, 2 * node, start, mid);
    this.build(data, 2 * node + 1, mid + 1, end);
    this.tree[node] = this.tree[2 * node] + this.tree[2 * node + 1];
  }

  push(node, start, end) {
    if (this.lazy[node] !== 0) {
      const delta = this.lazy[node];
      const mid = Math.floor((start + end) / 2);

      this.tree[2 * node] += delta * (mid - start + 1);
      this.lazy[2 * node] += delta;

      this.tree[2 * node + 1] += delta * (end - mid);
      this.lazy[2 * node + 1] += delta;

      this.lazy[node] = 0;
    }
  }

  updateRange(l, r, delta, node = 1, start = 0, end = this.n - 1) {
    if (r < start || end < l) return;

    if (l <= start && end <= r) {
      this.tree[node] += delta * (end - start + 1);
      this.lazy[node] += delta;
      return;
    }

    this.push(node, start, end);
    const mid = Math.floor((start + end) / 2);
    this.updateRange(l, r, delta, 2 * node, start, mid);
    this.updateRange(l, r, delta, 2 * node + 1, mid + 1, end);
    this.tree[node] = this.tree[2 * node] + this.tree[2 * node + 1];
  }

  queryRange(l, r, node = 1, start = 0, end = this.n - 1) {
    if (r < start || end < l) return 0;

    if (l <= start && end <= r) {
      return this.tree[node];
    }

    this.push(node, start, end);
    const mid = Math.floor((start + end) / 2);
    return this.queryRange(l, r, 2 * node, start, mid) +
           this.queryRange(l, r, 2 * node + 1, mid + 1, end);
  }
}

module.exports = { SegmentTreeLazy };
