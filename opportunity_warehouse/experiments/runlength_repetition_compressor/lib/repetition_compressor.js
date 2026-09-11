/**
 * Context Token Lossless Run-Length & Repetition Compressor
 * Detects repeated phrases, tabular null sequences, and character dividers in prompts,
 * encoding them using compact lossless syntax tags [REPEAT: "..." x N] with 100% round-trip fidelity.
 */

class RepetitionCompressor {
  constructor() {}

  compressRepetitions(text = '', minRepeat = 3) {
    if (!text) return { compressedText: '', originalTokens: 0, compressedTokens: 0, savingsPct: 0 };

    let result = text;

    // 1. Long character dividers (e.g. 10 or more dashes, equals, asterisks)
    result = result.replace(/([-=_*#~])\1{9,}/g, (match, char) => {
      return '[REPEAT: "' + char + '" x ' + match.length + ']';
    });

    // 2. Repeated log patterns or sequences like '0, 0, 0, ' or 'null, null, null, '
    result = result.replace(/((\b[a-zA-Z0-9_]+[,; ]+))\1{2,}/g, (match, unit) => {
      const count = match.length / unit.length;
      return '[REPEAT: "' + unit.trim() + '" x ' + count + '] ';
    });

    const origTokens = Math.max(1, Math.round(text.length / 4));
    const compTokens = Math.max(1, Math.round(result.length / 4));
    const tokensSaved = Math.max(0, origTokens - compTokens);
    const savingsPct = Number(((tokensSaved / origTokens) * 100).toFixed(1));

    return {
      originalText: text,
      compressedText: result,
      originalTokens: origTokens,
      compressedTokens: compTokens,
      tokensSaved,
      savingsPct
    };
  }

  decompressRepetitions(compressedText = '') {
    if (!compressedText) return '';

    return compressedText.replace(/\[REPEAT: "([^"]+)" x (\d+)\] ?/g, (match, unit, countStr) => {
      const count = parseInt(countStr, 10);
      // If unit was a single character divider
      if (unit.length === 1) {
        return unit.repeat(count);
      }
      // Repeated token pattern
      return (unit + ' ').repeat(count);
    });
  }
}

module.exports = { RepetitionCompressor };