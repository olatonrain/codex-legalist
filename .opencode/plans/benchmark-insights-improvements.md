# Plan: Benchmark + Counsel Insights Improvements

## Overview
4 changes to implement. Ordered by dependency.

---

## Task 1 — Gate "Run Live" button behind completed trial

**File: `static/ui.js`**

1. Add helper:
```js
function hasCompletedTrial() {
  const gs = State.graphState;
  return gs && Array.isArray(gs.transcript) && gs.transcript.length > 0 && !!gs.main_verdict;
}
```

2. Modify `initBenchmarkButtons()` — wrap live button click:
```js
$("runBenchmarkLiveBtn")?.addEventListener("click", () => {
  if (!hasCompletedTrial()) {
    showToast("Run a full trial first before using Live benchmark mode.", "warning", 4000);
    return;
  }
  runBenchmark(false);
});
```

---

## Task 2 — Move Counsel Insights to position 2

**File: `index.html`**

Cut lines 708–740:
```html
<!-- ─ COUNSEL INSIGHTS ─ -->
<div class="chart-card" style="margin-top: 20px">
  ...
</div>
```

Paste after `#actualJuryCard` closing `</div>` at line 628, before Shadow Jury Room `<!-- SHADOW JURY ROOM -->` at line 630.

---

## Task 3 — Add missing Single-Agent sample card

**File: `index.html`**

In `.sample-grid` (lines 849–867), insert between Raw LLM and Codex legalist cards:
```html
<div class="sample-card">
  <div class="sample-header"><i class="fas fa-user-tie"></i> Single-Agent Response</div>
  <div class="sample-content" id="benchSingleSample">Awaiting benchmark results...</div>
  <div class="sample-meta" id="benchSingleMeta">
    <span>—</span>
  </div>
</div>
```

**File: `static/ui.js`** (`renderBenchmarkView()`)

Add Single-Agent sample population (after Raw LLM block, around line 1811):
```js
const singleSample = $("benchSingleSample");
const singleMeta = $("benchSingleMeta");
if (singleSample && singleResults[0]) {
  const resp = singleResults[0].reasoning || singleResults[0].response || "";
  const v = singleResults[0].verdict || "";
  singleSample.innerHTML = `<strong>Verdict:</strong> ${escapeHtml(v)}<br><br>${escapeHtml(resp.slice(0, 300))}${resp.length > 300 ? "..." : ""}`;
  if (singleMeta) singleMeta.innerHTML = `<span>${singleResults[0].time?.toFixed(1) || "?"}s</span><span>${singleHalluc} hallucinations</span><span>${singleCitations} citations</span>`;
}
```

---

## Task 4 — SSE streaming backend + trial_context support

### 4a. `legalist/benchmark.py`

**Add `extract_trial_context` function** (matches `src/insight.py` pattern):
```python
def extract_benchmark_context(state: dict) -> str:
    """Format trial record as a text block for prompt injection."""
    ...
```

**Modify `run_raw_llm_query(case_description, use_mock, trial_context=None)`**:
- If trial_context, append context block to prompt: "The following trial has already been conducted. Use it as reference:\n\n{context}"

**Modify `run_single_agent_trial(case_description, use_mock, trial_context=None)`**:
- Same pattern — inject trial record into the judge prompt

**Modify `run_multi_agent_trial(case_description, use_mock, trial_context=None)`**:
- If trial_context is provided, DON'T invoke the graph. Extract metrics:
  - `verdict` = trial_context.get("main_verdict", "Unknown")
  - `reasoning` = joined transcript text
  - `transcript_length` = len(trial_context.get("transcript", []))
  - `hallucinations` = count_hallucinations(reasoning, case_description)
  - `evidence_citations` = count_evidence_citations(reasoning)
  - `shadow_jury_consensus` = trial_context.get("shadow_jury_results", {}).get("win_probability", 0)
  - `time` = 0
  - Add `source: "existing_trial"` field

### 4b. `server.py`

**Add new streaming endpoint** (`GET /api/benchmark/run-stream`):
```python
@app.get("/api/benchmark/run-stream")
async def run_benchmark_stream(
    case_description: str,
    num_runs: int = 3,
    use_mock: bool = False,
    trial_context: str = None,  # JSON-encoded dict
):
    async def event_stream():
        # Parse trial_context if provided
        ctx = json.loads(trial_context) if trial_context else None

        for i in range(num_runs):
            # Raw LLM
            yield f"event: raw_llm_start\ndata: {json.dumps({'run': i+1, 'total': num_runs})}\n\n"
            raw = run_raw_llm_query(case_description, use_mock, ctx)
            yield f"event: raw_llm_done\ndata: {json.dumps(raw)}\n\n"

            # Single-agent
            yield f"event: single_start\ndata: {json.dumps({'run': i+1})}\n\n"
            single = run_single_agent_trial(case_description, use_mock, ctx)
            yield f"event: single_done\ndata: {json.dumps(single)}\n\n"

            # Multi-agent
            multi = run_multi_agent_trial(case_description, use_mock, ctx)
            yield f"event: multi_result\ndata: {json.dumps(multi)}\n\n"

        # Build final aggregate
        # ... (same aggregation as POST /api/benchmark/run)
        yield f"event: complete\ndata: {json.dumps(aggregate)}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
```

---

## Task 5 — Frontend SSE consumer + progress display

**File: `index.html`**

Add a progress display section between the Benchmark Run buttons and the comparison table:
```html
<div id="benchmarkProgress" style="display:none; margin-top:16px;">
  <div id="benchProgressSteps"></div>
</div>
```

**File: `static/ui.js`**

Replace `runBenchmark()` body to use SSE instead of POST:
```js
async function runBenchmark(useMock) {
  // ... validation same as before ...

  const params = new URLSearchParams({
    case_description: caseText,
    num_runs: useMock ? 3 : 1,
    use_mock: String(useMock),
  });
  if (hasCompletedTrial()) {
    params.set("trial_context", JSON.stringify(State.graphState));
  }

  const url = `/api/benchmark/run-stream?${params}`;
  const evtSource = new EventSource(url);

  const progressEl = $("benchmarkProgress");
  const stepsEl = $("benchProgressSteps");
  progressEl.style.display = "";

  const rawResults = [], singleResults = [], multiResults = [];

  evtSource.addEventListener("raw_llm_done", (e) => {
    const r = JSON.parse(e.data);
    rawResults.push(r);
    stepsEl.innerHTML += `<div>✅ Raw LLM run ${r.run || rawResults.length}: ${(r.response || "").slice(0, 80)}...</div>`;
  });

  evtSource.addEventListener("single_done", (e) => {
    const r = JSON.parse(e.data);
    singleResults.push(r);
    stepsEl.innerHTML += `<div>✅ Single-Agent run: ${r.verdict} (${r.time?.toFixed(1) || "?"}s)</div>`;
  });

  evtSource.addEventListener("multi_result", (e) => {
    const r = JSON.parse(e.data);
    multiResults.push(r);
    stepsEl.innerHTML += `<div>✅ Multi-Agent: ${r.verdict}${r.source === "existing_trial" ? " (from trial)" : ""}</div>`;
  });

  evtSource.addEventListener("complete", (e) => {
    const data = JSON.parse(e.data);
    State.benchmarkData = data;
    evtSource.close();
    progressEl.style.display = "none";
    renderBenchmarkView();
    // restore buttons...
  });

  evtSource.onerror = () => {
    evtSource.close();
    // handle error...
  };
}
```

---

## Task 6 — Run verification

- `node --check static/ui.js static/jury.js`
- `python -m pytest tests/ -x -q`
- `python -c "from legalist.benchmark import *; print('ok')"`
- `python -c "from server import app; print('ok')"`
