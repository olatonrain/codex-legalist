# Safety

Codex Legalis implements three layers of safety guardrails to prevent hallucinations, prompt injection, and fabrication from insufficient facts.

---

## Fact Checker Agent

A dedicated `qwen-plus-latest` agent acts as an automated guardrail against generative drift. Every witness statement is routed through a two-pass verification:

1. **Content check** — The Fact Checker compares the witness's testimony against the original case record. Any claim not supported by the admitted facts or evidence is flagged.
2. **Correction** — When a hallucination is detected, the witness is instructed to revise their statement to stay within the record.

Witnesses are explicitly constrained by their prompts to role-play strictly from their deposition facts. The Fact Checker provides a visible audit trail for every statement.

---

## Prompt Injection Defence

Before any user-provided input enters the trial graph, a `security_check` node (at `src/security.py`) scans for:

- Attempts to override system prompts or agent instructions
- Injection of delimiters designed to break out of the LLM's instruction bounds
- Pattern-matched malicious content

If a security violation is detected, the input is rejected with a `[CONTEMPT OF COURT]` response and the trial does not proceed.

---

## Insufficient Record Gate

If the provided case facts contain fewer than 8 words, the system refuses to generate speculative content. Instead of fabricating arguments from thin facts, the opening statements and evidence nodes return placeholder "insufficient record" responses. The trial continues in a reduced mode without speculative generation.

This gate is critical because LLMs are prone to invent plausible-sounding but entirely fictional case details when given minimal input. The gate prevents the system from building a trial on fabricated foundations.
