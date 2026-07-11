# Benchmark

Three approaches are compared using identical case facts to demonstrate the value of adversarial multi-agent collaboration.

## Comparison

| Metric                | Raw LLM  | Single-Agent | Codex legalist |
| --------------------- | -------- | ------------ | -------------- |
| Evidence Citations    | 0-2      | 3-7          | 12-20          |
| Hallucinations        | 8-15     | 3-8          | 0-2            |
| Verdict Consistency   | N/A      | Variable     | High           |
| Shadow Jury Consensus | N/A      | N/A          | 75-92%         |
| Response Time         | 0.3-0.8s | 1.0-2.5s     | 15-30s         |

## Key Findings

- **Raw LLM** — A simple prompt produces one- or two-sentence verdicts with no evidence citations or adversarial testing. The model hallucinates case details and lacks any structured reasoning.
- **Single-Agent** — One model handling all roles produces structured verdicts with limited analysis, but suffers from bias toward whichever argument it writes first and a higher hallucination rate.
- **Codex legalist** — A full adversarial trial with 11 specialised agents produces comprehensive analysis with evidence tracking, witness examination, fact-checking, and a shadow jury consensus. The multi-agent approach trades speed for accuracy, transparency, and reliability — critical in legal reasoning where hallucinations carry serious consequences.

## Using a Trial Record

If a trial has already been run, the benchmark enriches prompts with the full trial record:

- **Raw LLM** and **Single-Agent** receive the existing trial transcript, evidence list, closing arguments, and verdict injected into their prompts — giving them the same context the multi-agent system had.
- **Multi-Agent** skips re-running the full graph and extracts metrics directly from the saved trial result. This reduces benchmark time from 5–10 minutes to seconds.

When no trial exists, all three approaches run from case facts alone as before.

## Running the Benchmark

### Mock mode (no API key needed)

Click **"Run Benchmark (Mock)"** in the UI, or from CLI:

```bash
python legalist/benchmark.py --mock
```

### Live mode (requires QWEN_API_KEY)

A completed trial must exist before **"Run Live (API Calls)"** is enabled. Click it from the UI, or from CLI:

```bash
python legalist/benchmark.py
```

### Streaming progress

Live benchmark runs show real-time progress via SSE. The UI displays each step as it finishes:

1. Raw LLM query — shows the actual response text inline
2. Single-Agent trial — shows verdict and time
3. Codex legalist — shows verdict and source (existing trial or fresh run)

When all runs complete, the final comparison table and charts render automatically.
