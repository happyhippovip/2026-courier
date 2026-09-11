/**
 * Hierarchical Context Window Suffix-Tree Exact Match & Common Substring Deduplicator
 * Employs suffix array and longest common prefix (LCP) analysis across multi-turn context
 * to extract repeated boilerplate strings, tool schema headers, and stack traces.
 */

class SuffixTreeDeduplicator {
  constructor(options = {}) {
    this.minSubstringLength = options.minSubstringLength || 15;
    this.minOccurrences = options.minOccurrences || 2;
  }

  buildSuffixArray(text) {
    const n = text.length;
    const suffixes = [];
    for (let i = 0; i < n; i++) {
      suffixes.push(i);
    }
    // Sort suffixes lexicographically
    suffixes.sort((a, b) => {
      let i = a;
      let j = b;
      while (i < n && j < n) {
        if (text[i] !== text[j]) {
          return text.charCodeAt(i) - text.charCodeAt(j);
        }
        i++;
        j++;
      }
      return (n - a) - (n - b);
    });
    return suffixes;
  }

  buildLCPArray(text, suffixArray) {
    const n = text.length;
    const rank = new Array(n).fill(0);
    for (let i = 0; i < n; i++) {
      rank[suffixArray[i]] = i;
    }

    const lcp = new Array(n).fill(0);
    let h = 0;
    for (let i = 0; i < n; i++) {
      if (rank[i] > 0) {
        const j = suffixArray[rank[i] - 1];
        while (i + h < n && j + h < n && text[i + h] === text[j + h]) {
          h++;
        }
        lcp[rank[i]] = h;
        if (h > 0) h--;
      }
    }
    return lcp;
  }

  findCommonSubstrings(text, minLen = this.minSubstringLength, minOccur = this.minOccurrences) {
    if (!text || text.length < minLen) return [];

    const sa = this.buildSuffixArray(text);
    const lcp = this.buildLCPArray(text, sa);

    const candidates = new Map(); // substring -> count

    for (let i = 1; i < text.length; i++) {
      const matchLen = lcp[i];
      if (matchLen >= minLen) {
        const sub = text.substring(sa[i], sa[i] + matchLen).trim();
        if (sub.length >= minLen) {
          candidates.set(sub, (candidates.get(sub) || 1) + 1);
        }
      }
    }

    // Filter and sort by savings: (length - refTagLength) * (occurrences - 1)
    const result = [];
    for (const [sub, count] of candidates.entries()) {
      if (count >= minOccur) {
        const estimatedSavings = (sub.length - 12) * (count - 1);
        if (estimatedSavings > 0) {
          result.push({
            substring: sub,
            length: sub.length,
            occurrences: count,
            estimatedSavings
          });
        }
      }
    }

    return result.sort((a, b) => b.estimatedSavings - a.estimatedSavings);
  }

  compactContext(turns, options = {}) {
    const minLen = options.minSubstringLength || this.minSubstringLength;
    const minOccur = options.minOccurrences || this.minOccurrences;

    const delimiter = ' \n__TURN_DELIM__\n ';
    const concatenated = turns.join(delimiter);

    const common = this.findCommonSubstrings(concatenated, minLen, minOccur);

    const dictionary = {};
    let workingText = concatenated;

    let dictId = 1;
    for (const item of common.slice(0, 10)) { // top 10 substrings
      const refTag = '[#REF_' + dictId + ']';
      dictionary[refTag] = item.substring;

      // Replace from 2nd occurrence onwards
      let firstIndex = workingText.indexOf(item.substring);
      if (firstIndex !== -1) {
        const prefix = workingText.substring(0, firstIndex + item.substring.length);
        const rest = workingText.substring(firstIndex + item.substring.length);
        const replacedRest = rest.replaceAll(item.substring, refTag);
        workingText = prefix + replacedRest;
        dictId++;
      }
    }

    const compactedTurns = workingText.split(delimiter);
    const originalBytes = Buffer.byteLength(concatenated, 'utf8');
    const compactedBytes = Buffer.byteLength(workingText, 'utf8');
    const bytesSaved = originalBytes - compactedBytes;
    const compressionRatio = originalBytes > 0 ? (compactedBytes / originalBytes) : 1;

    return {
      originalBytes,
      compactedBytes,
      bytesSaved,
      compressionRatio: Number(compressionRatio.toFixed(4)),
      dictionarySize: Object.keys(dictionary).length,
      dictionary,
      compactedTurns
    };
  }

  decompactContext(compactedTurns, dictionary) {
    const delimiter = ' \n__TURN_DELIM__\n ';
    let text = compactedTurns.join(delimiter);
    for (const [refTag, sub] of Object.entries(dictionary)) {
      text = text.replaceAll(refTag, sub);
    }
    return text.split(delimiter);
  }
}

module.exports = { SuffixTreeDeduplicator };
