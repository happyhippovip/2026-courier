'use strict';

/**
 * SHADOW IMPLEMENTATION: CANONICAL PATH NORMALIZER
 * Component: shadow/core/resources/path_normalizer.js
 * Mission: WINDOWS_AUTONOMOUS_DEEP_BUILD_PROOF_FACTORY_V2
 */

const path = require('path');

class PathNormalizer {
  constructor(options = {}) {
    this.disableCaseFolding = options.disableCaseFolding || false; // Mutant!
    this.disablePrefixCheck = options.disablePrefixCheck || false; // Mutant!
  }

  normalize(inputPath) {
    if (!inputPath || typeof inputPath !== 'string') return '';

    // 1. Convert backslashes to forward slashes
    let p = inputPath.replace(/\\/g, '/');

    // 2. Handle file:// URI scheme
    if (p.startsWith('file:///')) {
      p = p.substring(8);
    } else if (p.startsWith('file://')) {
      p = p.substring(7);
    }

    // 3. Resolve relative dots (. and ..)
    const segments = p.split('/').filter(Boolean);
    const resolved = [];

    for (const seg of segments) {
      if (seg === '.') {
        continue;
      } else if (seg === '..') {
        if (resolved.length > 0 && resolved[resolved.length - 1] !== '..') {
          resolved.pop();
        } else {
          resolved.push('..');
        }
      } else {
        resolved.push(seg);
      }
    }

    let normalized = resolved.join('/');
    // Preserve leading slash for absolute unix-style or drive letters
    if (p.startsWith('/')) {
      normalized = '/' + normalized;
    }

    // 4. Case folding for Windows-style case-insensitive semantics
    if (!this.disableCaseFolding) {
      normalized = normalized.toLowerCase();
    }

    return normalized;
  }

  isPrefixCollision(pathA, pathB) {
    if (this.disablePrefixCheck) {
      return false; // Mutant!
    }

    const normA = this.normalize(pathA);
    const normB = this.normalize(pathB);

    if (normA === normB) return true;

    // Check if normA is an ancestor of normB
    if (normB.startsWith(normA + '/')) return true;

    // Check if normB is an ancestor of normA
    if (normA.startsWith(normB + '/')) return true;

    return false;
  }
}

module.exports = {
  PathNormalizer
};
