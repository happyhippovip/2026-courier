class PiiRedactor {
  constructor() {
    this.patterns = [
      { name: 'EMAIL', regex: /[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+/g, mask: '[REDACTED_EMAIL]' },
      { name: 'IPV4', regex: /\b(?:\d{1,3}\.){3}\d{1,3}\b/g, mask: '[REDACTED_IP]' },
      { name: 'JWT', regex: /\beyJ[a-zA-Z0-9_-]+\.eyJ[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+\b/g, mask: '[REDACTED_JWT]' },
      { name: 'PHONE', regex: /\b(?:\+\d{1,3}[- ]?)?\(?\d{3}\)?[- ]?\d{3}[- ]?\d{4}\b/g, mask: '[REDACTED_PHONE]' },
      { name: 'BEARER', regex: /Bearer\s+[a-zA-Z0-9_\-\.~+/]+=*/gi, mask: 'Bearer [REDACTED_TOKEN]' }
    ];
  }

  redact(text) {
    if (!text || typeof text !== 'string') return { redactedText: '', redactionCount: 0, items: [] };

    let result = text;
    let totalCount = 0;
    const items = [];

    for (const pattern of this.patterns) {
      const matches = result.match(pattern.regex);
      if (matches) {
        totalCount += matches.length;
        items.push({ type: pattern.name, count: matches.length });
        result = result.replace(pattern.regex, pattern.mask);
      }
    }

    return {
      redactedText: result,
      redactionCount: totalCount,
      items
    };
  }
}

module.exports = { PiiRedactor };
