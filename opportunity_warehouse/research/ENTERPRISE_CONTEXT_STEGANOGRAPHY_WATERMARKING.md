# Enterprise Dynamic Context Steganography & Watermarking Detection Architecture

**Document Reference**: SPEC-SEC-2026-V86  
**Classification**: Enterprise AI Security & Defense Whitepaper  
**Target Standard**: ISO/IEC 27001 Annex A.8, NIST SP 800-218 (Secure Software Development), EU AI Act Article 50 (Transparency)  
**Scope**: Prompt Injection Defense, Zero-Width Unicode Sanitization, Statistical Token Watermarking, Model Exfiltration Detection  

---

## 1. Executive Summary: Covert Channels in Context Windows

In high-assurance autonomous agent environments, the context window serves as both the input perception bus and the output command bus. Malicious actors, rogue API plugins, and compromised RAG documents can exploit text-based covert channels to smuggle instructions, exfiltrate private tokens, or bypass safety boundaries:
1. **Zero-Width Unicode Injection**: Hiding secret commands using invisible characters (e.g., U+200B Zero-Width Space, U+200C ZWNJ, U+FEFF Byte Order Mark).
2. **Homoglyphic Substitution**: Bypassing token matching filters using lookalike Cyrillic or Greek glyphs (e.g., Latin 'a' vs. Cyrillic 'а').
3. **Whitespace & Punctuation Steganography**: Encoding binary payloads in trailing spaces, soft hyphens, or variable indentation.
4. **Statistical Token Watermarking**: Verifying that model outputs originate from certified corporate inference clusters rather than unauthorized shadow models.

This whitepaper details the enterprise architecture for automated steganography detection, context normalization (NFKC sanitization), and cryptographic token watermarking.

---

## 2. Threat Modeling: Steganographic Prompt Injection Vectors

```
+---------------------------------------------------------------------------------+
|                        STEGANOGRAPHIC INJECTION VECTORS                         |
+-------------------+---------------------+---------------------------------------+
| Attack Vector     | Unicode Characters  | Attack Mechanism                      |
+-------------------+---------------------+---------------------------------------+
| Zero-Width Bits   | U+200B (0),         | Binary payload encoded in invisible   |
|                   | U+200C (1)          | characters inside retrieved docs      |
+-------------------+---------------------+---------------------------------------+
| Homoglyphs        | U+0430 (Cyrillic a) | Masquerades as legitimate command     |
|                   | U+0435 (Cyrillic e) | but evades string-matching guardrails |
+-------------------+---------------------+---------------------------------------+
| Directional Bidi  | U+202E (RLO),       | Flips displayed text direction to     |
|                   | U+202B (RLE)        | mislead human reviewers in audit logs |
+-------------------+---------------------+---------------------------------------+
| Whitespace Run    | U+0020, U+00A0      | Tab/space parity encoding payload     |
+-------------------+---------------------+---------------------------------------+
```

---

## 3. The 4-Tier Automated Sanitization Gateway

Before any context fragment enters the Symphony prompt assembly pipeline, it must traverse the **Context Sanitization Gateway**:

```
   [ Raw Ingested Context / Tool Output ]
                     |
                     v
   +------------------------------------+
   | Tier 1: Invisible Unicode Stripper | ---> Strips U+200B, U+200C, U+FEFF, U+202E
   +------------------------------------+
                     |
                     v
   +------------------------------------+
   | Tier 2: Unicode NFKC Normalizer    | ---> Canonicalizes homoglyphs & ligature forms
   +------------------------------------+
                     |
                     v
   +------------------------------------+
   | Tier 3: Spectral Entropy Analyzer  | ---> Flags abnormal character frequency spikes
   +------------------------------------+
                     |
                     v
   +------------------------------------+
   | Tier 4: Watermark Signature Verifier| ---> Validates authorized green/red token hash
   +------------------------------------+
                     |
                     v
   [ Verified Clean Assembly Buffer ]
```

---

## 4. Statistical Token Watermarking (Kirchenbauer Protocol)

To guarantee verifiable provenance and prevent unauthorized synthetic data recycling:
1. **Hash Keying**: At token generation step $t$, the previous token $w_{t-1}$ is hashed with a secret enterprise key $K$:
   $$h = 	ext{HMAC-SHA256}(K, w_{t-1})$$
2. **Green/Red List Partitioning**: The vocabulary $V$ is pseudo-randomly partitioned into a "green list" $G$ of size $gamma |V|$ and a "red list" $R$ of size $(1-gamma)|V|$.
3. **Logit Biasing**: A positive bias $delta$ is added to the logits of green tokens:
   $$ell'_{t, i} = ell_{t, i} + delta quad 	ext{for } i in G$$
4. **Statistical Verification**: A test sequence of length $T$ containing $N_G$ green tokens is evaluated using the z-score:
   $$z = rac{N_G - gamma T}{sqrt{T gamma (1 - gamma)}}$$
   If $z > 4.0$, provenance is established with $p < 10^{-4}$.

---

## 5. Enterprise Compliance & Implementation Roadmap

1. **Gate 1**: Zero un-sanitized context buffers admitted into model inference.
2. **Gate 2**: Automated real-time alerts upon detection of hidden zero-width payloads.
3. **Gate 3**: Watermark verification on all customer-facing commercial outputs.

Instituting this architecture guarantees compliance with EU AI Act Article 50 transparency obligations and eliminates stealthy prompt injection attacks across the Symphony agent ecosystem.
