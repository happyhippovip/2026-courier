/**
 * Dynamic Context Window Compaction via Recursive Summarization & Delta Indexing
 * Condenses conversational turns while preserving technical anchors (file paths, hashes, error codes).
 */

class RecursiveSummarizer {
  constructor() {}

  extractAnchors(text = '') {
    const anchors = {
      filePaths: [],
      errorCodes: [],
      hashes: []
    };

    // File paths: e.g. path/to/file.ext or C:\path\to\file.ext
    const pathRegex = /(?:[a-zA-Z]:\\|\/|[a-zA-Z0-9_-]+\/)[a-zA-Z0-9_./\\-]+\.[a-zA-Z0-9]+/g;
    const paths = text.match(pathRegex) || [];
    anchors.filePaths = Array.from(new Set(paths));

    // Error codes: e.g. ERR_ASSERTION, ENOENT, EACCES, 404, 500
    const errRegex = /\b(?:ERR_[A-Z0-9_]+|E[A-Z]{3,6}|STATUS_[0-9]{3}|HTTP_[0-9]{3})\b/g;
    const errs = text.match(errRegex) || [];
    anchors.errorCodes = Array.from(new Set(errs));

    // Hashes: e.g. git SHA 7-40 hex chars
    const hashRegex = /\b[0-9a-f]{7,40}\b/gi;
    const hashes = text.match(hashRegex) || [];
    anchors.hashes = Array.from(new Set(hashes.filter(h => !/^\d+$/.test(h)))); // filter pure numbers

    return anchors;
  }

  summarizeTurn(turn = {}) {
    const content = turn.content || '';
    const anchors = this.extractAnchors(content);

    // Build condensed summary preserving all anchors
    const anchorSummary = [];
    if (anchors.filePaths.length > 0) anchorSummary.push('Files: ' + anchors.filePaths.join(', '));
    if (anchors.errorCodes.length > 0) anchorSummary.push('Errors: ' + anchors.errorCodes.join(', '));
    if (anchors.hashes.length > 0) anchorSummary.push('Hashes: ' + anchors.hashes.join(', '));

    const condensedText = '[Turn ' + turn.turnId + ' Summary]: ' + (turn.role || 'agent') + ' executed action. ' +
      anchorSummary.join(' | ');

    const origTokens = Math.max(1, Math.round(content.length / 4));
    const prunedTokens = Math.max(1, Math.round(condensedText.length / 4));

    return {
      turnId: turn.turnId,
      originalTokens: origTokens,
      prunedTokens: prunedTokens,
      tokensSaved: Math.max(0, origTokens - prunedTokens),
      anchorsPreserved: anchors,
      condensedContent: condensedText
    };
  }

  compactHistory(turns = [], targetTokenBudget = 2000) {
    let totalTokens = turns.reduce((acc, t) => acc + Math.round((t.content || '').length / 4), 0);
    if (totalTokens <= targetTokenBudget) {
      return {
        compacted: false,
        originalTokens: totalTokens,
        finalTokens: totalTokens,
        turns: turns
      };
    }

    const processedTurns = [];
    const deltaIndex = [];
    let currentTokens = totalTokens;

    // Compact older turns first until budget satisfied
    for (let i = 0; i < turns.length; i++) {
      const turn = turns[i];
      // Keep latest 2 turns intact if possible
      if (i < turns.length - 2 && currentTokens > targetTokenBudget) {
        const summary = this.summarizeTurn(turn);
        currentTokens -= summary.tokensSaved;
        processedTurns.push({
          turnId: turn.turnId,
          role: turn.role,
          content: summary.condensedContent,
          isCompacted: true
        });
        deltaIndex.push({
          turnId: turn.turnId,
          anchors: summary.anchorsPreserved,
          tokensSaved: summary.tokensSaved
        });
      } else {
        processedTurns.push({
          turnId: turn.turnId,
          role: turn.role,
          content: turn.content,
          isCompacted: false
        });
      }
    }

    return {
      compacted: true,
      originalTokens: totalTokens,
      finalTokens: currentTokens,
      totalTokensSaved: totalTokens - currentTokens,
      savingsPercent: Number((((totalTokens - currentTokens) / totalTokens) * 100).toFixed(1)),
      deltaIndex,
      turns: processedTurns
    };
  }
}

module.exports = { RecursiveSummarizer };
