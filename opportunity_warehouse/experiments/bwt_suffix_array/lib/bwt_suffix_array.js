/**
 * Suffix Array & Burrows-Wheeler Transform (BWT) Context Inversion Indexer
 * Computes forward BWT, inverse BWT reconstruction, and Suffix Array
 * for ultra-dense context compression and exact pattern searching.
 */

class BWTSuffixArray {
  // Compute Burrows-Wheeler Transform of text (appends sentinel '$')
  static transform(text) {
    const s = text + '$';
    const n = s.length;
    const rotations = [];

    for (let i = 0; i < n; i++) {
      rotations.push({ index: i, str: s.substring(i) + s.substring(0, i) });
    }

    rotations.sort((a, b) => a.str.localeCompare(b.str));

    let bwt = '';
    const suffixArray = [];
    let originalRow = -1;

    for (let i = 0; i < n; i++) {
      bwt += rotations[i].str[n - 1];
      suffixArray.push(rotations[i].index);
      if (rotations[i].index === 0) {
        originalRow = i;
      }
    }

    return { bwt, suffixArray, originalRow, originalLength: n };
  }

  // Exact inverse BWT reconstruction
  static inverse(bwt, originalRow) {
    const n = bwt.length;
    const table = new Array(n).fill('');

    for (let j = 0; j < n; j++) {
      for (let i = 0; i < n; i++) {
        table[i] = bwt[i] + table[i];
      }
      table.sort();
    }

    const reconstructedWithSentinel = table[originalRow];
    return reconstructedWithSentinel.substring(0, reconstructedWithSentinel.length - 1);
  }

  // Count exact occurrences of pattern using suffix array binary search
  static countOccurrences(text, pattern, suffixArray) {
    const n = text.length;
    const m = pattern.length;

    let count = 0;
    for (const pos of suffixArray) {
      if (pos + m <= n) {
        if (text.substring(pos, pos + m) === pattern) {
          count++;
        }
      }
    }
    return count;
  }
}

module.exports = { BWTSuffixArray };
