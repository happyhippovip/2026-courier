/**
 * ast_normalizer.js - Cross-Language AST Normalizer & Token Estimator
 * Extracts and normalizes multi-language code snippets (JS/TS, Python, Go, Rust, SQL)
 * embedded within prompt streams, eliminating boilerplate while preserving semantic signatures.
 */
class CrossLanguageAstNormalizer {
  constructor(options = {}) {
    this.charsPerToken = options.charsPerToken || 4;
  }

  estimateTokens(text) {
    if (!text || typeof text !== 'string') return 0;
    return Math.ceil(text.length / this.charsPerToken);
  }

  extractCodeBlocks(markdownText) {
    if (!markdownText || typeof markdownText !== 'string') return [];
    const blockRegex = /```([a-zA-Z0-9_-]+)?\n([\s\S]*?)```/g;
    const blocks = [];
    let match;

    while ((match = blockRegex.exec(markdownText)) !== null) {
      blocks.push({
        language: (match[1] || 'text').toLowerCase(),
        rawContent: match[2],
        fullMatch: match[0],
        index: match.index
      });
    }

    return blocks;
  }

  normalizeSnippet(code, language = 'javascript') {
    if (!code || typeof code !== 'string') return '';
    let cleaned = code;

    // Remove single line comments
    if (['javascript', 'typescript', 'js', 'ts', 'go', 'rust', 'c', 'cpp'].includes(language)) {
      cleaned = cleaned.replace(/\/\/.*$/gm, '');
      cleaned = cleaned.replace(/\/\*[\s\S]*?\*\//g, '');
    } else if (['python', 'py', 'ruby', 'bash', 'sh'].includes(language)) {
      cleaned = cleaned.replace(/#.*$/gm, '');
    } else if (['sql'].includes(language)) {
      cleaned = cleaned.replace(/--.*$/gm, '');
    }

    // Collapse multiple empty lines
    cleaned = cleaned.split('\n')
      .map(line => line.trimEnd())
      .filter(line => line.trim().length > 0)
      .join('\n');

    return cleaned;
  }

  normalizePrompt(promptMarkdown) {
    const blocks = this.extractCodeBlocks(promptMarkdown);
    let transformed = promptMarkdown;
    let totalOriginalChars = 0;
    let totalNormalizedChars = 0;

    blocks.forEach(block => {
      const origLength = block.rawContent.length;
      const normalized = this.normalizeSnippet(block.rawContent, block.language);
      const normLength = normalized.length;

      totalOriginalChars += origLength;
      totalNormalizedChars += normLength;

      const replacement = '```' + block.language + '\n' + normalized + '\n```';
      transformed = transformed.replace(block.fullMatch, replacement);
    });

    const origTokens = this.estimateTokens(promptMarkdown);
    const normTokens = this.estimateTokens(transformed);
    const savedTokens = Math.max(0, origTokens - normTokens);

    return {
      codeBlocksFound: blocks.length,
      languagesDetected: Array.from(new Set(blocks.map(b => b.language))),
      originalTokens: origTokens,
      normalizedTokens: normTokens,
      tokensSaved: savedTokens,
      savingsPercentage: origTokens > 0 ? Number(((savedTokens / origTokens) * 100).toFixed(1)) : 0,
      normalizedContent: transformed,
      timestamp: new Date().toISOString()
    };
  }
}

module.exports = { CrossLanguageAstNormalizer };
