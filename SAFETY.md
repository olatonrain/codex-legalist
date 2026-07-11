# Safety Guidelines

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
