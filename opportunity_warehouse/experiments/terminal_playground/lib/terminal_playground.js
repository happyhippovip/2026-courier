class TerminalPlayground {
  constructor(initialPrompt = '') {
    this.initialPrompt = initialPrompt;
    this.activeRules = {
      dedupHeaders: true,
      pruneComments: true,
      minifyWhitespace: true,
      stripDecorativeAscii: true
    };
  }

  toggleRule(ruleName) {
    if (this.activeRules[ruleName] !== undefined) {
      this.activeRules[ruleName] = !this.activeRules[ruleName];
    }
    return this.activeRules;
  }

  simulatePruning() {
    let result = this.initialPrompt;
    const initialTokens = Math.ceil(result.length / 4);

    if (this.activeRules.stripDecorativeAscii) {
      result = result.replace(/[─│┌┐└┘├┤┬┴┼═║╔╗╚╝╠╣╦╩╬▓▒░■▲▼◄►]+/g, '');
    }

    if (this.activeRules.pruneComments) {
      result = result.replace(/<!--[\s\S]*?-->/g, '');
      result = result.replace(/\/\/[^\n]*/g, '');
    }

    if (this.activeRules.dedupHeaders) {
      const seenHeaders = new Set();
      result = result.split('\n').filter(line => {
        if (line.startsWith('#')) {
          const h = line.trim();
          if (seenHeaders.has(h)) return false;
          seenHeaders.add(h);
        }
        return true;
      }).join('\n');
    }

    if (this.activeRules.minifyWhitespace) {
      result = result.replace(/\n{3,}/g, '\n\n').trim();
    }

    const finalTokens = Math.ceil(result.length / 4);
    const tokensSaved = Math.max(0, initialTokens - finalTokens);
    const savingsPct = initialTokens > 0 ? Number(((tokensSaved / initialTokens) * 100).toFixed(2)) : 0;

    return {
      activeRules: { ...this.activeRules },
      initialTokens,
      finalTokens,
      tokensSaved,
      savingsPct,
      previewSnippet: result.slice(0, 150)
    };
  }
}

module.exports = { TerminalPlayground };
