# Codex Legalis — Autonomous Courtroom Simulation

> A Qwen Cloud Agent Society that runs a full, adversarial legal trial.

**Codex Legalis** distributes legal labour across 11 specialised Qwen agents — Magistrate, Judge, Prosecutor, Defence Counsel, Witnesses, Fact Checker, and a full Jury — who debate, object, testify, and deliberate autonomously on user-provided case facts. The result is a Shadow Jury Simulation that computes a mathematically grounded win-probability, not a single model's guess.

---

## Hackathon Track

**Qwen Cloud Global AI Hackathon — Track 3: Agent Society**

---

## Live Demo

**🟢 Play with the live deployment here:** [http://47.237.180.168:8000](http://47.237.180.168:8000)

*(Hosted on Alibaba Cloud ECS)*

---

## Demo Video

*Link to be added*

---

## Blog Post

*Link to be added*

---

## Quickstart

```bash
git clone https://github.com/olatonrain/codex-legalis.git
cd codex-legalis

cp .env.example .env
# Edit .env and add your QWEN_API_KEY

./deploy.sh
```

Open [http://localhost:8000](http://localhost:8000).

---

## Documentation

| Document | Description |
|----------|-------------|
| [Architecture](docs/ARCHITECTURE.md) | System diagram, tech stack, agent roles, trial phases |
| [Deployment](docs/DEPLOYMENT.md) | Alibaba Cloud proof, Qwen Cloud config, compliance |
| [Benchmark](docs/BENCHMARK.md) | Raw LLM vs Single-Agent vs Codex Legalis comparison |
| [Usage](docs/USAGE.md) | How to run trials, demo cases, file upload, API reference |
| [Safety](docs/SAFETY.md) | Anti-hallucination, prompt injection defence, record gates |

---

## Sample Cases

Ready-to-upload case files for testing. See [sample_cases/](sample_cases/) for a variety of criminal and civil scenarios across multiple jurisdictions.

---

## License

MIT — anyone may use, modify, and distribute this software for any purpose, commercial or private. Attribution is required. The software is provided without warranty. See [LICENSE](LICENSE) for the full terms.

MIT was chosen because it is permissive for open-source adoption, satisfies the hackathon's open-source licensing requirement, and places no restrictions on downstream use.
