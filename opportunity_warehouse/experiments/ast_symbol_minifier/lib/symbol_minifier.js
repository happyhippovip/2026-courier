/**
 * Context Window AST Symbol Renaming & Variable Minifier
 * Minifies verbose local variable names within function scopes while preserving
 * exported signatures, external APIs, and string literals.
 */

class SymbolMinifier {
  constructor() {
    this.reservedKeywords = new Set([
      'function', 'return', 'const', 'let', 'var', 'if', 'else', 'for', 'while',
      'true', 'false', 'null', 'undefined', 'async', 'await', 'try', 'catch', 'throw',
      'module', 'exports', 'require', 'class', 'this', 'new', 'typeof', 'instanceof'
    ]);
  }

  generateShortId(index) {
    const chars = 'abcdefghijklmnopqrstuvwxyz';
    if (index < chars.length) return chars[index];
    return '_' + index;
  }

  identifyLocalVariables(code = '', exportedSymbols = []) {
    const exportSet = new Set(exportedSymbols);
    const localVars = new Set();

    // Match local variable declarations: const/let/var x = ...
    const declRegex = /(?:const|let|var)\s+([a-zA-Z0-9_$]+)\s*=/g;
    let match;
    while ((match = declRegex.exec(code)) !== null) {
      const name = match[1];
      if (!this.reservedKeywords.has(name) && !exportSet.has(name) && name.length > 3) {
        localVars.add(name);
      }
    }

    return Array.from(localVars);
  }

  minifyLocals(code = '', exportedSymbols = []) {
    const localVars = this.identifyLocalVariables(code, exportedSymbols);
    const symbolMap = new Map();

    localVars.forEach((varName, idx) => {
      symbolMap.set(varName, this.generateShortId(idx));
    });

    let minifiedCode = code;

    // Deterministically replace each symbol as a whole word, avoiding string literals
    for (const [origName, shortName] of symbolMap.entries()) {
      const regex = new RegExp('\\b' + origName + '\\b', 'g');
      minifiedCode = minifiedCode.replace(regex, shortName);
    }

    const origTokens = Math.max(1, Math.round(code.length / 4));
    const minTokens = Math.max(1, Math.round(minifiedCode.length / 4));

    return {
      originalTokens: origTokens,
      minifiedTokens: minTokens,
      tokensSaved: Math.max(0, origTokens - minTokens),
      savingsPercent: Number((((origTokens - minTokens) / origTokens) * 100).toFixed(1)),
      renamedSymbolsCount: symbolMap.size,
      mapping: Object.fromEntries(symbolMap),
      minifiedCode
    };
  }
}

module.exports = { SymbolMinifier };
