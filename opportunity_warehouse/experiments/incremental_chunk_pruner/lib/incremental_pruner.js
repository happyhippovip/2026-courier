/**
 * incremental_pruner.js - AST Chunk Streaming & Incremental Pruning Pipeline
 * Processes massive multi-megabyte context streams in bounded chunks without memory spikes.
 */
class IncrementalChunkPruner {
  constructor(options = {}) {
    this.maxChunkChars = options.maxChunkChars || 1000;
    this.boundaryDelimiter = options.boundaryDelimiter || '\n\n';
  }

  splitIntoChunks(text) {
    if (!text || text.length === 0) return [];
    if (text.length <= this.maxChunkChars) return [text];

    const rawParts = text.split(this.boundaryDelimiter);
    const chunks = [];
    let currentChunk = '';

    for (const part of rawParts) {
      const candidate = currentChunk.length === 0 ? part : currentChunk + this.boundaryDelimiter + part;
      if (candidate.length > this.maxChunkChars && currentChunk.length > 0) {
        chunks.push(currentChunk);
        currentChunk = part;
      } else {
        currentChunk = candidate;
      }
    }
    if (currentChunk.length > 0) {
      chunks.push(currentChunk);
    }
    return chunks;
  }

  pruneChunk(chunk, rules = []) {
    let pruned = chunk;
    // Default safe trims: collapse 3+ empty lines, strip debug comments
    pruned = pruned.replace(/\/\/\s*DEBUG:.*$/gm, '');
    pruned = pruned.replace(/([-=_]{10,}\r?\n){2,}/g, '----------\n');
    pruned = pruned.replace(/\n{3,}/g, '\n\n').trim();

    for (const rule of rules) {
      if (rule.pattern && rule.action === 'trim') {
        const regex = new RegExp(rule.pattern, 'g');
        pruned = pruned.replace(regex, '');
      }
    }
    return pruned;
  }

  processStream(text, rules = []) {
    const originalLength = text.length;
    const rawChunks = this.splitIntoChunks(text);
    const prunedChunks = [];
    let totalSavedChars = 0;

    for (let i = 0; i < rawChunks.length; i++) {
      const p = this.pruneChunk(rawChunks[i], rules);
      totalSavedChars += (rawChunks[i].length - p.length);
      prunedChunks.push(p);
    }

    const assembledOutput = prunedChunks.join('\n\n');
    const compressionRatio = originalLength > 0 ? +((totalSavedChars / originalLength) * 100).toFixed(2) : 0;

    return {
      timestamp: new Date().toISOString(),
      originalLength,
      prunedLength: assembledOutput.length,
      chunksProcessed: rawChunks.length,
      totalSavedChars,
      compressionRatioPercent: compressionRatio,
      output: assembledOutput
    };
  }
}

module.exports = { IncrementalChunkPruner };
