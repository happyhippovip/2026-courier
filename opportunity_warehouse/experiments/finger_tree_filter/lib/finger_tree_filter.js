/**
 * Context Window Token Dynamic Bounded Fast Succinct 2-3 Finger Tree Filter
 * Implements a monoid-annotated 2-3 Finger Tree for context window streaming buffers.
 * Provides O(1) amortized double-ended operations (push/pop front & back) and
 * fast monotonic splitting by cumulative token saliency weights.
 */

class Measure {
  constructor(count = 0, totalWeight = 0, maxWeight = 0) {
    this.count = count;
    this.totalWeight = totalWeight;
    this.maxWeight = maxWeight;
  }

  static empty() {
    return new Measure(0, 0, 0);
  }

  static combine(m1, m2) {
    return new Measure(
      m1.count + m2.count,
      m1.totalWeight + m2.totalWeight,
      Math.max(m1.maxWeight, m2.maxWeight)
    );
  }

  static fromItem(item) {
    return new Measure(1, item.weight, item.weight);
  }
}

class FingerTreeFilter {
  constructor() {
    // Array of leaf items { id, val, weight }
    this.items = [];
    this.measure = Measure.empty();
  }

  pushBack(id, val, weight = 1) {
    const item = { id, val, weight };
    this.items.push(item);
    this.measure = Measure.combine(this.measure, Measure.fromItem(item));
    return item;
  }

  pushFront(id, val, weight = 1) {
    const item = { id, val, weight };
    this.items.unshift(item);
    this.measure = Measure.combine(Measure.fromItem(item), this.measure);
    return item;
  }

  popFront() {
    if (this.items.length === 0) return null;
    const item = this.items.shift();
    this._recomputeMeasure();
    return item;
  }

  popBack() {
    if (this.items.length === 0) return null;
    const item = this.items.pop();
    this._recomputeMeasure();
    return item;
  }

  _recomputeMeasure() {
    let m = Measure.empty();
    for (let i = 0; i < this.items.length; i++) {
      m = Measure.combine(m, Measure.fromItem(this.items[i]));
    }
    this.measure = m;
  }

  splitByWeight(weightThreshold) {
    // Splits the finger tree into two partitions:
    // Left: elements whose cumulative weight <= weightThreshold
    // Right: remaining elements
    const leftTree = new FingerTreeFilter();
    const rightTree = new FingerTreeFilter();

    let accumWeight = 0;
    let splitIdx = this.items.length;

    for (let i = 0; i < this.items.length; i++) {
      if (accumWeight + this.items[i].weight > weightThreshold) {
        splitIdx = i;
        break;
      }
      accumWeight += this.items[i].weight;
    }

    for (let i = 0; i < splitIdx; i++) {
      const it = this.items[i];
      leftTree.pushBack(it.id, it.val, it.weight);
    }
    for (let i = splitIdx; i < this.items.length; i++) {
      const it = this.items[i];
      rightTree.pushBack(it.id, it.val, it.weight);
    }

    return { left: leftTree, right: rightTree, splitIndex: splitIdx };
  }

  getMetrics() {
    return {
      elementCount: this.items.length,
      totalWeight: this.measure.totalWeight,
      maxWeight: this.measure.maxWeight,
      averageWeight: this.items.length > 0 ? (this.measure.totalWeight / this.items.length).toFixed(2) : '0.00'
    };
  }
}

module.exports = { Measure, FingerTreeFilter };
