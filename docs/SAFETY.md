# Safety Guidelines

This file covers safety guidelines, data handling limits, deployment guardrails, human-in-the-loop checkpoints, and agent guardrails.


This file covers safety guardrails only. See [SECURITY.md](SECURITY.md) for vulnerability reporting, dependency scanning, secrets handling, and authentication policy. Zero content overlap.

## Data Handling Limits

| Limit | Value |
|-------|-------|
| Max upload file size | 10 MB |
| Supported formats | PDF, DOCX, TXT, audio (WAV, MP3, etc.) |
| Audio transcription max duration | Model-dependent (varies by Qwen audio model) |
| Rate limit | 30 requests per 60 seconds per IP |

## Deployment Guardrails

- All LLM calls go through Qwen Cloud only (`dashscope-intl.aliyuncs.com`).
- No fallback to OpenAI, Anthropic, Gemini, or other third-party AI APIs.
- API keys stored in `.env` only — never hardcoded. `.env` is in `.gitignore`.
- Prompt injection detection runs on all user-supplied input before entering the trial graph.
- Insufficient record gate: if case facts < 8 words, system refuses to generate speculative content.

## Rollback Triggers

- If any trial step raises an unhandled exception, the state machine returns a 500 error with JSON detail.
- Container restarts are handled by Docker's `--restart unless-stopped` policy.
- Previous deployments can be restored by re-running the deploy script from an earlier git commit.

## Human-in-the-Loop Checkpoints

1. **Magistrate Review** — Before trial starts, the Magistrate agent asks clarifying questions. The human must provide answers.
2. **Human Input During Trial** — Agents can submit questions to the human via `POST /api/trial/human_question`. The trial pauses until the human responds via `POST /api/trial/human_answer`.
3. **Pending Question Gate** — If a question is pending, `POST /api/trial/step` returns the question without advancing the trial.

No automated decisions are made without at least one human input cycle per trial session.

## AI Safety Guardrails <!-- agent-updated -->

### Fact Checker Agent

A dedicated `qwen-plus-latest` agent acts as an automated guardrail against generative drift. Every witness statement is routed through a two-pass verification:

1. **Content check** — The Fact Checker compares the witness's testimony against the original case record. Any claim not supported by the admitted facts or evidence is flagged.
2. **Correction** — When a hallucination is detected, the witness is instructed to revise their statement to stay within the record.

Witnesses are explicitly constrained by their prompts to role-play strictly from their deposition facts. The Fact Checker provides a visible audit trail for every statement.

### Prompt Injection Defence

Before any user-provided input enters the trial graph, a `security_check` node (at `src/security.py`) scans for:

- Attempts to override system prompts or agent instructions
- Injection of delimiters designed to break out of the LLM's instruction bounds
- Pattern-matched malicious content

If a security violation is detected, the input is rejected with a `[CONTEMPT OF COURT]` response and the trial does not proceed.

### Insufficient Record Gate

If the provided case facts contain fewer than 8 words, the system refuses to generate speculative content. Instead of fabricating arguments from thin facts, the opening statements and evidence nodes return placeholder "insufficient record" responses. The trial continues in a reduced mode without speculative generation.

This gate is critical because LLMs are prone to invent plausible-sounding but entirely fictional case details when given minimal input. The gate prevents the system from building a trial on fabricated foundations.
