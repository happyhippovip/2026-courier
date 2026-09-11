# GitHub Community Governance Pack & Issue Templates
**Product**: agent-context-trimmer  
**Target Repository Directory**: `.github/ISSUE_TEMPLATE/` and `.github/PULL_REQUEST_TEMPLATE.md`

---

## 1. Bug Report Template (`bug_report.yml`)
```yaml
name: Bug Report
description: Report unexpected prompt pruning, AST parser syntax errors, or broken rules.
labels: ["bug", "triage"]
body:
  - type: markdown
    attributes:
      value: Thank you for reporting a bug with agent-context-trimmer!
  - type: textarea
    id: prompt_sample
    attributes:
      label: Minimal Reproducible Prompt
      description: Provide the minimal input prompt that produces erroneous trimming or syntax errors.
      placeholder: |
        # System Instructions
        - MUST preserve this rule...
    validations:
      required: true
  - type: input
    id: cli_version
    attributes:
      label: CLI Version
      placeholder: 1.0.0
    validations:
      required: true
  - type: textarea
    id: expected_vs_actual
    attributes:
      label: Expected vs Actual Behavior
      description: Explain what was pruned that should have been kept, or vice versa.
    validations:
      required: true
```

---

## 2. Feature Request Template (`feature_request.yml`)
```yaml
name: Feature Request / Parser Improvement
description: Propose a new AST pruning rule, model tokenizer support, or SDK adapter.
labels: ["enhancement"]
body:
  - type: textarea
    id: feature_desc
    attributes:
      label: Proposed Improvement
      description: Describe the new feature or model integration you would like to see.
    validations:
      required: true
  - type: textarea
    id: use_case
    attributes:
      label: Agent Use Case
      description: How does this help agent developer workflows or reduce LLM costs?
```

---

## 3. Commercial Support & License Issue Template (`commercial_support.yml`)
```yaml
name: Commercial Customer Support
description: Dedicated support for Gumroad license holders and enterprise teams.
labels: ["commercial-support", "priority"]
body:
  - type: input
    id: order_ref
    attributes:
      label: Gumroad Order ID
      description: Your order reference from your Gumroad purchase receipt.
    validations:
      required: true
  - type: textarea
    id: support_details
    attributes:
      label: Issue Description
      description: Describe your licensing or enterprise deployment issue.
    validations:
      required: true
```

---

## 4. Code of Conduct & Contributing Guide
- **Code of Conduct**: Strict zero-harassment, collaborative environment adhering to Contributor Covenant 2.1.
- **Contributing Principles**:
  - All core parser functions must maintain 0 third-party runtime dependencies.
  - Every AST transformation must include 100% offline unit tests.
  - Zero telemetry or network egress allowed in core binaries.
