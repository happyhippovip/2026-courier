/**
 * Context Window Streaming FSA Guard & Syntax Validator
 * Deterministic Finite-State Automaton tracking lexer states (strings, objects, arrays),
 * detecting abrupt token truncations, and automatically repairing incomplete JSON envelopes
 * to prevent downstream parser failures.
 */

class FsaSyntaxGuard {
  constructor() {}

  inspectStream(text = '') {
    const stack = [];
    let inString = false;
    let isEscaped = false;

    for (let i = 0; i < text.length; i++) {
      const ch = text[i];

      if (inString) {
        if (isEscaped) {
          isEscaped = false;
        } else if (ch === '\\') {
          isEscaped = true;
        } else if (ch === '"') {
          inString = false;
        }
      } else {
        if (ch === '"') {
          inString = true;
        } else if (ch === '{') {
          stack.push('}');
        } else if (ch === '[') {
          stack.push(']');
        } else if (ch === '}' || ch === ']') {
          if (stack.length > 0 && stack[stack.length - 1] === ch) {
            stack.pop();
          }
        }
      }
    }

    const isTruncated = inString || stack.length > 0;
    return {
      inString,
      unclosedStack: stack,
      isTruncated,
      isCleanTerminal: !isTruncated
    };
  }

  repairTruncatedJson(truncatedText = '') {
    const status = this.inspectStream(truncatedText);
    if (!status.isTruncated) return truncatedText;

    let repaired = truncatedText;
    // If truncated inside a string, close quote
    if (status.inString) {
      repaired += '"';
    }

    // Pop and append required closing delimiters in reverse order
    const stack = [...status.unclosedStack];
    while (stack.length > 0) {
      repaired += stack.pop();
    }

    return repaired;
  }
}

module.exports = { FsaSyntaxGuard };