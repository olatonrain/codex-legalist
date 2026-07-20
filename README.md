# Codex legalist — Autonomous Courtroom Simulation

> A Qwen Cloud Agent Society that runs a full, adversarial legal trial.

![Qwen](https://img.shields.io/badge/Qwen-Cloud-blue?logo=alibabacloud&logoColor=white&style=flat-square)
![LangGraph](https://img.shields.io/badge/Orchestration-LangGraph-orange?style=flat-square)
![FastAPI](https://img.shields.io/badge/Backend-FastAPI-green?logo=fastapi&logoColor=white&style=flat-square)
![JS](https://img.shields.io/badge/Frontend-Vanilla_JS-yellow?logo=javascript&logoColor=black&style=flat-square)

**Codex legalist** distributes legal labour across 11 specialised Qwen agents — Magistrate, Judge, Prosecutor, Defence Counsel, Witnesses, Fact Checker, and a full Jury — who debate, object, testify, and deliberate autonomously on user-provided case facts. The result is a Shadow Jury Simulation that computes a mathematically grounded win-probability, not a single model's guess.

---

## Features <!-- agent-updated -->

- **11-Agent Society:** Magistrate, Judge, Prosecutor, Defence Counsel, Witness Panel, Fact Checker, Clerk, Jury Foreperson, Jury Panel, Shadow Juries, and Archivist role-playing in an adversarial arena.
- **Dynamic Evidence & Objection Engine:** Prosecution and Defence argue admissibility based on jurisdiction rules; Judge rules live to admit/exclude.
- **Fact-Checking Guardrails:** Active `qwen-plus` Fact Checker intercepts witness testimonies to prevent model hallucinations and enforce boundary facts.
- **Multilingual Jurisdictions:** Adapts procedural rules, evidence acts, and burdens of proof across 16 adversarial, inquisitorial, and mixed legal systems.
- **Shadow Jury Simulation:** Spawns 5–50 parallel independent juries to run statistical consensus analysis and compute an objective win-probability.
- **On-Demand Counsel Insights:** Post-trial strategic advisory giving constructive defense, prosecution, and judicial guidance based on the trial outcome.
- **Benchmarking Engine:** Direct comparison tool contrasting Raw LLM queries vs. Single-Agent vs. Codex legalist Agent Society with SSE live streaming progress.

---

## Hackathon Track

**Qwen Cloud Global AI Hackathon — Track 3: Agent Society**

---

## Live Demo

**🟢 Play with the live deployment here:** [http://47.237.180.168:8000](http://47.237.180.168:8000)

_(Hosted on Alibaba Cloud ECS)_

**Backup (Vercel):** [https://codex-legalist.vercel.app/](https://codex-legalist.vercel.app/)

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

## Documentation <!-- agent-updated -->

| Document                                       | Description                                               |
| ---------------------------------------------- | --------------------------------------------------------- |
| [Architecture](docs/ARCHITECTURE.md)           | System diagram, tech stack, agent roles, trial phases     |
| [Usage & API Guide](docs/USAGE.md)             | How to run trials, demo cases, file upload, API reference |
| [Benchmark System](docs/BENCHMARK.md)          | Raw LLM vs Single-Agent vs Codex legalist comparison      |
| [Alibaba Cloud Deployment](docs/DEPLOYMENT.md) | Deployment process, environment config, DashScope setup   |
| [Safety Guidelines](docs/SAFETY.md)            | Data limits, Fact Checker, prompt injection defense       |
| [Security Policy](SECURITY.md)                 | Vulnerability reporting, secrets handling, rate limits    |

---

## Sample Cases

Ready-to-upload case files for testing. See [sample_cases/](sample_cases/) for a variety of criminal and civil scenarios across multiple jurisdictions.

---

## License

MIT — anyone may use, modify, and distribute this software for any purpose, commercial or private. Attribution is required. The software is provided without warranty. See [LICENSE](LICENSE) for the full terms.
