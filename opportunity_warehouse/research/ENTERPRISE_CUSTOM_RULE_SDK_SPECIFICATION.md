# Symphony Enterprise Custom Rule Extension SDK & Plugin Architecture

**Specification Version**: 1.0.0-ENTERPRISE  
**Target Audience**: Enterprise Platform Architects, DevSecOps Engineers, Custom Tooling Teams  
**Runtime Compatibility**: Node.js 18.x+, Zero External Dependencies  

---

## 1. Architectural Purpose

Enterprise development organizations possess proprietary internal frameworks, confidential domain models, and custom boilerplate patterns that cannot be addressed by off-the-shelf AST pruning rules.

The **Symphony Custom Rule Extension SDK** enables platform engineering teams to author, test, and distribute proprietary in-house AST pruning rules across thousands of internal developer workstations without modifying the core trimmer engine.

```
  +-------------------------------------------------------------+
  |              Symphony Rule Execution Pipeline               |
  |                                                             |
  |   Input Code / AST                                          |
  |         │                                                   |
  |         ▼                                                   |
  |   +───────────────────────────────────+                     |
  |   | Core Symphony Rules (v1.0.0)      |                     |
  |   +─────────────────┬─────────────────+                     |
  |                     │                                       |
  |                     ▼                                       |
  |   +───────────────────────────────────+                     |
  |   | Enterprise Custom Rule Extensions | <-- [In-House SDK]  |
  |   | - ACME-Fintech-Proto-Pruner       |                     |
  |   | - HIPAA-HealthRecord-Filter       |                     |
  |   +─────────────────┬─────────────────+                     |
  |                     │                                       |
  |                     ▼                                       |
  |   Optimized / Sanitized Context Stream                      |
  +-------------------------------------------------------------+
```

---

## 2. Standardized Rule Plugin Interface (`SymphonyRulePlugin`)

Every custom rule plugin implements the following TypeScript / JavaScript contract:

```typescript
interface SymphonyRulePlugin {
  name: string;             // e.g., "@acme/fintech-ast-pruner"
  version: string;          // SemVer e.g., "1.2.0"
  targetLanguages: string[]; // ["typescript", "protobuf", "go"]
  
  // Evaluates whether this node is eligible for custom transformation
  matchNode(node: ASTNode, context: RuleContext): boolean;
  
  // Executes deterministic in-place structural pruning
  transform(node: ASTNode, context: RuleContext): TransformResult;
  
  // Estimates token savings for telemetry / reporting
  estimateSavings(originalNode: ASTNode, transformedNode: ASTNode): number;
}
```

---

## 3. Sandboxing & Safety Invariants

To maintain enterprise operational stability:
1. **Zero External I/O**: Custom plugins execute within an isolated Node.js context with restricted access to disk and network.
2. **Fail-Open Policy**: If a custom enterprise rule throws an uncaught exception, the engine logs a warning, skips the faulty rule, and outputs the original node safely.
3. **Deterministic AST Validation**: Every transformed node is verified by `ast_syntax_guard.js` to ensure 100% syntactical reversibility before dispatch.

---

## 4. Distribution & Deployment via Internal Private Registry
- Enterprise plugins are packaged as private npm scoped packages (`@mycorp/symphony-rules`).
- Automatically loaded by `agent-context-trimmer --plugin @mycorp/symphony-rules`.
