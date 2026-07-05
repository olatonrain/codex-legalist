# Codex Legalis — Project Reference Document

> This document is the authoritative technical and product reference for the Codex Legalis project.
> Keep it updated as the project evolves. AI assistants and contributors should treat it as ground truth.

---

## 1. Project Overview

**Codex Legalis** is a multi-agent courtroom simulation built for the **Global AI Hackathon — Track 3: Agent Society** (Qwen Cloud / Alibaba Cloud).

You submit a case file — a plain text description of facts, parties, and evidence — and the system runs a full adversarial trial autonomously. Before the trial begins, the **Magistrate** agent generates up to 5 strategic clarifying questions. After the user answers them, a panel of agents (Judge, Prosecutor, Defense Counsel, Witnesses, Clerk, Fact Checker, Jurors, Foreperson, and Archivist) conducts the trial through a procedural state machine. The trial concludes with a verdict and a **shadow jury simulation** that computes the prosecution's win probability across multiple independent jury panels.

**Core differentiators for Track 3:**

- True adversarial collaboration — opposing roles with structured conflict and resolution.
- Emergent societal behavior — jury deliberation, hung juries, objection rulings, and witness cross-examination emerge from agent interactions, not pre-scripted logic.
- Human-in-the-loop at the right level — up to 5 pre-trial clarifying questions; the society handles the rest.
- Measurable output — win-likelihood is grounded in repeated shadow jury simulation, not a single model confidence score.
- Jurisdiction-aware — the trial adapts its procedure, evidence rules, court address, jury eligibility, and legal standard to the selected country.

---

## 2. Tech Stack

| Layer                | Technology                                                           |
| -------------------- | -------------------------------------------------------------------- |
| LLM Backend          | Qwen Cloud via OpenAI-compatible API (`dashscope-intl.aliyuncs.com`) |
| Agent Orchestration  | LangGraph (Python) — `StateGraph` with typed `TrialState`            |
| Backend Server       | FastAPI + Uvicorn                                                    |
| Frontend             | Vanilla HTML + CSS + JavaScript (`index.html` + `static/app.js`)     |
| LLM Client Wrapper   | `langchain-openai` (`ChatOpenAI` pointed at Qwen endpoint)           |
| Audio Transcription  | Qwen Audio / Qwen Omni models via DashScope SDK                      |
| Document Parsing     | `pypdf`, `python-docx`, `lxml` (case file upload)                    |
| Containerisation     | Docker / `docker-compose` (via `deploy.sh`)                          |
| Monitoring / Logging | Python `logging`, structured transcript entries                      |

**Hard constraint:** All LLM inference — chat, audio transcription, deliberation, summarisation — must use Qwen models on Qwen Cloud. No OpenAI, Anthropic, Gemini, Whisper, or local non-Qwen models.

---

## 3. Actual Directory Structure

```
codex-legalis/
├── index.html              # Main UI — served by FastAPI at GET /
├── server.py               # FastAPI application entrypoint
├── deploy.sh               # Virtualenv setup + run helper
├── requirements.txt        # Python dependencies
├── .env                    # API keys (not committed)
├── .env.example            # Template for .env
├── README.md               # Public-facing project README
├── Codex Legalis.md        # Authoritative technical reference document
├── AGENTS.md               # AI assistant context and project rules
├── LICENSE                 # Open-source licence (required for hackathon)
├── Makefile                # Setup, test, lint, run targets
├── pytest.ini              # Pytest configuration
├── benchmark.py            # Benchmark: raw LLM vs single-agent vs multi-agent
├── test_graph.py           # Integration test — full LangGraph execution
├── test_trial_safety.py    # Safety tests — insufficient record gate, routing
│
├── src/                    # Core Python backend
│   ├── state.py            # TrialState TypedDict — single source of truth for trial data
│   ├── graph.py            # LangGraph StateGraph definition, nodes, and conditional edges
│   ├── nodes.py            # All agent node functions (magistrate, judge, jury, etc.)
│   ├── prompts.py          # Agent system prompt templates
│   ├── llm.py              # Qwen Cloud LLM client factory (get_llm, get_structured_llm)
│   ├── audio.py            # Qwen-only audio transcription and TTS helpers
│   ├── config.py           # AGENT_MODELS dict, JURISDICTIONS registry, COUNTRY_LIST
│   ├── security.py         # Prompt injection detection
│   └── logger.py           # Structured logging helper
│
├── legalis/                # Trial orchestration layer
│   ├── __init__.py
│   ├── agents.py           # generate_dramatic_opening(), run_trial_step(), helpers
│   ├── data.py             # DEMO_CASES, AGENT_STYLE, AGENT_NAME_COLOR
│   └── parser.py           # extract_text() — parses PDF, DOCX, TXT uploads
│
├── tests/                  # Pytest test suite
│   ├── conftest.py         # Shared fixtures (mock_state, mock_llm, mock_structured_llm)
│   ├── test_nodes.py       # Node function tests (opening, evidence, security, magistrate)
│   ├── test_agents.py      # Agent helper tests (norm_agent, sanitise, run_trial_step)
│   ├── test_server.py      # FastAPI endpoint tests (health, jurisdictions, upload, trial)
│   ├── test_security.py    # Prompt injection detection tests
│   └── test_parser.py      # File parser tests (TXT, PDF, DOCX)
│
├── docs/                   # Supplementary documentation
│   └── ALIBABA_CLOUD_PROOF.md
│
└── static/                 # Static frontend assets served at /static/*
    └── app.js              # Browser runtime, state machine driver, UI logic
```

---

## 4. Agent Society Architecture

### 4.1 Agent Roles

| Agent               | Role                                                                                                               | Model Assigned                  |
| ------------------- | ------------------------------------------------------------------------------------------------------------------ | ------------------------------- |
| **Magistrate**      | Generates between 1 and 5 strategic clarifying questions; identifies named witnesses and missing evidence/witnesses | `qwen-max`                      |
| **Judge**           | Rules on objections (SUSTAINED / OVERRULED with cited rationale); instructs jury                                   | `qwen-max`                      |
| **Prosecutor**      | Opens case, presents evidence, examines prosecution witnesses, cross-examines defense witnesses                    | `qwen-plus-latest`              |
| **Defense Counsel** | Challenges evidence, examines defense witnesses, cross-examines prosecution witnesses                              | `qwen-plus-latest`              |
| **Witnesses**       | Role-play strictly from their deposition; cannot invent facts; say "I don't recall" if asked outside their record  | `qwen-flash`                    |
| **Fact Checker**    | Intercepts witness answers; triggers "Objection: Speculation" if witness invents facts outside their source text   | `qwen-flash`                    |
| **Clerk**           | Compresses running trial history into a Fact Sheet and Admitted/Excluded Evidence list to prevent context overflow | `qwen-flash`                    |
| **Jury Foreperson** | Leads jury deliberation; manages voting rounds; detects hung jury after 3 rounds                                   | `qwen-plus-latest`              |
| **Jurors (3–5)**    | Diverse personalities; deliberate privately on the compressed case summary + judge's instructions                  | _(spawned by shadow jury node)_ |
| **Archivist**       | Logs key rulings and precedents; runs at end of trial as the final node                                            | `qwen-turbo-latest`             |

Agent models are configured in `src/config.py → AGENT_MODELS`.

### 4.2 State Machine — Trial Phases

Defined in `src/graph.py` using LangGraph `StateGraph`:

```
security_check
    ↓ (pass) → magistrate → human_input → opening_statements → evidence
                                                                    ↓
                                                        witness_examination ⟲ (loop until queue empty)
                                                                    ↓
                                                         closing_arguments → jury_instructions
                                                                                  ↓
                                                                      jury_deliberation ⟲ (up to 3 rounds)
                                                                                  ↓
                                                                          shadow_jury → archivist → END
    ↓ (fail)  → archivist → END
```

**Conditional edge logic:**

- `security_check` → if prompt injection detected, short-circuits to `archivist` (trial ends immediately).
- `witness_examination` → loops until `witness_queue` is empty, then proceeds to closing arguments.
- `jury_deliberation` → loops until `main_verdict` is set or `deliberation_rounds >= 3` (hung jury / mistrial).

### 4.3 Jurisdiction-Aware Behaviour

The `TrialState` carries a full jurisdiction context loaded from `JURISDICTIONS` in `src/config.py`:

| Field                    | Example (Nigeria)                        |
| ------------------------ | ---------------------------------------- |
| `jurisdiction_system`    | `"Common Law"`                           |
| `jurisdiction_procedure` | `"adversarial"`                          |
| `criminal_standard`      | `"Beyond reasonable doubt"`              |
| `civil_standard`         | `"Balance of probabilities"`             |
| `evidence_rules`         | `"Evidence Act 2011; ACJA 2015"`         |
| `jury_enabled`           | `False` (Nigeria abolished jury trials)  |
| `cross_examination`      | `True`                                   |
| `court_address`          | `"My Lord / Your Lordship (High Court)"` |

If `jury_enabled` is `False`, the Judge delivers the verdict directly (bench trial) and the Jury Instructions / Jury Deliberation phases are skipped.

Supported jurisdictions include: Nigeria, United Kingdom, United States, Ghana, Kenya, South Africa, France, Germany, and more — see `src/config.py` for the full registry.

---

## 5. API Endpoints (FastAPI — `server.py`)

| Method | Path                       | Description                                                                                         |
| ------ | -------------------------- | --------------------------------------------------------------------------------------------------- |
| `GET`  | `/`                        | Serves `index.html` (main UI)                                                                       |
| `GET`  | `/static/*`                | Serves static assets (JS, CSS)                                                                      |
| `GET`  | `/api/health`              | Health check — returns `{"status": "ok"}`                                                           |
| `GET`  | `/api/jurisdictions`       | Returns full jurisdiction registry for the UI country picker                                        |
| `POST` | `/api/demo`                | Load a pre-scripted demo case; returns full `script` array for client-side streaming                |
| `POST` | `/api/upload`              | Parse uploaded case file (PDF, DOCX, TXT) via `legalis/parser.py`                                   |
| `POST` | `/api/upload_audio`        | Transcribe uploaded audio using Qwen audio/omni model                                               |
| `POST` | `/api/trial/magistrate`    | Run Magistrate node — returns up to 5 clarifying questions + witness queue + missing items          |
| `POST` | `/api/trial/start`         | Initialise live trial state; generates dramatic courtroom opening sequence via AI                   |
| `POST` | `/api/trial/step`          | Advance trial by one phase step; returns new transcript entries, updated state, and next phase name |
| `POST` | `/api/trial/human_question`| Agent submits a question to the human during trial                                                  |
| `POST` | `/api/trial/human_answer`  | Human submits an answer to an agent's pending question                                              |
| `POST` | `/api/benchmark/run`       | Run benchmark comparing raw LLM vs single-agent vs multi-agent                                      |

### Trial Step Cycle (live mode)

The browser drives the trial step-by-step by calling `POST /api/trial/step` repeatedly:

```
Client sends: { "live_step": "opening", "graph_state": {...} }
Server returns: { "messages": [...], "graph_state": {...}, "next_step": "evidence" }

Client sends: { "live_step": "evidence", "graph_state": {...} }
...
Server returns: { ..., "next_step": "done", "verdict_data": { verdict, probability, sensitivity, juries } }
```

When `next_step == "done"`, `verdict_data` is included with the final verdict, win probability, and sensitivity summary.

---

## 6. TrialState Shape

Defined in `src/state.py` as a `TypedDict`:

```python
class TrialState(TypedDict):
    case_description: str
    transcript: List[BaseMessage]
    # Jurisdiction
    country: str
    jurisdiction_system: str
    jurisdiction_procedure: str
    criminal_standard: str
    civil_standard: str
    evidence_rules: str
    jury_enabled: bool
    cross_examination: bool
    court_address: str
    case_type: str                    # "Criminal" or "Civil"
    # Clerk's state compression
    fact_sheet: str
    admitted_evidence: List[str]
    excluded_evidence: List[str]
    # Pre-trial
    clarifying_questions: List[Dict[str, str]]
    human_answers: Dict[str, str]
    missing_evidence_answers: Dict[str, str]
    missing_witnesses_answers: Dict[str, str]
    # Live human input during trial
    pending_human_question: Optional[Dict[str, str]]
    human_input_buffer: List[Dict[str, str]]
    # Witness tracking
    witness_queue: List[str]
    current_witness: Optional[str]
    examination_phase: Optional[str]  # "direct", "cross", or "redirect"
    # Config
    shadow_jury_count: int
    shadow_jury_model: str
    jury_count: int                   # Main jury panel size (default 12)
    audio_enabled: bool
    # Outcomes
    deliberation_rounds: int
    jury_profiles: List[Dict[str, Any]]
    deliberation_snapshot: Dict[str, Any]
    main_verdict: Optional[str]
    shadow_jury_results: Dict[str, Any]
    multimodal_evidence: list
    errors: List[str]
```

---

## 7. LLM Client

All agent calls go through `src/llm.py`:

```python
get_llm(temperature=0.7, model="qwen-max")
    # Returns ChatOpenAI(
    #     base_url="https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
    #     api_key=os.getenv("QWEN_API_KEY"),
    #     model=model
    # )

get_structured_llm(schema, temperature=0.1, model="qwen-max")
    # Returns llm.with_structured_output(schema) — JSON mode for routing decisions
```

Routing decisions (judge rulings, jury verdicts, magistrate output) use `get_structured_llm` with Pydantic schemas (`JudgeRuling`, `JuryVerdict`, `MagistrateOutput`, `ClerkOutput`) to guarantee parseable JSON and prevent trial deadlocks from malformed LLM responses.

---

## 8. Audio Transcription

Defined in `src/audio.py`. Uses only Qwen audio/omni models via the DashScope SDK.

Configuration via environment variables:

```bash
QWEN_AUDIO_MODEL=qwen-omni-turbo                                      # single model
QWEN_AUDIO_MODELS=qwen-omni-turbo,qwen3-omni-flash,qwen-audio-turbo  # fallback chain
```

If no configured model is available on the account, the server returns a clear error message. It never silently falls back to Whisper or any other non-Qwen transcription service.

---

## 9. Frontend

The UI is a **single-page vanilla HTML/CSS/JS application** served at `GET /` by FastAPI. There is no Streamlit, no React, and no separate frontend build step.

- **`index.html`** — full courtroom UI markup (Deep Navy + Gold palette; Playfair Display headings, Inter body font; dark mode toggle).
- **`static/app.js`** — browser runtime that:
  - Drives the live trial step-by-step by calling `/api/trial/step` sequentially.
  - Streams demo scripts from the pre-loaded `script` array for demo mode (no extra API calls).
  - Displays a live scrolling transcript with per-agent colour coding.
  - Shows the Evidence Board (admitted ✅ / excluded ❌), Agent Roster (currently speaking agent), and Jury Monitor (vote rounds).
  - Renders the final verdict dashboard: verdict banner, win-probability gauge, sensitivity summary.

---

## 10. Demo Cases

Pre-scripted demo cases are stored in `legalis/data.py → DEMO_CASES`. Each entry contains:

```python
{
    "title": "...",
    "jurisdiction": "...",
    "description": "...",
    "questions": [...],        # pre-scripted magistrate questions
    "verdict": "...",
    "win_probability": 0.72,
    "sensitivity": "...",
    "trial_script": [...]      # ordered list of transcript entries for client-side streaming
}
```

Current demo keys: `"theft"`, `"contract"`. Extend `DEMO_CASES` to add more.

---

## 11. Coding Rules

- **Type hints required** on all Python functions.
- **No hardcoded secrets** — API keys live in `.env` only; `QWEN_API_KEY` is loaded at startup.
- **Retry logic** — Qwen API calls must wrap errors with exponential backoff (`try/except` in node functions).
- **Structured outputs** — all agent decisions that route state (verdict, objection ruling, magistrate output) must use `get_structured_llm` with a Pydantic schema.
- **Character consistency** — no agent may break the fourth wall, claim to be AI, or reference information outside the case file, admitted evidence, or running transcript.
- **Anti-hallucination** — witnesses are constrained to their deposition; the Fact Checker node intercepts speculative answers automatically.
- **Fact sufficiency gate** — if the submitted case description is fewer than 8 meaningful words, the opening statements node returns an "insufficient record" response from both sides instead of generating fabricated facts.
- **Logging** — all agent utterances are logged with `agent_id`, `phase`, and `timestamp`.

---

## 12. Environment Variables

| Variable            | Purpose                                                 |
| ------------------- | ------------------------------------------------------- |
| `QWEN_API_KEY`      | Primary key for Qwen Cloud (chat completions and audio) |
| `DASHSCOPE_API_KEY` | Alternative key name accepted by the audio module       |
| `QWEN_AUDIO_MODEL`  | Single Qwen audio/omni model to use for transcription   |
| `QWEN_AUDIO_MODELS` | Comma-separated fallback chain of audio model names     |

See `.env.example` for a ready-to-copy template.

---

## 13. Running Locally

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Configure environment
cp .env.example .env
# Edit .env and set: QWEN_API_KEY=<your-key>

# 3. Start the server
uvicorn server:app --reload --port 8000

# 4. Open the UI in your browser
# http://localhost:8000
```

---

## 14. Hackathon Submission Checklist

- [x] All LLM inference uses Qwen Cloud (chat + audio)
- [x] Backend runs on Alibaba Cloud (proof: `deploy.sh` + live API endpoint)
- [x] Public open-source repository with licence file
- [ ] Architecture diagram added to README
- [ ] Demo video (< 3 minutes) uploaded to YouTube / Vimeo / Youku
- [x] Track 3: Agent Society selected on the Devpost submission form
- [ ] Blog / social post (optional — qualifies for the $1,000 Blog Post bonus prize)
