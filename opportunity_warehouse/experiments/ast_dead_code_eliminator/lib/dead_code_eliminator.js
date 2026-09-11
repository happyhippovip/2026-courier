/**
 * AST Call Graph & Unused Function Elimination Engine
 * Parses JavaScript/TypeScript code snippets, maps internal call dependencies,
 * and strips unreferenced functions and dead code to minimize context bloat.
 */

class DeadCodeEliminator {
  constructor() {}

  extractFunctions(code = '') {
    // Regex-based AST extractor for function declarations
    // Matches: function name(...) { ... } or const name = (...) => { ... }
    const functionRegex = /(?:function\s+([a-zA-Z0-9_$]+)|(?:const|let|var)\s+([a-zA-Z0-9_$]+)\s*=\s*(?:function|\([^)]*\)\s*=>))/g;
    const functions = new Map();

    let match;
    while ((match = functionRegex.exec(code)) !== null) {
      const name = match[1] || match[2];
      const startIndex = match.index;
      
      // Find matching brace block
      const openBrace = code.indexOf('{', startIndex);
      if (openBrace !== -1) {
        let depth = 1;
        let endIndex = openBrace + 1;
        while (depth > 0 && endIndex < code.length) {
          if (code[endIndex] === '{') depth++;
          else if (code[endIndex] === '}') depth--;
          endIndex++;
        }

        const body = code.slice(startIndex, endIndex);
        functions.set(name, {
          name,
          startIndex,
          endIndex,
          fullCode: body,
          tokens: Math.max(1, Math.round(body.length / 4))
        });
      }
    }

    return functions;
  }

  buildCallGraph(functions) {
    const graph = new Map(); // name -> Set of called function names

    for (const [name, fn] of functions.entries()) {
      const calls = new Set();
      for (const targetName of functions.keys()) {
        if (targetName !== name) {
          // Check if targetName is called in fn.fullCode
          const callPattern = new RegExp('\\b' + targetName + '\\s*\\(', 'g');
          if (callPattern.test(fn.fullCode)) {
            calls.add(targetName);
          }
        }
      }
      graph.set(name, calls);
    }

    return graph;
  }

  findReachableSymbols(rootSymbols = [], callGraph) {
    const reachable = new Set();
    const queue = [...rootSymbols];

    while (queue.length > 0) {
      const curr = queue.shift();
      if (!reachable.has(curr)) {
        reachable.add(curr);
        const deps = callGraph.get(curr) || new Set();
        for (const dep of deps) {
          if (!reachable.has(dep)) {
            queue.push(dep);
          }
        }
      }
    }

    return reachable;
  }

  pruneDeadFunctions(code = '', requiredSymbols = []) {
    const functions = this.extractFunctions(code);
    const callGraph = this.buildCallGraph(functions);
    const reachable = this.findReachableSymbols(requiredSymbols, callGraph);

    const prunableFunctions = [];
    for (const [name, fn] of functions.entries()) {
      if (!reachable.has(name)) {
        prunableFunctions.push(fn);
      }
    }

    // Sort descending by startIndex to remove without offsetting indices
    prunableFunctions.sort((a, b) => b.startIndex - a.startIndex);

    let prunedCode = code;
    let tokensSaved = 0;

    for (const fn of prunableFunctions) {
      prunedCode = prunedCode.slice(0, fn.startIndex) + prunedCode.slice(fn.endIndex);
      tokensSaved += fn.tokens;
    }

    // Clean up excessive blank lines
    prunedCode = prunedCode.replace(/\n\s*\n\s*\n/g, '\n\n').trim();

    return {
      originalTokens: Math.max(1, Math.round(code.length / 4)),
      prunedTokens: Math.max(1, Math.round(prunedCode.length / 4)),
      tokensSaved,
      pruneRatioPercent: code.length > 0 ? Number(((tokensSaved / Math.round(code.length / 4)) * 100).toFixed(1)) : 0,
      totalFunctionsFound: functions.size,
      retainedSymbols: Array.from(reachable),
      prunedFunctions: prunableFunctions.map(f => f.name),
      prunedCode
    };
  }
}

module.exports = { DeadCodeEliminator };
