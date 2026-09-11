/**
 * Multi-Turn Context Semantic Dependency Disambiguation & Coreference Graph Engine
 * Identifies anaphoric pronouns and references across multi-turn context streams,
 * linking pronouns to antecedent entities and protecting critical antecedent turns during context pruning.
 */

class CoreferenceGraphEngine {
  constructor() {
    this.pronounPatterns = [
      { regex: /\b(it|this|that)\b/gi, category: 'singular_concept' },
      { regex: /\b(they|these|those)\b/gi, category: 'plural_concept' },
      { regex: /\b(the\s+transaction|the\s+order|the\s+payment)\b/gi, category: 'transaction' },
      { regex: /\b(the\s+agent|the\s+user|the\s+customer)\b/gi, category: 'actor' }
    ];
  }

  extractEntities(turnText, turnIndex) {
    const entities = [];
    // Entity patterns: IDs, currencies, order references, named concepts
    const patterns = [
      { regex: /\b(order_[a-z0-9_]+)\b/gi, type: 'order_id' },
      { regex: /\b(customer_[a-z0-9_]+)\b/gi, type: 'customer_id' },
      { regex: /\b(tx_[a-z0-9_]+)\b/gi, type: 'transaction_id' },
      { regex: /(€\s*\d+(?:\.\d{2})?|\b(?:euro|eur)\s*\d+)\b/gi, type: 'currency_amount' },
      { regex: /\b(license_key_[a-z0-9_]+)\b/gi, type: 'license_key' }
    ];

    for (const p of patterns) {
      let match;
      while ((match = p.regex.exec(turnText)) !== null) {
        entities.push({
          entityId: match[1].toLowerCase(),
          type: p.type,
          turnIndex,
          charOffset: match.index
        });
      }
    }
    return entities;
  }

  buildGraph(turns) {
    const allEntities = [];
    const coreferenceLinks = [];
    const antecedentTurns = new Set();

    turns.forEach((turnText, turnIndex) => {
      const turnEntities = this.extractEntities(turnText, turnIndex);
      allEntities.push(...turnEntities);

      // Check for pronouns/anaphora in current turn
      for (const p of this.pronounPatterns) {
        let match;
        while ((match = p.regex.exec(turnText)) !== null) {
          const mentionText = match[1].toLowerCase();
          // Find most recent matching entity in prior turns
          const candidates = allEntities.filter(e => e.turnIndex < turnIndex);
          if (candidates.length > 0) {
            const antecedent = candidates[candidates.length - 1]; // most recent
            coreferenceLinks.push({
              turnIndex,
              mention: mentionText,
              category: p.category,
              antecedentEntity: antecedent.entityId,
              antecedentTurn: antecedent.turnIndex
            });
            antecedentTurns.add(antecedent.turnIndex);
          }
        }
      }
    });

    return {
      totalEntities: allEntities.length,
      totalLinks: coreferenceLinks.length,
      antecedentTurns: Array.from(antecedentTurns),
      entities: allEntities,
      links: coreferenceLinks
    };
  }

  safePrune(turns, maxRetainedTurns, graph) {
    const protectedTurns = new Set(graph.antecedentTurns);
    // Always protect last turn (current user turn)
    protectedTurns.add(turns.length - 1);

    const candidatesToPrune = [];
    turns.forEach((turn, idx) => {
      if (!protectedTurns.has(idx)) {
        candidatesToPrune.push(idx);
      }
    });

    const turnsToEvictCount = Math.max(0, turns.length - maxRetainedTurns);
    const evictedTurns = new Set(candidatesToPrune.slice(0, turnsToEvictCount));

    const retainedTurns = turns
      .map((text, idx) => ({ idx, text }))
      .filter(t => !evictedTurns.has(t.idx));

    return {
      originalTurnsCount: turns.length,
      retainedTurnsCount: retainedTurns.length,
      evictedTurnsCount: evictedTurns.size,
      retainedTurns,
      protectedAntecedentTurns: Array.from(protectedTurns)
    };
  }
}

module.exports = { CoreferenceGraphEngine };
