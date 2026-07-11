# Changelog

All notable changes to this project will be documented here.

## 2026-07-11 (session 5)

### Added
- **Benchmark streaming progress** — `GET /api/benchmark/run-stream` SSE endpoint yields real-time events per approach/run; frontend displays inline progress with actual response snippets
- **Single-Agent sample card** — benchmark results now show Single-Agent verdict, reasoning, and metrics alongside Raw LLM and Codex legalist
- **`trial_context` support** — benchmark functions accept optional trial record; raw LLM and single-agent get enriched prompts; multi-agent skips re-running and extracts metrics from existing trial
- **`hasCompletedTrial()`** helper — gates "Run Live" button behind existing trial with transcript + verdict

### Changed
- **Counsel Insights moved** — verdict view reordered to position 2 (right after Jury Vote Breakdown, before Shadow Jury Room)
- **Benchmark CLI hint removed** — `python benchmark.py --mock` code block deleted from UI
- `BenchmarkRequest` model updated with optional `trial_context` field

## 2026-07-11 (session 4)

### Fixed
- **Module load failure** — three bugs fixed in ES module split:
  - `SAMPLE` in state.js export list (not defined in source) — removed phantom export
  - `initTheme` in state.js export list (named IIFE, not a module binding) — removed from exports and all import statements
  - `JX_DATA` reassignment in ui.js `loadJurisdictions` (imported bindings are read-only in ES modules) — changed to `Object.assign`
- **Insight functions missing** — `requestInsights`, `renderInsightResults`, `initInsightButtons`, `toggleInsightExpand` added to jury.js (were never in committed app.js, only in session 2's lost working tree)

### Added
- `src/__init__.py` — makes `src/` a regular package (was implicit namespace, caused Vercel import failures)

## 2026-07-11 (session 3)

### Changed
- **Phase 4 — Module Split**: `static/app.js` split into 6 ES module files using `acorn` AST-based extraction (reliable brace matching)
  - `static/state.js` — State, globals, helpers, constants, theme
  - `static/transcript.js` — transcript management
  - `static/evidence.js` — evidence display
  - `static/jury.js` — jury, verdict, deliberation, charts, counsel insights
  - `static/ui.js` — all remaining UI functions
  - `static/app.js` — 59-line entry point importing from all modules
- `index.html` script tag changed to `<script type="module" src="/static/app.js">`

### Added (session 1 — moved to jury.js)
- 4 insight JS functions — `requestInsights()`, `renderInsightResults()`, `initInsightButtons()`, `toggleInsightExpand()`

### Removed
- `_split_appjs.py` — buggy regex-based module split script (deleted in session 2)
- `_acorn_split.mjs` — helper script, deleted after successful split

## 2026-07-11 (session 2)

### Added
- 4 insight JS functions inlined to `static/app.js` — `requestInsights()`, `renderInsightResults()`, `initInsightButtons()`, `toggleInsightExpand()`

### Removed
- `_split_appjs.py` — buggy module split script; regex-based extraction corrupted function bodies
- `static/{state,transcript,evidence,jury,ui}.js` — generated modules had syntax errors (missing closing braces); monolithic app.js kept

## 2026-07-11 (session 1)

### Added
- **Counsel Insights** — on-demand post-trial strategic advice from Defense, Prosecution, and Judge perspectives
  - `src/insight.py`: context truncation, LLM generation, cache key computation
  - `POST /api/trial/insight` endpoint with in-memory caching and per-perspective error handling
  - `CounselInsight` and `InsightResponse` schemas in `src/schemas.py`
  - 3 insight prompts (defense, prosecution, judge) in `src/prompts.py`
  - UI in verdict view: perspective checkbox selector, generate button, loading state, collapsible results
  - Judge's Counsel collapsed by default; 0.35 temperature for factual consistency
- ruff (pyproject.toml) — Python linting and formatting tooling, replaces flake8
- package.json — frontend tooling with eslint + prettier
- `.prettierrc` and `eslint.config.js` — frontend lint/format configs
- `src/schemas.py` — extracted 18 Pydantic models from monolithic nodes.py
- `src/trial_phases.py` — trial flow node functions (security, magistrate, discovery, motions, opening, closing, reporter, archivist)
- `src/evidence.py` — evidence presentation, objections, rebuttal nodes
- `src/witness.py` — witness examination nodes (direct, cross, redirect)
- `src/jury.py` — jury profiles, deliberation, shadow jury, sentencing nodes
- `static/styles.css` — extracted ~2000 lines of inline CSS from index.html
- Deprecation banner on Streamlit UI (app.py) directing to FastAPI frontend
- Startup API key check — warns if QWEN_API_KEY is not set
- Configurable CORS origins via `CORS_ORIGINS` env var
- SAFETY.md — data handling limits, deployment guardrails, rollback triggers, human-in-the-loop checkpoints

- Detailed agent rules: mandatory session protocol, archive policy, patch-not-overwrite, uncertainty rule, SECURITY/SAFETY boundary, agent boundaries, exploration scope
<!-- agent-updated -->

### Changed
- SECURITY.md — narrowed to vulnerability reporting, dependency scanning, secrets handling, auth policy only (zero overlap with SAFETY.md)
- MEMORY.md — restructured to top-most-recent-first format (newest entries at top)
- AGENTS.md — upgraded with all new rules per specification
- CONTRIBUTING.md — updated with verified commands from Makefile/requirements.txt
- README.md — added SAFETY.md reference in doc table

## 2026-07-11 (earlier)

### Added
- Project documentation suite: AGENTS.md, MEMORY.md, CHANGELOG.md, CONTRIBUTING.md, SECURITY.md, ARCHITECTURE.md, DEPLOY_GUIDE.md
- Standardized MEMORY.md 5-field format
- Standardized CHANGELOG.md date-based category-tagged format
- Skill usage rules and session protocol for AI agents

### Changed
- Restructured README.md with comprehensive project overview
- Moved ARCHITECTURE.md from `docs/` to project root
- Moved deployment documentation to root-level DEPLOY_GUIDE.md
- Updated AGENTS.md with documentation sync table and escalation rule

## Previous Releases

See `docs/` for earlier documentation and git history for detailed change log prior to 2026-07-11.
