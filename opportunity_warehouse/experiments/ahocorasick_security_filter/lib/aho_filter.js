/**
 * Context Window Dynamic Trie-Based Radix Automaton & Aho-Corasick Multi-Pattern Security Filter
 * Implements linear-time O(N + M) simultaneous multi-keyword dictionary matching,
 * intercepting prompt injections, sensitive credential markers, and exfiltration attempts in a single streaming pass.
 */

class AhoNode {
  constructor() {
    this.children = new Map(); // char -> AhoNode
    this.fail = null;
    this.outputs = []; // array of { id, pattern, severity }
  }
}

class AhoCorasickSecurityFilter {
  constructor() {
    this.root = new AhoNode();
    this.isCompiled = false;
    this.patternCount = 0;
  }

  addPattern(pattern, id = null, severity = 'HIGH') {
    if (!pattern || typeof pattern !== 'string') return;
    const lower = pattern.toLowerCase();
    let current = this.root;

    for (let i = 0; i < lower.length; i++) {
      const ch = lower[i];
      if (!current.children.has(ch)) {
        current.children.set(ch, new AhoNode());
      }
      current = current.children.get(ch);
    }

    current.outputs.push({
      id: id || ('pat_' + (++this.patternCount)),
      pattern: lower,
      severity
    });
    this.isCompiled = false;
  }

  buildAutomaton() {
    const queue = [];

    // Root children have fail link pointing to root
    for (const child of this.root.children.values()) {
      child.fail = this.root;
      queue.push(child);
    }

    // BFS to establish failure transitions and output links
    while (queue.length > 0) {
      const current = queue.shift();

      for (const [ch, childNode] of current.children.entries()) {
        let f = current.fail;
        while (f !== null && !f.children.has(ch)) {
          f = f.fail;
        }

        childNode.fail = (f !== null && f.children.has(ch)) ? f.children.get(ch) : this.root;
        // Merge output links from failure node
        if (childNode.fail.outputs.length > 0) {
          childNode.outputs.push(...childNode.fail.outputs);
        }

        queue.push(childNode);
      }
    }

    this.isCompiled = true;
  }

  scan(text) {
    if (!this.isCompiled) this.buildAutomaton();
    if (!text || typeof text !== 'string') return [];

    const lower = text.toLowerCase();
    const matches = [];
    let current = this.root;

    for (let i = 0; i < lower.length; i++) {
      const ch = lower[i];

      while (current !== null && !current.children.has(ch)) {
        current = current.fail;
      }

      if (current === null) {
        current = this.root;
        continue;
      }

      current = current.children.get(ch);

      if (current.outputs.length > 0) {
        for (const out of current.outputs) {
          matches.push({
            id: out.id,
            pattern: out.pattern,
            severity: out.severity,
            startIndex: i - out.pattern.length + 1,
            endIndex: i + 1
          });
        }
      }
    }

    return matches;
  }

  redact(text, replacement = '[REDACTED_SECURITY_ALERT]') {
    const matches = this.scan(text);
    if (matches.length === 0) {
      return { redactedText: text, matchCount: 0, matches: [] };
    }

    // Merge overlapping intervals
    matches.sort((a, b) => a.startIndex - b.startIndex);
    const mergedIntervals = [];
    let currentInterval = { start: matches[0].startIndex, end: matches[0].endIndex };

    for (let i = 1; i < matches.length; i++) {
      const m = matches[i];
      if (m.startIndex <= currentInterval.end) {
        currentInterval.end = Math.max(currentInterval.end, m.endIndex);
      } else {
        mergedIntervals.push(currentInterval);
        currentInterval = { start: m.startIndex, end: m.endIndex };
      }
    }
    mergedIntervals.push(currentInterval);

    // Build redacted string
    let result = '';
    let lastIdx = 0;
    for (const inter of mergedIntervals) {
      result += text.substring(lastIdx, inter.start) + replacement;
      lastIdx = inter.end;
    }
    result += text.substring(lastIdx);

    return {
      redactedText: result,
      matchCount: matches.length,
      distinctIntervalsCount: mergedIntervals.length,
      matches
    };
  }
}

module.exports = { AhoCorasickSecurityFilter };
