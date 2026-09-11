/**
 * Multi-Turn Context Coherence & Pronoun Resolution Validator
 * Detects dangling anaphoric references (pronouns, demonstratives) when aggressive
 * context pruning removes the required antecedent entity.
 */

class CoherenceValidator {
  constructor() {
    this.anaphoricPatterns = [
      /\b(it|its|they|them|their|this|that|these|those)\b/gi,
      /\b(?:the error|the file|the bug|the function|the class)\b/gi
    ];
  }

  extractReferences(text = '') {
    const refs = [];
    for (const pattern of this.anaphoricPatterns) {
      let match;
      while ((match = pattern.exec(text)) !== null) {
        refs.push({
          word: match[0].toLowerCase(),
          offset: match.index
        });
      }
    }
    return refs;
  }

  extractNamedEntities(text = '') {
    // Entities that act as valid antecedents: functions, files, errors, variables
    const entities = new Set();

    // Words with camelCase or snake_case
    const idRegex = /\b[a-zA-Z][a-zA-Z0-9]*[A-Z_][a-zA-Z0-9_]*\b/g;
    const ids = text.match(idRegex) || [];
    ids.forEach(id => entities.add(id.toLowerCase()));

    // File extensions
    const fileRegex = /\b[a-zA-Z0-9_-]+\.(?:js|ts|py|go|rs|json|md|html)\b/g;
    const files = text.match(fileRegex) || [];
    files.forEach(f => entities.add(f.toLowerCase()));

    return Array.from(entities);
  }

  validateCoherence(retainedContext = '', currentQuery = '') {
    const queryRefs = this.extractReferences(currentQuery);
    const retainedEntities = this.extractNamedEntities(retainedContext);

    const dangling = [];
    const satisfied = [];

    for (const ref of queryRefs) {
      // Demonstratives like "this file" or "it" require at least one entity in context
      if (retainedEntities.length === 0) {
        dangling.push({
          reference: ref.word,
          reason: 'NO_ANTECEDENT_ENTITIES_IN_RETAINED_CONTEXT'
        });
      } else {
        satisfied.push({
          reference: ref.word,
          potentialAntecedentsCount: retainedEntities.length
        });
      }
    }

    const isCoherent = dangling.length === 0;
    const coherenceScore = queryRefs.length > 0
      ? Number(((satisfied.length / queryRefs.length)).toFixed(2))
      : 1.0;

    return {
      isCoherent,
      coherenceScore,
      totalReferencesFound: queryRefs.length,
      danglingReferences: dangling,
      retainedEntitiesCount: retainedEntities.length,
      recommendation: isCoherent ? 'COHERENT_PROCEED' : 'RESTORE_REFERRED_ENTITIES'
    };
  }
}

module.exports = { CoherenceValidator };
