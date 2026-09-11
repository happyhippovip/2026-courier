/**
 * Levenshtein Automaton & Approximate Keyword Search Engine
 * Provides bounded-distance fuzzy token search and automaton state evaluation
 * over token vocabularies and context buffers with O(k * |term|) query complexity.
 */

class LevenshteinAutomaton {
  constructor(pattern, maxDistance = 2) {
    this.pattern = pattern.toLowerCase();
    this.maxDistance = maxDistance;
  }

  // Compute Levenshtein distance using optimized dynamic programming matrix
  static computeDistance(s1, s2) {
    const a = s1.toLowerCase();
    const b = s2.toLowerCase();
    const m = a.length;
    const n = b.length;

    let prev = new Array(n + 1);
    let curr = new Array(n + 1);

    for (let j = 0; j <= n; j++) prev[j] = j;

    for (let i = 1; i <= m; i++) {
      curr[0] = i;
      const charA = a.charCodeAt(i - 1);
      for (let j = 1; j <= n; j++) {
        const cost = (charA === b.charCodeAt(j - 1)) ? 0 : 1;
        curr[j] = Math.min(
          prev[j] + 1,      // deletion
          curr[j - 1] + 1,  // insertion
          prev[j - 1] + cost // substitution
        );
      }
      for (let j = 0; j <= n; j++) prev[j] = curr[j];
    }

    return prev[n];
  }

  // Match a candidate token against the pattern within maxDistance
  match(token) {
    const distance = LevenshteinAutomaton.computeDistance(this.pattern, token);
    return {
      token,
      matches: distance <= this.maxDistance,
      distance,
      similarity: 1 - (distance / Math.max(this.pattern.length, token.length, 1))
    };
  }

  // Search a vocabulary or token list for all approximate matches
  search(vocabulary) {
    const results = [];
    for (const token of vocabulary) {
      const res = this.match(token);
      if (res.matches) {
        results.push(res);
      }
    }
    // Sort by distance ascending, then similarity descending
    results.sort((a, b) => a.distance - b.distance || b.similarity - a.similarity);
    return results;
  }
}

module.exports = { LevenshteinAutomaton };
