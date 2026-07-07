# Benchmark

Three approaches were compared using identical case facts to demonstrate the value of adversarial multi-agent collaboration.

## Comparison

| Metric                | Raw LLM  | Single-Agent | Codex Legalis |
| --------------------- | -------- | ------------ | ------------- |
| Evidence Citations    | 0-2      | 3-7          | 12-20         |
| Hallucinations        | 8-15     | 3-8          | 0-2           |
| Verdict Consistency   | N/A      | Variable     | High          |
| Shadow Jury Consensus | N/A      | N/A          | 75-92%        |
| Response Time         | 0.3-0.8s | 1.0-2.5s     | 15-30s        |

## Key Findings

- **Raw LLM** — A simple prompt produces one- or two-sentence verdicts with no evidence citations or adversarial testing. The model hallucinates case details and lacks any structured reasoning.
- **Single-Agent** — One model handling all roles produces structured verdicts with limited analysis, but suffers from bias toward whichever argument it writes first and a higher hallucination rate.
- **Codex Legalis** — A full adversarial trial with 11 specialised agents produces comprehensive analysis with evidence tracking, witness examination, fact-checking, and a shadow jury consensus. The multi-agent approach trades speed for accuracy, transparency, and reliability — critical in legal reasoning where hallucinations carry serious consequences.

## Running the Benchmark

```bash
# Mock mode — no API key needed, uses pre-computed results
make benchmark-mock

# Live mode — runs against Qwen Cloud API (requires QWEN_API_KEY)
make benchmark

# Direct invocation
python legalis/benchmark.py --mock
python legalis/benchmark.py
```

Pre-computed mock results are stored in `benchmark_results.json`.
