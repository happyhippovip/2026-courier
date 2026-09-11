/**
 * AST Regular Expression & Pattern Optimization Engine
 * Detects redundant character classes, simplifies character sets ([0-9] -> \d),
 * and minifies regex patterns to conserve context window tokens.
 */

class RegexOptimizer {
  constructor() {}

  detectRedundancies(pattern = '') {
    const redundancies = [];

    // Duplicate chars in character classes like [aaabbb]
    const classRegex = /\[([^\]]+)\]/g;
    let match;
    while ((match = classRegex.exec(pattern)) !== null) {
      const rawClass = match[1];
      const seen = new Set();
      let hasDuplicates = false;
      for (const char of rawClass) {
        if (seen.has(char)) {
          hasDuplicates = true;
          break;
        }
        seen.add(char);
      }
      if (hasDuplicates) {
        redundancies.push({
          type: 'DUPLICATE_CLASS_CHARS',
          original: match[0]
        });
      }
    }

    if (pattern.includes('[0-9]')) {
      redundancies.push({ type: 'UNOPTIMIZED_DIGIT_CLASS', original: '[0-9]' });
    }
    if (pattern.includes('[a-zA-Z0-9_]')) {
      redundancies.push({ type: 'UNOPTIMIZED_WORD_CLASS', original: '[a-zA-Z0-9_]' });
    }

    return redundancies;
  }

  optimizePattern(pattern = '') {
    let optimized = pattern;

    // 1. Simplify digit class [0-9] -> \d
    optimized = optimized.replace(/\[0-9\]/g, '\\d');

    // 2. Simplify word class [a-zA-Z0-9_] -> \w
    optimized = optimized.replace(/\[a-zA-Z0-9_\]/g, '\\w');

    // 3. De-duplicate characters in remaining character classes
    optimized = optimized.replace(/\[([^\]]+)\]/g, (match, p1) => {
      // Don't modify if contains ranges like a-z
      if (p1.includes('-')) return match;
      const uniqueChars = Array.from(new Set(p1)).join('');
      return '[' + uniqueChars + ']';
    });

    const origTokens = Math.max(1, Math.round(pattern.length / 4));
    const optTokens = Math.max(1, Math.round(optimized.length / 4));

    return {
      originalPattern: pattern,
      optimizedPattern: optimized,
      tokensSaved: Math.max(0, origTokens - optTokens),
      originalLength: pattern.length,
      optimizedLength: optimized.length,
      reductionPercent: pattern.length > 0 ? Number((((pattern.length - optimized.length) / pattern.length) * 100).toFixed(1)) : 0
    };
  }

  verifySemantics(origPattern, optPattern, testStrings = []) {
    const origRe = new RegExp(origPattern);
    const optRe = new RegExp(optPattern);

    const matches = testStrings.map(str => ({
      input: str,
      origMatches: origRe.test(str),
      optMatches: optRe.test(str),
      equivalent: origRe.test(str) === optRe.test(str)
    }));

    return {
      allEquivalent: matches.every(m => m.equivalent),
      results: matches
    };
  }
}

module.exports = { RegexOptimizer };
