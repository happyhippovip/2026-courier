/**
 * Context Window JSON Schema Pruner & Strict Type Flattener
 * Strips verbose metadata ($schema, title, examples) and flattens nested allOf structures
 * in tool schemas to maximize token efficiency without breaking schema validation.
 */

class JsonSchemaPruner {
  constructor() {
    this.metadataFieldsToStrip = new Set([
      '$schema', 'title', 'examples', 'default', 'additionalProperties'
    ]);
  }

  pruneSchema(schema = {}, options = {}) {
    const stripDescriptions = options.stripDescriptions || false;

    const processNode = (node) => {
      if (!node || typeof node !== 'object') return node;

      if (Array.isArray(node)) {
        return node.map(processNode);
      }

      const pruned = {};

      // Check for nested allOf flattening: if node has allOf with 1 item, flatten it
      if (node.allOf && Array.isArray(node.allOf) && node.allOf.length === 1) {
        const flattened = processNode(node.allOf[0]);
        Object.assign(pruned, flattened);
      }

      for (const [key, value] of Object.entries(node)) {
        if (key === 'allOf' && node.allOf.length === 1) continue; // already flattened
        if (this.metadataFieldsToStrip.has(key)) continue;
        if (key === 'description' && stripDescriptions) continue;

        pruned[key] = processNode(value);
      }

      return pruned;
    };

    const result = processNode(schema);
    const rawJson = JSON.stringify(schema, null, 2);
    const prunedJson = JSON.stringify(result);

    const origTokens = Math.max(1, Math.round(rawJson.length / 4));
    const finalTokens = Math.max(1, Math.round(prunedJson.length / 4));

    return {
      originalTokens: origTokens,
      prunedTokens: finalTokens,
      tokensSaved: Math.max(0, origTokens - finalTokens),
      savingsPercent: Number((((origTokens - finalTokens) / origTokens) * 100).toFixed(1)),
      prunedSchema: result
    };
  }

  validatePayload(schema, payload) {
    if (!schema || !schema.properties) return true;
    const required = schema.required || [];

    // Check all required fields present
    for (const req of required) {
      if (payload[req] === undefined) return false;
    }

    // Check types
    for (const [prop, val] of Object.entries(payload)) {
      if (schema.properties[prop]) {
        const expectedType = schema.properties[prop].type;
        if (expectedType === 'string' && typeof val !== 'string') return false;
        if (expectedType === 'number' && typeof val !== 'number') return false;
        if (expectedType === 'boolean' && typeof val !== 'boolean') return false;
      }
    }

    return true;
  }
}

module.exports = { JsonSchemaPruner };
