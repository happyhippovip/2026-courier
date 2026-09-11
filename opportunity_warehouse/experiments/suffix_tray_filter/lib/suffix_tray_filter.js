/**
 * Context Window Token Dynamic Bounded Fast Succinct Suffix Tray Filter
 * Implements a two-level hybrid indexing structure (shallow tray prefix table +
 * compact sorted suffix index) for sublinear token sequence pattern matching.
 */

class SuffixTrayFilter {
  constructor(text = '', prefixDepth = 2) {
    this.text = text;
    this.prefixDepth = prefixDepth;
    this.n = text.length;
    this.trays = new Map(); // prefix of length L -> sorted array of suffix starting positions
    if (this.n > 0) {
      this.build(text);
    }
  }

  build(text) {
    this.text = text;
    this.n = text.length;
    this.trays.clear();

    for (let i = 0; i < this.n; i++) {
      const prefix = text.slice(i, i + this.prefixDepth);
      if (!this.trays.has(prefix)) {
        this.trays.set(prefix, []);
      }
      this.trays.get(prefix).push(i);
    }

    // Sort suffixes within each tray lexicographically
    for (const [prefix, positions] of this.trays.entries()) {
      positions.sort((a, b) => {
        const sA = this.text.slice(a + this.prefixDepth);
        const sB = this.text.slice(b + this.prefixDepth);
        return sA.localeCompare(sB);
      });
    }
  }

  locate(pattern) {
    if (typeof pattern !== 'string' || pattern.length === 0) return [];
    const prefix = pattern.slice(0, this.prefixDepth);

    if (pattern.length < this.prefixDepth) {
      // Find all trays that start with pattern
      const matchingLocs = [];
      for (const [trayPrefix, positions] of this.trays.entries()) {
        if (trayPrefix.startsWith(pattern)) {
          for (const pos of positions) {
            if (this.text.startsWith(pattern, pos)) {
              matchingLocs.push(pos);
            }
          }
        }
      }
      return matchingLocs.sort((a, b) => a - b);
    }

    if (!this.trays.has(prefix)) return [];
    const positions = this.trays.get(prefix);

    const matches = [];
    for (const pos of positions) {
      if (this.text.startsWith(pattern, pos)) {
        matches.push(pos);
      }
    }

    return matches.sort((a, b) => a - b);
  }

  count(pattern) {
    return this.locate(pattern).length;
  }

  contains(pattern) {
    return this.count(pattern) > 0;
  }

  longestCommonPrefixWithContext(pattern) {
    if (typeof pattern !== 'string' || pattern.length === 0) return { length: 0, prefix: '' };
    let bestLen = 0;
    let bestPrefix = '';

    for (let len = pattern.length; len >= 1; len--) {
      const sub = pattern.slice(0, len);
      if (this.contains(sub)) {
        bestLen = len;
        bestPrefix = sub;
        break;
      }
    }

    return { length: bestLen, prefix: bestPrefix };
  }

  getMetrics() {
    let maxTraySize = 0;
    let totalPositions = 0;
    for (const arr of this.trays.values()) {
      if (arr.length > maxTraySize) maxTraySize = arr.length;
      totalPositions += arr.length;
    }
    const avgTraySize = this.trays.size > 0 ? (totalPositions / this.trays.size).toFixed(2) : '0.00';

    return {
      textLength: this.n,
      prefixDepth: this.prefixDepth,
      trayCount: this.trays.size,
      maxTraySize,
      averageTraySize: parseFloat(avgTraySize),
      indexingEfficiency: 'O(1)_TRAY_LOOKUP_PLUS_LOCAL_SEARCH'
    };
  }
}

module.exports = { SuffixTrayFilter };
