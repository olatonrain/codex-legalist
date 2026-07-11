# MEMORY — Codex legalist

## Last Session
2026-07-11 (session 5) — Benchmark improvements + Counsel Insights placement + SSE streaming. Full session completed with all 118 tests passing.

## Done
- **Counsel Insights moved to position 2** — verdict view HTML reordered: verdict card → jury breakdown → Counsel Insights → shadow jury → sentencing → charts
- **"Run Live" gated** — `hasCompletedTrial()` in ui.js checks `State.graphState` for transcript + verdict; Live button blocked with toast if no trial exists
- **Single-Agent sample card** — added to benchmark results HTML and `renderBenchmarkView()` JS (was missing, only Raw LLM and Codex legalist were shown)
- **Benchmark uses trial record** — `legalist/benchmark.py`:
  - `extract_benchmark_context()` formats existing trial record for prompt injection
  - `run_raw_llm_query()` and `run_single_agent_trial()` accept optional `trial_context`; prompts enriched with full trial record when provided
  - `run_multi_agent_trial()` skips graph invoke when `trial_context` is provided; extracts metrics directly (verdict, transcript length, hallucinations, evidence citations, shadow jury consensus)
  - CLI `run_benchmark()` passes `trial_context` through
- **SSE streaming endpoint** — `GET /api/benchmark/run-stream` in server.py yields events (`raw_llm_start`, `raw_llm_done`, `single_start`, `single_done`, `multi_result`, `complete`) for real-time progress
- **Frontend SSE consumer** — `runBenchmark()` uses `EventSource` to connect to streaming endpoint; progress panel shows each step inline with actual response snippets; closes on `complete` and renders final benchmark view
- **CLI hint removed** — `python benchmark.py --mock` code block deleted from benchmark UI

## Decisions
- SSE streaming over polling — simpler implementation, real-time updates, no extra state management
- Multi-agent skips graph for existing trials — seconds instead of 5-10 min per benchmark run; existing trial is the "baseline" for comparison
- `trial_context` passed as JSON-encoded query param for SSE (EventSource only supports GET)

## Next Steps
- Commit and push to GitHub

## Blockers & Open Questions
- (none)
