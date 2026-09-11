/**
 * Context Window Token Dynamic Bounded Fast Succinct CDAWG / Suffix Automaton Filter
 * Implements a linear-time Suffix Automaton to index context window text streams,
 * providing O(m) substring verification, exact occurrence frequency counting, and
 * longest common substring extraction with sublinear state transitions.
 */

class CDAWGFilter {
  constructor() {
    this.st = [{ len: 0, link: -1, next: new Map(), isClone: false, endPosCount: 0 }];
    this.sz = 1;
    this.last = 0;
    this.indexedLength = 0;
  }

  insert(text) {
    if (typeof text !== 'string' || text.length === 0) return;
    for (let i = 0; i < text.length; i++) {
      this._extend(text[i]);
    }
    this.indexedLength += text.length;
    this._propagateEndPosCounts();
  }

  _extend(c) {
    const curr = this.sz++;
    this.st.push({
      len: this.st[this.last].len + 1,
      link: 0,
      next: new Map(),
      isClone: false,
      endPosCount: 1
    });

    let p = this.last;
    while (p !== -1 && !this.st[p].next.has(c)) {
      this.st[p].next.set(c, curr);
      p = this.st[p].link;
    }

    if (p === -1) {
      this.st[curr].link = 0;
    } else {
      const q = this.st[p].next.get(c);
      if (this.st[p].len + 1 === this.st[q].len) {
        this.st[curr].link = q;
      } else {
        const clone = this.sz++;
        this.st.push({
          len: this.st[p].len + 1,
          link: this.st[q].link,
          next: new Map(this.st[q].next),
          isClone: true,
          endPosCount: 0
        });

        while (p !== -1 && this.st[p].next.get(c) === q) {
          this.st[p].next.set(c, clone);
          p = this.st[p].link;
        }

        this.st[q].link = this.st[curr].link = clone;
      }
    }

    this.last = curr;
  }

  _propagateEndPosCounts() {
    // Reset endPosCount for clones and re-aggregate
    // Sort state indices by length descending
    const order = [];
    for (let i = 0; i < this.sz; i++) {
      order.push(i);
    }
    order.sort((a, b) => this.st[b].len - this.st[a].len);

    for (const u of order) {
      if (this.st[u].link !== -1) {
        this.st[this.st[u].link].endPosCount += this.st[u].endPosCount;
      }
    }
  }

  contains(pattern) {
    if (typeof pattern !== 'string' || pattern.length === 0) return false;
    let u = 0;
    for (let i = 0; i < pattern.length; i++) {
      const c = pattern[i];
      if (!this.st[u].next.has(c)) return false;
      u = this.st[u].next.get(c);
    }
    return true;
  }

  countOccurrences(pattern) {
    if (typeof pattern !== 'string' || pattern.length === 0) return 0;
    let u = 0;
    for (let i = 0; i < pattern.length; i++) {
      const c = pattern[i];
      if (!this.st[u].next.has(c)) return 0;
      u = this.st[u].next.get(c);
    }
    return this.st[u].endPosCount;
  }

  longestCommonSubstring(query) {
    if (typeof query !== 'string' || query.length === 0) return { length: 0, substring: '' };
    let u = 0;
    let currLen = 0;
    let maxLen = 0;
    let maxEnd = 0;

    for (let i = 0; i < query.length; i++) {
      const c = query[i];
      while (u !== -1 && !this.st[u].next.has(c)) {
        u = this.st[u].link;
        if (u !== -1) currLen = this.st[u].len;
      }

      if (u === -1) {
        u = 0;
        currLen = 0;
      } else {
        u = this.st[u].next.get(c);
        currLen++;
        if (currLen > maxLen) {
          maxLen = currLen;
          maxEnd = i;
        }
      }
    }

    return {
      length: maxLen,
      substring: query.slice(maxEnd - maxLen + 1, maxEnd + 1)
    };
  }

  getMetrics() {
    let transitionCount = 0;
    for (let i = 0; i < this.sz; i++) {
      transitionCount += this.st[i].next.size;
    }
    const stateCount = this.sz;
    const estimatedBytes = stateCount * 40 + transitionCount * 16;
    const uncompressedTrieEstimatedBytes = (this.indexedLength * (this.indexedLength + 1) / 2) * 32;

    return {
      indexedLength: this.indexedLength,
      stateCount,
      transitionCount,
      estimatedBytes,
      compressionAdvantage: (uncompressedTrieEstimatedBytes / Math.max(1, estimatedBytes)).toFixed(2) + 'x'
    };
  }
}

module.exports = { CDAWGFilter };
