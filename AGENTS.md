# Codex Legalis Agent Context

## Project Purpose

Codex Legalis is an autonomous courtroom simulation for the **Global AI Hackathon (Qwen Cloud / Agent Society Track)**. It distributes legal labor across 9 specialized AI agents (Magistrate, Judge, Prosecutor, Defense Counsel, Witnesses, Fact Checker, Clerk, Jurors, Foreperson, Archivist) to conduct a full adversarial trial based on user-provided case facts.

The core goal is to demonstrate emergent societal behavior and rigorous legal reasoning through adversarial collaboration, rather than relying on a single LLM prompt for a verdict.

## Hackathon Constraints (STRICT)

1. **AI Models:** You MUST use Qwen models on Qwen Cloud for all AI functionality. Do not add OpenAI, Anthropic, Gemini, local non-Qwen models, or third-party model APIs for generation, transcription, speech, deliberation, summarization, or agent reasoning.
2. **LLM Integration:** Use `dashscope-intl.aliyuncs.com` compatible endpoints or the DashScope SDK.
3. **Deployment Proof:** The project must run on Alibaba Cloud services. Files like `src/llm.py` and `src/audio.py` serve as proof of this integration.

## Architecture & Tech Stack

This project uses a vanilla web stack. **Do NOT use or reference Streamlit.**

- **Backend:** FastAPI (`server.py`) serving static files and API routes.
- **Frontend:** Vanilla HTML/JS/CSS (`index.html` + `static/app.js`). The browser drives the trial via `POST /api/trial/step`.
- **Orchestration:** LangGraph `StateGraph` (`src/graph.py`) passing a typed `TrialState` (`src/state.py`).
- **Agents:** Node logic in `src/nodes.py`. Prompts in `src/prompts.py`. Orchestration helpers in `legalis/agents.py`.
- **Audio:** Qwen audio/omni models configured via `QWEN_AUDIO_MODEL` / `QWEN_AUDIO_MODELS` environment variables (`src/audio.py`).

## Agent Society & Model Assignments

Agents are assigned specific Qwen models (configured in `src/config.py`):

- **Magistrate** (`qwen-max`): Clarifying questions pre-trial.
- **Judge** (`qwen-max`): Rules on objections strictly based on jurisdiction evidence code.
- **Prosecutor & Defense Counsel** (`qwen-plus-latest`): Argumentation and witness examination.
- **Witnesses** (`qwen-flash`): Strict role-play from deposition facts.
- **Fact Checker** (`qwen-flash`): Intercepts witness hallucinations and triggers "Objection: Speculation".
- **Clerk** (`qwen-flash`): Compresses trial history into a Fact Sheet.
- **Jury Foreperson** (`qwen-plus-latest`): Leads deliberation and detects hung juries.
- **Archivist** (`qwen-turbo-latest`): Logs final outcomes.

## Product Behavior Rules

- **Zero Hallucination:** Never invent case facts, witness names, dates, exhibits, statutes, forensic findings, or procedural events. If a witness strays, the Fact Checker MUST catch it.
- **Insufficient Record Gate:** If facts are insufficient (< 8 words), agents must say the record is insufficient and ask for fuller particulars. Do not fabricate a case.
- **Jurisdiction-Aware:** The trial must respect the selected `jurisdiction_system` (Common vs Civil Law), `evidence_rules`, and `jury_enabled` boolean from the active `TrialState`.
- **Structured Outputs:** All routing decisions (Judge rulings, verdicts) must use `get_structured_llm` with Pydantic schemas to prevent state machine deadlocks.
- **API Keys:** No hardcoded secrets. Use `.env` with `QWEN_API_KEY`.
- **Documentation Sync:** Always update `README.md` and `Codex Legalis.md` if any architectural or feature changes are made so the documentation remains strictly up-to-date.
