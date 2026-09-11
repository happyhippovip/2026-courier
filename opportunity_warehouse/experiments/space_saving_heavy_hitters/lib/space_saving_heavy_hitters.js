/**
 * Context Window Token Space-Saving Heavy Hitters Evaluator
 * Implements Metwally et al. Space-Saving algorithm.
 * Tracks (token, count, error) triplets. When an unmonitored item arrives and capacity is full,
 * the item with minimum count min_count is replaced by the new item with count = min_count + 1
 * and error = min_count. Guarantees true frequency is bounded: count - error <= f_x <= count.
 */

class SpaceSavingItem {
  constructor(token, count, error = 0) {
    this.token = token;
    this.count = count;
    this.error = error;
  }
}

class SpaceSavingHeavyHitters {
  constructor(k) {
    if (k < 2) throw new Error('k must be >= 2');
    this.k = k; // Maximum number of items tracked
    this.items = new Map(); // token -> SpaceSavingItem
    this.totalProcessed = 0;
  }

  processToken(token) {
    this.totalProcessed++;

    if (this.items.has(token)) {
      const item = this.items.get(token);
      item.count++;
      return;
    }

    if (this.items.size < this.k) {
      this.items.set(token, new SpaceSavingItem(token, 1, 0));
      return;
    }

    // Find item with minimum count
    let minItem = null;
    let minKey = null;
    for (const [key, item] of this.items.entries()) {
      if (!minItem || item.count < minItem.count) {
        minItem = item;
        minKey = key;
      }
    }

    // Evict minItem and insert new token with count = minItem.count + 1 and error = minItem.count
    this.items.delete(minKey);
    this.items.set(token, new SpaceSavingItem(token, minItem.count + 1, minItem.count));
  }

  processStream(tokens) {
    for (const token of tokens) {
      this.processToken(token);
    }
  }

  getHeavyHitters() {
    const threshold = this.totalProcessed / this.k;
    const results = [];
    for (const item of this.items.values()) {
      results.push({
        token: item.token,
        count: item.count,
        error: item.error,
        guaranteedMinCount: item.count - item.error,
        estimatedFrequency: item.count / this.totalProcessed,
        isGuaranteedHeavyHitter: (item.count - item.error) > threshold
      });
    }
    return results.sort((a, b) => b.count - a.count);
  }

  getItem(token) {
    return this.items.get(token) || null;
  }
}

module.exports = { SpaceSavingHeavyHitters, SpaceSavingItem };
