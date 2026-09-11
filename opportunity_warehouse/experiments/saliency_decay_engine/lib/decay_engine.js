/**
 * Multi-Turn Context Semantic Saliency Decay & Attention Annealing Engine
 * Dynamically decays historical conversational turns using half-life annealing,
 * protecting pinned invariant anchors while evicting cold, unreferenced memory items.
 */

class SaliencyDecayEngine {
  constructor(options = {}) {
    this.decayRate = options.decayRate || 0.15; // lambda in exp(-lambda * deltaTurns)
    this.pruneThreshold = options.pruneThreshold || 0.25;
    this.currentTurn = 1;
    this.items = []; // array of { id, text, turnCreated, initialWeight, currentWeight, pinned, tags, tokens }
  }

  addItem(id, text, options = {}) {
    const tokens = options.tokens || Math.ceil(text.length / 4);
    const item = {
      id,
      text,
      turnCreated: this.currentTurn,
      initialWeight: options.initialWeight || 1.0,
      currentWeight: options.initialWeight || 1.0,
      pinned: options.pinned || false,
      tags: options.tags || [],
      tokens
    };
    this.items.push(item);
    return item;
  }

  advanceTurn(reinforcements = []) {
    this.currentTurn++;

    for (const item of this.items) {
      if (item.pinned) {
        item.currentWeight = 1.0;
        continue;
      }

      // Check reinforcement (by ID or tag)
      const isReinforced = reinforcements.includes(item.id) ||
        item.tags.some(t => reinforcements.includes(t));

      if (isReinforced) {
        // Boost weight and reset turn baseline
        item.currentWeight = Math.min(1.0, item.currentWeight + 0.5);
        item.turnCreated = this.currentTurn;
      } else {
        const delta = this.currentTurn - item.turnCreated;
        item.currentWeight = Number((item.initialWeight * Math.exp(-this.decayRate * delta)).toFixed(4));
      }
    }
  }

  pruneToBudget(maxTokenBudget) {
    const totalTokens = this.items.reduce((acc, it) => acc + it.tokens, 0);
    if (totalTokens <= maxTokenBudget) {
      return {
        prunedCount: 0,
        tokensSaved: 0,
        retainedTokens: totalTokens,
        retainedItems: this.items
      };
    }

    // Separate pinned (never pruned) and unpinned
    const pinned = this.items.filter(it => it.pinned);
    const unpinned = this.items.filter(it => !it.pinned);

    // Sort unpinned by currentWeight descending (keep highest weight)
    unpinned.sort((a, b) => b.currentWeight - a.currentWeight);

    let currentTokens = pinned.reduce((acc, it) => acc + it.tokens, 0);
    const retainedUnpinned = [];
    const pruned = [];

    for (const item of unpinned) {
      if (item.currentWeight >= this.pruneThreshold && currentTokens + item.tokens <= maxTokenBudget) {
        retainedUnpinned.push(item);
        currentTokens += item.tokens;
      } else {
        pruned.push(item);
      }
    }

    // Maintain original turn order in retained
    const retainedIds = new Set([...pinned.map(p => p.id), ...retainedUnpinned.map(u => u.id)]);
    this.items = this.items.filter(it => retainedIds.has(it.id));

    const tokensSaved = pruned.reduce((acc, it) => acc + it.tokens, 0);

    return {
      prunedCount: pruned.length,
      tokensSaved,
      retainedTokens: currentTokens,
      prunedItems: pruned.map(p => ({ id: p.id, weight: p.currentWeight, tokens: p.tokens })),
      retainedItems: this.items
    };
  }
}

module.exports = { SaliencyDecayEngine };
