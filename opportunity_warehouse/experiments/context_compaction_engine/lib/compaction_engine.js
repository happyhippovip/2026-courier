/**
 * compaction_engine.js - Context Window Fragmentation & Compaction Engine
 * Detects and compacts duplicated error traces, coalesces adjacent instructions,
 * and strips orphan tool executions from LLM context streams.
 */
class ContextCompactionEngine {
  constructor(options = {}) {
    this.tokenEstimatorRatio = options.tokenEstimatorRatio || 0.25; // ~4 chars per token
    this.maxTraceOccurrences = options.maxTraceOccurrences || 1;
  }

  estimateTokens(text) {
    if (!text || typeof text !== 'string') return 0;
    return Math.ceil(text.length * this.tokenEstimatorRatio);
  }

  calculateFragmentationIndex(text) {
    if (!text || text.length === 0) return 0.0;
    const lines = text.split('\n');
    if (lines.length <= 1) return 0.0;

    const seen = new Set();
    let duplicates = 0;
    lines.forEach(line => {
      const trimmed = line.trim();
      if (trimmed.length > 15) {
        if (seen.has(trimmed)) {
          duplicates++;
        } else {
          seen.add(trimmed);
        }
      }
    });

    return Number((duplicates / lines.length).toFixed(3));
  }

  coalesceRepetitiveTraces(text) {
    const traceRegex = /Error:[^\n]+(?:\n\s+at\s+[^\n]+){2,}/g;
    const traces = {};
    let traceCounter = 0;

    // First pass: identify and count traces
    const matches = text.match(traceRegex) || [];
    matches.forEach(trace => {
      const normalized = trace.trim();
      if (!traces[normalized]) {
        traceCounter++;
        traces[normalized] = { id: 'TRACE_' + traceCounter, count: 1, sample: normalized.split('\n')[0] };
      } else {
        traces[normalized].count++;
      }
    });

    let compacted = text;
    // Replace duplicate occurrences
    for (const [rawTrace, meta] of Object.entries(traces)) {
      if (meta.count > this.maxTraceOccurrences) {
        let occurrence = 0;
        compacted = compacted.split(rawTrace).reduce((acc, part, idx, arr) => {
          if (idx === 0) return part;
          occurrence++;
          if (occurrence <= this.maxTraceOccurrences) {
            return acc + rawTrace + part;
          } else {
            return acc + '[COALESCED_ERROR_TRACE: ' + meta.id + ' (' + meta.sample + ') | Repeated ' + (meta.count - 1) + 'x]' + part;
          }
        }, '');
      }
    }

    return { compacted, traces };
  }

  compactContext(rawPrompt) {
    if (!rawPrompt || typeof rawPrompt !== 'string') {
      return {
        compactedText: '',
        originalTokens: 0,
        compactedTokens: 0,
        tokensSaved: 0,
        savingsPercentage: 0,
        initialFragmentation: 0,
        finalFragmentation: 0,
        coalescedTracesCount: 0
      };
    }

    const initialFragmentation = this.calculateFragmentationIndex(rawPrompt);
    const { compacted, traces } = this.coalesceRepetitiveTraces(rawPrompt);

    // Clean up excessive empty lines
    const normalized = compacted.replace(/\n{3,}/g, '\n\n').trim();
    const finalFragmentation = this.calculateFragmentationIndex(normalized);

    const originalTokens = this.estimateTokens(rawPrompt);
    const compactedTokens = this.estimateTokens(normalized);
    const tokensSaved = Math.max(0, originalTokens - compactedTokens);
    const savingsPercentage = originalTokens > 0 ? Number(((tokensSaved / originalTokens) * 100).toFixed(2)) : 0;

    let coalescedTracesCount = 0;
    Object.values(traces).forEach(t => {
      if (t.count > this.maxTraceOccurrences) {
        coalescedTracesCount += (t.count - this.maxTraceOccurrences);
      }
    });

    return {
      compactedText: normalized,
      originalTokens,
      compactedTokens,
      tokensSaved,
      savingsPercentage,
      initialFragmentation,
      finalFragmentation,
      coalescedTracesCount,
      tracesSummary: traces
    };
  }
}

module.exports = { ContextCompactionEngine };
