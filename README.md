# Codex legalist — Autonomous Courtroom Simulation

> A Qwen Cloud Agent Society that runs a full, adversarial legal trial.

**Codex legalist** distributes legal labour across 11 specialised Qwen agents — Magistrate, Judge, Prosecutor, Defence Counsel, Witnesses, Fact Checker, and a full Jury — who debate, object, testify, and deliberate autonomously on user-provided case facts. The result is a Shadow Jury Simulation that computes a mathematically grounded win-probability, not a single model's guess.

---

## Hackathon Track

**Qwen Cloud Global AI Hackathon — Track 3: Agent Society**

---

## Live Demo

**🟢 Play with the live deployment here:** [http://47.237.180.168:8000](http://47.237.180.168:8000) and also at [https://codex-legalist.vercel.app/](https://codex-legalist.vercel.app/)

_(Hosted on Alibaba Cloud ECS)_

---

## Demo Video

[![Codex legalist Demo](https://img.youtube.com/vi/hwRAtOsYiWk/0.jpg)](https://youtu.be/hwRAtOsYiWk)

---

## Blog Post

[Codex legalist - Qwen Hackathon Project](https://www.linkedin.com/posts/xa4real_qwencloud-alibabacloud-hackathon-ugcPost-7480464001672396800-F13t/?utm_source=share&utm_medium=member_ios&rcm=ACoAABJy-eYBMgamdm81HKCISLctT4zLcALuoSo)

---

## Quickstart

```bash
git clone https://github.com/olatonrain/codex-legalist.git
cd codex-legalist

cp .env.example .env
# Edit .env and add your QWEN_API_KEY

./deploy.sh
```

Open [http://localhost:8000](http://localhost:8000).

---

## Documentation

| Document                     | Description                                                |
| ---------------------------- | ---------------------------------------------------------- |
| [Architecture](ARCHITECTURE.md) | System diagram, tech stack, agent roles, trial phases      |
| [Deployment](DEPLOY_GUIDE.md)   | Deployment process, environment config, CI/CD              |
| [Agents](AGENTS.md)          | AI agent rules, session protocol, documentation sync       |
| [Memory](MEMORY.md)          | Project memory tracking (decisions, blockers, next steps)  |
| [Changelog](CHANGELOG.md)    | Version history with date-based entries                    |
| [Contributing](CONTRIBUTING.md) | Code conventions, PR workflow, testing                    |
| [Benchmark](docs/BENCHMARK.md) | Raw LLM vs Single-Agent vs Codex legalist comparison       |
| [Usage](docs/USAGE.md)       | How to run trials, demo cases, file upload, API reference  |
| [Safety](SAFETY.md)          | Data handling limits, deployment guardrails, human-in-the-loop checkpoints |
| [Security](SECURITY.md)      | Vulnerability reporting, secrets handling, auth policy |

---

## Sample Cases

Ready-to-upload case files for testing. See [sample_cases/](sample_cases/) for a variety of criminal and civil scenarios across multiple jurisdictions.

---

## License

MIT — anyone may use, modify, and distribute this software for any purpose, commercial or private. Attribution is required. The software is provided without warranty. See [LICENSE](LICENSE) for the full terms.

MIT was chosen because it is permissive for open-source adoption, satisfies the hackathon's open-source licensing requirement, and places no restrictions on downstream use.
