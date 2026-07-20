# Security Policy

This file covers security policies only. See [SAFETY.md](docs/SAFETY.md) for data handling limits, deployment guardrails, rollback triggers, and human-in-the-loop checkpoints. Zero content overlap.

## Reporting a Vulnerability

If you discover a security issue, do **not** open a public issue. Send details privately to the project maintainers via GitHub's security advisory feature or a direct message.

## Dependency Scanning

Dependencies are listed in `requirements.txt`. No automated dependency scanning is currently configured. Update dependencies regularly:

```bash
pip install --upgrade -r requirements.txt
```

## Secrets Handling

- API keys stored in `.env` — never hardcoded.
- `.env` is in `.gitignore` and never committed.
- Key rotation: rotate `QWEN_API_KEY` immediately if exposed.
- Consider adding a pre-commit hook (e.g., gitleaks, detect-secrets) to prevent accidental secret commits.
- Only Qwen Cloud (DashScope) endpoints are used — no third-party AI API keys.

## Authentication & Authorization

- No user authentication is currently implemented. The API is designed for local/private deployment.
- Rate limiting (30 req/60s per IP) is enforced via middleware in `server.py` as a basic abuse-prevention measure.
- All API endpoints return JSON only — no HTML responses to prevent XSS vectors.
- CORS is configured with `allow_origins=["*"]` — relax this in production to specific origins.
