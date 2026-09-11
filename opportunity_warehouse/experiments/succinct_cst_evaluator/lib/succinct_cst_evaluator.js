/**
 * Context Window Token Succinct CST LCP-Array Evaluator
 * Computes Suffix Array and Kasai's Longest Common Prefix (LCP) array
 * in O(N) linear time for maximal repeat and redundancy extraction.
 */

class SuccinctCSTEvaluator {
  // Construct Suffix Array for string text
  static buildSuffixArray(text) {
    const n = text.length;
    const suffixes = [];
    for (let i = 0; i < n; i++) {
      suffixes.push({ index: i, str: text.substring(i) });
    }
    suffixes.sort((a, b) => a.str.localeCompare(b.str));
    return suffixes.map(s => s.index);
  }

  // Kasai's algorithm for O(N) LCP Array construction
  static buildLCPArray(text, sa) {
    const n = text.length;
    const rank = new Array(n).fill(0);
    for (let i = 0; i < n; i++) {
      rank[sa[i]] = i;
    }

    const lcp = new Array(n).fill(0);
    let h = 0;

    for (let i = 0; i < n; i++) {
      if (rank[i] > 0) {
        const k = sa[rank[i] - 1];
        while (i + h < n && k + h < n && text[i + h] === text[k + h]) {
          h++;
        }
        lcp[rank[i]] = h;
        if (h > 0) h--;
      }
    }

    return lcp;
  }

  // Find longest repeated substring
  static findLongestRepeat(text) {
    const sa = SuccinctCSTEvaluator.buildSuffixArray(text);
    const lcp = SuccinctCSTEvaluator.buildLCPArray(text, sa);

    let maxLCP = 0;
    let maxIdx = -1;

    for (let i = 1; i < lcp.length; i++) {
      if (lcp[i] > maxLCP) {
        maxLCP = lcp[i];
        maxIdx = sa[i];
      }
    }

    return {
      sa,
      lcp,
      longestRepeatLength: maxLCP,
      longestRepeatString: maxLCP > 0 ? text.substring(maxIdx, maxIdx + maxLCP) : ''
    };
  }
}

module.exports = { SuccinctCSTEvaluator };
