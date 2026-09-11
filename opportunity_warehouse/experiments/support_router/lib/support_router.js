class SupportRouter {
  constructor() {
    this.categoryRules = [
      {
        category: 'LICENSE_VERIFICATION',
        keywords: ['license', 'key', 'activate', 'gumroad', 'invalid license', 'receipt'],
        priority: 'HIGH',
        suggestedResponse: 'Please ensure you pass your license key via the --license-key flag or set the AGENT_TRIMMER_LICENSE environment variable. If your key shows expired or invalid, reply with your Gumroad order ID and we will re-issue it immediately.'
      },
      {
        category: 'AST_PARSER_ERROR',
        keywords: ['syntax error', 'parse error', 'broken markdown', 'yaml', 'corrupted code block'],
        priority: 'CRITICAL',
        suggestedResponse: 'Thank you for reporting this AST parsing issue. agent-context-trimmer v1.0.0 uses strict syntactic preservation. Please run with --dry-run --dump-ast and share the minimal prompt snippet so our engineers can reproduce and fix it.'
      },
      {
        category: 'FRAMEWORK_INTEGRATION',
        keywords: ['langchain', 'llamaindex', 'crewai', 'autogen', 'openai', 'anthropic'],
        priority: 'MEDIUM',
        suggestedResponse: 'agent-context-trimmer works seamlessly with all agent frameworks! You can invoke it as a pre-processing middleware function or use our provided Python / TypeScript SDK wrappers in the /sdk folder.'
      },
      {
        category: 'BILLING_REFUND',
        keywords: ['refund', 'invoice', 'charge', 'vat', 'receipt', 'tax'],
        priority: 'HIGH',
        suggestedResponse: 'All payments are handled securely via Gumroad. You can retrieve your VAT-compliant invoice directly from your Gumroad receipt email. For refund requests within 14 days, send your order reference and we will process it unconditionally.'
      }
    ];
  }

  routeTicket(inquiry) {
    const text = (inquiry.subject + ' ' + inquiry.body).toLowerCase();
    let bestMatch = null;
    let maxKeywordHits = 0;

    for (const rule of this.categoryRules) {
      let hits = 0;
      for (const kw of rule.keywords) {
        if (text.includes(kw)) hits++;
      }
      if (hits > maxKeywordHits) {
        maxKeywordHits = hits;
        bestMatch = rule;
      }
    }

    if (!bestMatch || maxKeywordHits === 0) {
      return {
        ticketId: 'TCK-' + Date.now().toString(36).toUpperCase(),
        category: 'GENERAL_INQUIRY',
        priority: 'LOW',
        automatedResponse: 'Thank you for reaching out to the agent-context-trimmer support team. A technical maintainer will review your inquiry within 24 hours.'
      };
    }

    return {
      ticketId: 'TCK-' + Date.now().toString(36).toUpperCase(),
      category: bestMatch.category,
      priority: bestMatch.priority,
      matchedKeywords: maxKeywordHits,
      automatedResponse: bestMatch.suggestedResponse
    };
  }
}

module.exports = { SupportRouter };
