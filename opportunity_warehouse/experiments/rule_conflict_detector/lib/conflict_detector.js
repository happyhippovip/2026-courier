// Deterministic rule contradiction detector
const KNOWN_OPPOSITIONS = [
  {
    topic: 'TypeScript Typing',
    patternA: /(strict mode|never use any|strict typing|no any)/i,
    patternB: /(allow any|rapid prototyping without types|disable strict)/i,
    description: 'Conflict between strict type safety and permissive dynamic typing'
  },
  {
    topic: 'Paradigm Preference',
    patternA: /(purely functional|avoid classes|prefer functions|no oop)/i,
    patternB: /(class hierarchy|object-oriented|use inheritance|prefer classes)/i,
    description: 'Conflict between functional programming and object-oriented class hierarchies'
  },
  {
    topic: 'Indentation Style',
    patternA: /(use tabs|tab indentation)/i,
    patternB: /(use 2 spaces|use 4 spaces|spaces only)/i,
    description: 'Conflict between tabs and spaces indentation'
  },
  {
    topic: 'Control Flow',
    patternA: /(early return|guard clauses)/i,
    patternB: /(single return point|one exit per function)/i,
    description: 'Conflict between early exit guard clauses and single return point paradigms'
  }
];

function detectRuleConflicts(rulesText) {
  const lines = rulesText.split('\n').map(l => l.trim()).filter(Boolean);
  const conflicts = [];

  for (const pair of KNOWN_OPPOSITIONS) {
    let matchA = null;
    let matchB = null;

    for (const line of lines) {
      if (!matchA && pair.patternA.test(line)) {
        matchA = line;
      }
      if (!matchB && pair.patternB.test(line)) {
        matchB = line;
      }
    }

    if (matchA && matchB) {
      conflicts.push({
        topic: pair.topic,
        description: pair.description,
        rule_a: matchA,
        rule_b: matchB,
        severity: 'HIGH_HALLUCINATION_RISK'
      });
    }
  }

  return {
    total_lines_analyzed: lines.length,
    conflicts_detected: conflicts.length,
    conflicts,
    analyzed_at: new Date().toISOString()
  };
}

module.exports = { detectRuleConflicts, KNOWN_OPPOSITIONS };
