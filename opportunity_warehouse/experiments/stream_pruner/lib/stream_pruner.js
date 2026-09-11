class StreamPruner {
  constructor(options = {}) {
    this.buffer = '';
    this.prunedChunks = [];
    this.stripThinking = options.stripThinking !== undefined ? options.stripThinking : true;
    this.totalOriginalChars = 0;
    this.totalPrunedChars = 0;
  }

  processChunk(chunk) {
    if (!chunk || typeof chunk !== 'string') return '';
    this.totalOriginalChars += chunk.length;
    this.buffer += chunk;

    let outputChunk = '';

    if (this.stripThinking) {
      // Look for completed thinking tags: <thought>...</thought> or <thinking>...</thinking>
      const thoughtRegex = /<(?:thought|thinking)>[\s\S]*?<\/(?:thought|thinking)>/gi;
      if (thoughtRegex.test(this.buffer)) {
        this.buffer = this.buffer.replace(thoughtRegex, '');
      }
    }

    // Prune duplicate consecutive blank lines
    this.buffer = this.buffer.replace(/\n{3,}/g, '\n\n');

    // If buffer contains a newline, emit up to the last newline
    const lastNewlineIdx = this.buffer.lastIndexOf('\n');
    if (lastNewlineIdx !== -1) {
      outputChunk = this.buffer.slice(0, lastNewlineIdx + 1);
      this.buffer = this.buffer.slice(lastNewlineIdx + 1);
    }

    this.totalPrunedChars += outputChunk.length;
    this.prunedChunks.push(outputChunk);
    return outputChunk;
  }

  flush() {
    let finalChunk = this.buffer;
    if (this.stripThinking) {
      finalChunk = finalChunk.replace(/<(?:thought|thinking)>[\s\S]*?<\/(?:thought|thinking)>/gi, '');
    }
    this.buffer = '';
    this.totalPrunedChars += finalChunk.length;
    this.prunedChunks.push(finalChunk);
    return finalChunk;
  }

  getMetrics() {
    const charsSaved = Math.max(0, this.totalOriginalChars - this.totalPrunedChars);
    const savingsPercent = this.totalOriginalChars > 0 
      ? Number(((charsSaved / this.totalOriginalChars) * 100).toFixed(2))
      : 0;

    return {
      totalOriginalChars: this.totalOriginalChars,
      totalPrunedChars: this.totalPrunedChars,
      charsSaved,
      savingsPercent
    };
  }
}

module.exports = { StreamPruner };
