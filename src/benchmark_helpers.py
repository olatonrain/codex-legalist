"""
src/benchmark_helpers.py
────────────────────────
Shared helpers for benchmark endpoints.
Extracted to avoid duplication between POST /api/benchmark/run
and GET /api/benchmark/run-stream.
"""

from __future__ import annotations


def safe_avg(results: list[dict], key: str, default: float = 0) -> float:
    """Compute average of a key across result dicts, returning default if empty."""
    if not results:
        return default
    return sum(r.get(key, default) for r in results) / len(results)


def build_benchmark_aggregate(
    raw_results: list[dict],
    single_results: list[dict],
    multi_results: list[dict],
    num_runs: int,
    errors: list[str] | None = None,
) -> dict:
    """Build the standard benchmark aggregate response object."""
    return {
        "raw_llm": {
            "results": raw_results,
            "avg_hallucinations": safe_avg(raw_results, "hallucinations"),
            "avg_evidence_citations": safe_avg(raw_results, "evidence_citations"),
        },
        "single_agent": {
            "results": single_results,
            "avg_hallucinations": safe_avg(single_results, "hallucinations"),
            "avg_evidence_citations": safe_avg(single_results, "evidence_citations"),
        },
        "multi_agent": {
            "results": multi_results,
            "avg_hallucinations": safe_avg(multi_results, "hallucinations"),
            "avg_evidence_citations": safe_avg(multi_results, "evidence_citations"),
            "avg_shadow_jury_consensus": safe_avg(multi_results, "shadow_jury_consensus"),
        },
        "completed_runs": len(multi_results),
        "total_runs": num_runs,
        "errors": errors if errors else None,
    }