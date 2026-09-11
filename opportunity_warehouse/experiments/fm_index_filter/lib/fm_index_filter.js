/**
 * Context Window Token Dynamic Bounded Fast Succinct FM-Index Filter
 * Suffix indexing via Burrows-Wheeler Transform (BWT), C-table, and Occ/Rank table.
 * Supports exact count and locate queries over token sequences or character strings.
 */

class FMIndexFilter {
  constructor(textOrTokens, sampleRate = 2) {
    this.sampleRate = sampleRate;
    this.text = null;
    this.tokens = [];
    this.sa = [];
    this.bwt = [];
    this.c = new Map();
    this.rankTable = new Map();

    if (textOrTokens) {
      this.build(textOrTokens);
    }
  }

  build(textOrTokens) {
    if (typeof textOrTokens === 'string') {
      this.text = textOrTokens;
      this.tokens = textOrTokens.split('');
    } else {
      this.text = null;
      this.tokens = [...textOrTokens];
    }

    const n = this.tokens.length;
    const sa = Array.from({ length: n }, (_, i) => i);
    sa.sort((a, b) => {
      let i = a, j = b;
      while (i < n && j < n) {
        if (this.tokens[i] !== this.tokens[j]) {
          return String(this.tokens[i]).localeCompare(String(this.tokens[j]));
        }
        i++;
        j++;
      }
      return (n - a) - (n - b);
    });

    this.sa = sa;
    this.bwt = new Array(n);
    for (let i = 0; i < n; i++) {
      this.bwt[i] = this.tokens[(sa[i] - 1 + n) % n];
    }

    // Build C table
    const sorted = [...this.tokens].sort((a, b) => String(a).localeCompare(String(b)));
    const counts = new Map();
    for (const t of sorted) counts.set(t, (counts.get(t) || 0) + 1);

    let cum = 0;
    this.c.clear();
    for (const [t, cnt] of counts.entries()) {
      this.c.set(t, cum);
      cum += cnt;
    }

    // Build Rank Table
    this.rankTable.clear();
    const running = new Map();
    for (let i = 0; i < n; i++) {
      const tok = this.bwt[i];
      running.set(tok, (running.get(tok) || 0) + 1);
      for (const [t, r] of running.entries()) {
        if (!this.rankTable.has(t)) this.rankTable.set(t, new Array(n).fill(0));
        this.rankTable.get(t)[i] = r;
      }
      for (const t of counts.keys()) {
        if (!this.rankTable.has(t)) this.rankTable.set(t, new Array(n).fill(0));
        if (this.rankTable.get(t)[i] === undefined || this.rankTable.get(t)[i] === 0) {
          this.rankTable.get(t)[i] = i > 0 ? this.rankTable.get(t)[i - 1] : 0;
        }
      }
    }
  }

  _rank(tok, idx) {
    if (idx < 0) return 0;
    if (!this.rankTable.has(tok)) return 0;
    const arr = this.rankTable.get(tok);
    return idx < arr.length ? arr[idx] : arr[arr.length - 1];
  }

  count(pattern) {
    const locs = this.locate(pattern);
    return locs.length;
  }

  locate(pattern) {
    if (!pattern || pattern.length === 0) return [];
    const patTokens = typeof pattern === 'string' && this.text !== null ? pattern.split('') : (Array.isArray(pattern) ? pattern : [pattern]);
    const m = patTokens.length;

    let low = 0, high = this.sa.length - 1;
    let first = -1;

    while (low <= high) {
      const mid = Math.floor((low + high) / 2);
      const suffixStart = this.sa[mid];
      let cmp = 0;
      for (let k = 0; k < m; k++) {
        if (suffixStart + k >= this.tokens.length) {
          cmp = -1;
          break;
        }
        if (this.tokens[suffixStart + k] !== patTokens[k]) {
          cmp = String(this.tokens[suffixStart + k]).localeCompare(String(patTokens[k]));
          break;
        }
      }

      if (cmp >= 0) {
        if (cmp === 0) first = mid;
        high = mid - 1;
      } else {
        low = mid + 1;
      }
    }

    if (first === -1) return [];

    low = first;
    high = this.sa.length - 1;
    let last = first;

    while (low <= high) {
      const mid = Math.floor((low + high) / 2);
      const suffixStart = this.sa[mid];
      let cmp = 0;
      for (let k = 0; k < m; k++) {
        if (suffixStart + k >= this.tokens.length) {
          cmp = -1;
          break;
        }
        if (this.tokens[suffixStart + k] !== patTokens[k]) {
          cmp = String(this.tokens[suffixStart + k]).localeCompare(String(patTokens[k]));
          break;
        }
      }

      if (cmp === 0) {
        last = mid;
        low = mid + 1;
      } else {
        high = mid - 1;
      }
    }

    const results = [];
    for (let i = first; i <= last; i++) {
      results.push(this.sa[i]);
    }
    return results.sort((a, b) => a - b);
  }

  getMetrics() {
    return {
      textLength: this.tokens.length,
      alphabetSize: this.c.size,
      bwtLength: this.bwt.length,
      sampleRate: this.sampleRate
    };
  }
}

module.exports = { FMIndexFilter };
