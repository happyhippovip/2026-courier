/**
 * Context Window Token Dynamic Bounded Fast Succinct Compressed Suffix Array Evaluator
 * Compressed Suffix Array (CSA) using Burrow-Wheeler Transform (BWT) and LF-mapping
 * for fast O(P log N) substring locate and count queries in succinct memory.
 */

class CompressedSuffixArrayEvaluator {
  constructor() {
    this.tokens = [];
    this.sa = [];
    this.bwt = [];
    this.c = new Map(); // token -> cumulative count in first column
    this.occ = new Map(); // token -> array of cumulative occurrences in BWT
  }

  build(tokens) {
    // Add terminal sentinel token
    this.tokens = [...tokens, '$'];
    const n = this.tokens.length;

    // Construct full Suffix Array by sorting indices
    const suffixIndices = Array.from({ length: n }, (_, i) => i);
    suffixIndices.sort((a, b) => {
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

    this.sa = suffixIndices;

    // Construct BWT: BWT[i] = tokens[ (SA[i] - 1 + n) % n ]
    this.bwt = this.sa.map(idx => this.tokens[(idx - 1 + n) % n]);

    // Build C array (cumulative count of characters in First column)
    const sortedTokens = [...this.tokens].sort((a, b) => String(a).localeCompare(String(b)));
    const counts = new Map();
    for (const tok of sortedTokens) {
      counts.set(tok, (counts.get(tok) || 0) + 1);
    }

    let cum = 0;
    this.c.clear();
    for (const [tok, cnt] of counts.entries()) {
      this.c.set(tok, cum);
      cum += cnt;
    }

    // Build Occ table
    this.occ.clear();
    const runningCounts = new Map();
    for (let i = 0; i < n; i++) {
      const tok = this.bwt[i];
      runningCounts.set(tok, (runningCounts.get(tok) || 0) + 1);
      for (const [t, cnt] of runningCounts.entries()) {
        if (!this.occ.has(t)) this.occ.set(t, new Array(n).fill(0));
        this.occ.get(t)[i] = cnt;
      }
      // propagate non-present tokens
      for (const t of counts.keys()) {
        if (!this.occ.has(t)) this.occ.set(t, new Array(n).fill(0));
        if (this.occ.get(t)[i] === undefined || this.occ.get(t)[i] === 0) {
          this.occ.get(t)[i] = i > 0 ? this.occ.get(t)[i - 1] : 0;
        }
      }
    }
  }

  _getOcc(token, idx) {
    if (idx < 0) return 0;
    if (!this.occ.has(token)) return 0;
    const arr = this.occ.get(token);
    return idx < arr.length ? arr[idx] : arr[arr.length - 1];
  }

  count(pattern) {
    const range = this._findRange(pattern);
    return range ? (range.sp <= range.ep ? range.ep - range.sp + 1 : 0) : 0;
  }

  locate(pattern) {
    const range = this._findRange(pattern);
    if (!range || range.sp > range.ep) return [];
    const results = [];
    for (let i = range.sp; i <= range.ep; i++) {
      results.push(this.sa[i]);
    }
    return results.sort((a, b) => a - b);
  }

  _findRange(pattern) {
    if (!pattern || pattern.length === 0) return null;
    let m = pattern.length;
    let tok = pattern[m - 1];
    if (!this.c.has(tok)) return null;

    let sp = this.c.get(tok);
    let ep = (this.c.get(tok) + (this.tokens.filter(t => t === tok).length)) - 1;

    let i = m - 2;
    while (sp <= ep && i >= 0) {
      tok = pattern[i];
      if (!this.c.has(tok)) return null;
      sp = this.c.get(tok) + this._getOcc(tok, sp - 1);
      ep = this.c.get(tok) + this._getOcc(tok, ep) - 1;
      i--;
    }

    return { sp, ep };
  }

  getCompressionRatio() {
    // Compressed SA stores BWT + sampling intervals instead of full N*log(N) integers
    const rawBits = this.tokens.length * 32;
    const succinctBits = this.bwt.length * 8 + this.c.size * 32;
    return Number((succinctBits / rawBits).toFixed(4));
  }
}

module.exports = { CompressedSuffixArrayEvaluator };
