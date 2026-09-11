/**
 * Context Window Checkpoint Delta Compactor
 * Detects duplicate/unchanged subtrees between successive agent state checkpoints,
 * replacing unmodified subtrees with lightweight path references ($ref) to dramatically
 * reduce prompt token overhead in multi-turn stateful agent runs.
 */

class CheckpointDeltaCompactor {
  constructor() {}

  computeDelta(prevState, currentState, basePath = '$') {
    if (prevState === currentState) {
      return { $ref: basePath };
    }

    if (!prevState || typeof prevState !== 'object' || !currentState || typeof currentState !== 'object') {
      return currentState;
    }

    if (Array.isArray(currentState)) {
      if (Array.isArray(prevState) && JSON.stringify(prevState) === JSON.stringify(currentState)) {
        return { $ref: basePath };
      }
      return currentState.map((item, idx) => {
        const prevItem = Array.isArray(prevState) ? prevState[idx] : undefined;
        return this.computeDelta(prevItem, item, basePath + '[' + idx + ']');
      });
    }

    // Object comparison
    const delta = {};
    const allKeys = new Set([...Object.keys(prevState), ...Object.keys(currentState)]);

    for (const key of allKeys) {
      const currentVal = currentState[key];
      const prevVal = prevState[key];
      const currentPath = basePath + '.' + key;

      if (currentVal === undefined) {
        // Key was deleted
        delta[key] = { $deleted: true };
      } else if (prevVal === undefined) {
        // Key was newly added
        delta[key] = currentVal;
      } else if (JSON.stringify(prevVal) === JSON.stringify(currentVal)) {
        // Subtree identical - replace with reference
        delta[key] = { $ref: currentPath };
      } else if (typeof currentVal === 'object' && currentVal !== null && typeof prevVal === 'object' && prevVal !== null) {
        // Subtree partially modified - recurse
        delta[key] = this.computeDelta(prevVal, currentVal, currentPath);
      } else {
        // Primitive modified
        delta[key] = currentVal;
      }
    }

    return delta;
  }

  resolvePath(rootObj, pathStr) {
    if (pathStr === '$') return rootObj;
    const parts = pathStr.replace(/^\$\.?/, '').split(/\.|(?:\[(\d+)\])/).filter(Boolean);
    let curr = rootObj;
    for (const part of parts) {
      if (curr === undefined || curr === null) return undefined;
      curr = curr[part];
    }
    return curr;
  }

  reconstructState(prevState, delta) {
    if (!delta || typeof delta !== 'object') return delta;
    if (delta.$ref) {
      return this.resolvePath(prevState, delta.$ref);
    }

    if (Array.isArray(delta)) {
      return delta.map(item => this.reconstructState(prevState, item));
    }

    const reconstructed = {};
    for (const [k, v] of Object.entries(delta)) {
      if (v && typeof v === 'object' && v.$deleted === true) {
        continue; // skip deleted
      }
      if (v && typeof v === 'object' && v.$ref) {
        reconstructed[k] = this.resolvePath(prevState, v.$ref);
      } else if (typeof v === 'object' && v !== null) {
        reconstructed[k] = this.reconstructState(prevState, v);
      } else {
        reconstructed[k] = v;
      }
    }
    return reconstructed;
  }

  calculateCompressionMetrics(prevState, currentState, delta) {
    const fullJson = JSON.stringify(currentState);
    const deltaJson = JSON.stringify(delta);
    const fullTokens = Math.max(1, Math.round(fullJson.length / 4));
    const deltaTokens = Math.max(1, Math.round(deltaJson.length / 4));
    const tokensSaved = Math.max(0, fullTokens - deltaTokens);
    const savingsPct = Number(((tokensSaved / fullTokens) * 100).toFixed(1));

    return {
      fullTokens,
      deltaTokens,
      tokensSaved,
      savingsPct,
      deltaSizeRatio: Number((deltaTokens / fullTokens).toFixed(2))
    };
  }
}

module.exports = { CheckpointDeltaCompactor };