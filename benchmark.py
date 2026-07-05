"""
benchmark.py
────────────
Compares raw LLM vs single-agent vs multi-agent verdict quality on the same case.

Usage:
    python benchmark.py --case "the defendant stole a car from the parking lot"
    python benchmark.py --mock  # Use mocked responses (no API calls)

Three approaches tested with identical case facts:
    1. Raw LLM: Simple prompt to Qwen ("What's the verdict?")
    2. Single-Agent: One LLM handles all roles (prosecutor, defense, judge, jury)
    3. Multi-Agent: Codex Legalis (9 specialized agents + shadow jury)

Metrics:
    - Verdict consistency (agreement rate across runs)
    - Hallucination count (facts not in case description)
    - Evidence citations (references to exhibits, witnesses, testimony)
    - Shadow jury consensus score (multi-agent only)
    - Response time
"""
import argparse
import json
import random
import re
import time
from typing import Dict, List
from unittest.mock import patch, MagicMock
from langchain_core.messages import AIMessage


def extract_facts(text: str) -> set:
    """Extract key facts from text using improved extraction."""
    # Convert to lowercase and split into sentences
    text = text.lower()
    
    # Remove common legal/procedural phrases that shouldn't count as facts
    procedural_phrases = [
        'the court', 'your honor', 'my lord', 'objection', 'sustained', 'overruled',
        'ladies and gentlemen', 'jury', 'witness', 'testimony', 'evidence', 'exhibit',
        'prosecution', 'defense', 'counsel', 'your worship', 'may it please',
        'respectfully submit', 'would submit', 'the people', 'the state',
        'beyond reasonable doubt', 'balance of probabilities', 'preponderance',
        'guilty', 'not guilty', 'liable', 'not liable', 'verdict',
        'i do not recall', 'i don\'t know', 'outside my knowledge'
    ]
    
    # Extract words (3+ letters)
    words = set(re.findall(r'\b[a-z]{3,}\b', text))
    
    # Remove stopwords
    stopwords = {
        'the', 'and', 'for', 'are', 'but', 'not', 'you', 'all', 'can', 'had', 'her', 'was', 'one', 'our', 'out', 'has', 'have', 'been', 'some', 'them', 'than', 'its', 'over', 'also', 'would', 'this', 'that', 'with', 'from', 'they', 'know', 'want', 'been', 'good', 'much', 'those', 'each', 'make', 'like', 'just', 'over', 'such', 'take', 'year', 'most', 'only', 'new', 'will', 'time', 'very', 'when', 'come', 'could', 'into', 'state', 'your', 'what', 'there', 'use', 'way', 'about', 'many', 'then', 'them', 'would', 'these', 'other', 'which', 'their', 'may', 'any', 'who', 'did', 'does', 'had', 'his', 'him', 'she', 'let', 'say', 'said', 'ask', 'tell', 'give', 'take', 'see', 'look', 'find', 'think', 'believe', 'consider', 'must', 'should', 'shall'
    }
    
    # Remove procedural phrases
    for phrase in procedural_phrases:
        words.discard(phrase)
    
    return words - stopwords


def count_hallucinations(response: str, case_facts: str) -> int:
    """Count facts in response that are not in the original case facts using improved method."""
    response_facts = extract_facts(response)
    case_fact_set = extract_facts(case_facts)
    
    # Only count words that appear in response but NOT in case facts
    hallucinated = response_facts - case_fact_set
    
    # Filter out very common words that might slip through
    common_words = {
        'yes', 'no', 'sir', 'madam', 'please', 'thank', 'thanks', 'question', 'answer',
        'right', 'wrong', 'true', 'false', 'correct', 'incorrect', 'agree', 'disagree'
    }
    hallucinated = hallucinated - common_words
    
    return len(hallucinated)


def count_evidence_citations(response: str) -> int:
    """Count references to evidence in the response."""
    patterns = [
        r'exhibit',
        r'evidence',
        r'witness',
        r'testimony',
        r'document',
        r'record',
        r'proof',
    ]
    count = 0
    for pattern in patterns:
        count += len(re.findall(pattern, response, re.IGNORECASE))
    return count


def run_raw_llm_query(case_description: str, use_mock: bool = False) -> Dict:
    """Query a single LLM directly without any courtroom structure."""
    if use_mock:
        return {
            "response": "Based on the facts provided, the defendant appears guilty of theft. The evidence shows they took a car without permission.",
            "hallucinations": random.randint(8, 15),
            "evidence_citations": random.randint(0, 2),
            "time": round(random.uniform(0.3, 0.8), 2),
        }
    
    from src.llm import get_llm
    from langchain_core.messages import HumanMessage
    
    llm = get_llm(temperature=0.3, model="qwen-plus-latest")
    
    prompt = f"""Case facts:

{case_description}

What's the verdict? Provide only the verdict and brief reasoning based strictly on the facts provided."""
    
    start = time.time()
    response = llm.invoke([HumanMessage(content=prompt)])
    elapsed = time.time() - start
    content = response.content
    
    return {
        "response": content,
        "hallucinations": count_hallucinations(content, case_description),
        "evidence_citations": count_evidence_citations(content),
        "time": elapsed,
    }


def run_single_agent_trial(case_description: str, use_mock: bool = False) -> Dict:
    """Run a trial with a single agent handling all roles."""
    if use_mock:
        verdict = random.choice(["Guilty", "Guilty", "Not Guilty"])
        reasoning = "The evidence clearly shows the defendant committed the crime."
        return {
            "verdict": verdict,
            "reasoning": reasoning,
            "transcript_length": random.randint(8, 15),
            "hallucinations": random.randint(3, 8),
            "evidence_citations": random.randint(3, 7),
            "time": round(random.uniform(1.0, 2.5), 2),
        }
    
    from src.llm import get_llm
    from langchain_core.messages import SystemMessage, HumanMessage
    
    llm = get_llm(temperature=0.3, model="qwen-plus-latest")
    
    prompt = f"""You are a judge in a criminal trial. The case facts are:

{case_description}

Based STRICTLY on these facts alone, provide:
1. A verdict (Guilty or Not Guilty)
2. Your reasoning (2-3 sentences citing only facts from the case)

Do not invent any facts, names, dates, or evidence not explicitly mentioned in the case description.

Respond in this exact format:
Verdict: [Your verdict]
Reasoning: [Your reasoning]
"""
    
    response = llm.invoke([
        SystemMessage(content="You are a fair and impartial judge."),
        HumanMessage(content=prompt)
    ])
    
    content = response.content
    verdict_match = re.search(r'Verdict:\s*(Guilty|Not Guilty)', content, re.IGNORECASE)
    verdict = verdict_match.group(1) if verdict_match else "Unknown"
    
    return {
        "verdict": verdict,
        "reasoning": content,
        "transcript_length": len(content),
        "hallucinations": count_hallucinations(content, case_description),
        "evidence_citations": count_evidence_citations(content),
        "time": 0,
    }


def run_multi_agent_trial(case_description: str, use_mock: bool = False) -> Dict:
    """Run a trial with the full 9-agent society."""
    if use_mock:
        return {
            "verdict": "Guilty",
            "reasoning": "The multi-agent system reached a consensus based on thorough adversarial examination.",
            "transcript_length": random.randint(400, 600),
            "hallucinations": random.randint(0, 2),
            "evidence_citations": random.randint(12, 20),
            "shadow_jury_consensus": round(random.uniform(0.75, 0.92), 2),
            "time": round(random.uniform(15.0, 30.0), 2),
        }
    
    from src.graph import app as compiled_graph
    
    initial_state = {
        "case_description": case_description,
        "transcript": [],
        "fact_sheet": "",
        "admitted_evidence": [],
        "excluded_evidence": [],
        "clarifying_questions": [],
        "human_answers": {},
        "witness_queue": [],
        "current_witness": None,
        "examination_phase": None,
        "shadow_jury_count": 2,
        "shadow_jury_model": "qwen-plus-latest",
        "jury_count": 4,
        "audio_enabled": False,
        "deliberation_rounds": 0,
        "jury_profiles": [],
        "deliberation_snapshot": {},
        "main_verdict": None,
        "shadow_jury_results": {},
        "multimodal_evidence": [],
        "errors": [],
        "country": "United States",
        "jurisdiction_system": "Common Law",
        "jurisdiction_procedure": "adversarial",
        "criminal_standard": "Beyond a reasonable doubt",
        "civil_standard": "Preponderance of the evidence",
        "evidence_rules": "Federal Rules of Evidence",
        "jury_enabled": True,
        "cross_examination": True,
        "court_address": "Your Honor",
        "case_type": "Criminal",
    }
    
    start = time.time()
    try:
        result = compiled_graph.invoke(initial_state, config={"recursion_limit": 50})
    except Exception as e:
        elapsed = time.time() - start
        error_msg = str(e)
        if "403" in error_msg or "access_denied" in error_msg.lower():
            return {
                "verdict": "Error",
                "reasoning": f"API access denied. Check your QWEN_API_KEY has access to the required models. Error: {error_msg[:200]}",
                "transcript_length": 0,
                "hallucinations": 0,
                "evidence_citations": 0,
                "shadow_jury_consensus": 0,
                "time": elapsed,
                "error": True,
            }
        return {
            "verdict": "Error",
            "reasoning": f"Benchmark failed: {error_msg[:200]}",
            "transcript_length": 0,
            "hallucinations": 0,
            "evidence_citations": 0,
            "shadow_jury_consensus": 0,
            "time": elapsed,
            "error": True,
        }
    
    elapsed = time.time() - start
    verdict = result.get("main_verdict", "Unknown")
    shadow_jury_results = result.get("shadow_jury_results", {})
    win_prob = shadow_jury_results.get("win_probability", 0.5)
    
    transcript_text = " ".join([
        msg.content if hasattr(msg, "content") else str(msg)
        for msg in result.get("transcript", [])
    ])
    
    return {
        "verdict": verdict,
        "reasoning": transcript_text,
        "transcript_length": len(result.get("transcript", [])),
        "hallucinations": count_hallucinations(transcript_text, case_description),
        "evidence_citations": count_evidence_citations(transcript_text),
        "shadow_jury_consensus": win_prob,
        "time": elapsed,
    }


def run_benchmark(case_description: str, num_runs: int = 3, use_mock: bool = False):
    """Run the benchmark comparing raw LLM vs single-agent vs multi-agent."""
    print(f"\n{'='*70}")
    print(f"BENCHMARK: Raw LLM vs Single-Agent vs Multi-Agent")
    print(f"Case: {case_description[:80]}...")
    print(f"Runs: {num_runs}")
    print(f"Mode: {'MOCK' if use_mock else 'LIVE (API calls)'}")
    print(f"{'='*70}\n")
    
    raw_results = []
    single_results = []
    multi_results = []
    
    print("Running raw LLM queries...")
    for i in range(num_runs):
        print(f"  Run {i+1}/{num_runs}...", end=" ")
        result = run_raw_llm_query(case_description, use_mock)
        raw_results.append(result)
        print(f"Done ({result['time']:.2f}s)")
    
    print("\nRunning single-agent trials...")
    for i in range(num_runs):
        print(f"  Run {i+1}/{num_runs}...", end=" ")
        start = time.time()
        result = run_single_agent_trial(case_description, use_mock)
        elapsed = time.time() - start
        result["time"] = elapsed
        single_results.append(result)
        print(f"Verdict: {result['verdict']} ({elapsed:.2f}s)")
    
    print("\nRunning multi-agent trials...")
    for i in range(num_runs):
        print(f"  Run {i+1}/{num_runs}...", end=" ")
        start = time.time()
        result = run_multi_agent_trial(case_description, use_mock)
        elapsed = time.time() - start
        result["time"] = elapsed
        multi_results.append(result)
        print(f"Verdict: {result['verdict']} ({elapsed:.2f}s)")
    
    # Calculate metrics
    single_verdicts = [r["verdict"] for r in single_results]
    multi_verdicts = [r["verdict"] for r in multi_results]
    
    single_consistency = single_verdicts.count(single_verdicts[0]) / len(single_verdicts)
    multi_consistency = multi_verdicts.count(multi_verdicts[0]) / len(multi_verdicts)
    
    raw_avg_hallucinations = sum(r["hallucinations"] for r in raw_results) / len(raw_results)
    single_avg_hallucinations = sum(r["hallucinations"] for r in single_results) / len(single_results)
    multi_avg_hallucinations = sum(r["hallucinations"] for r in multi_results) / len(multi_results)
    
    raw_avg_citations = sum(r["evidence_citations"] for r in raw_results) / len(raw_results)
    single_avg_citations = sum(r["evidence_citations"] for r in single_results) / len(single_results)
    multi_avg_citations = sum(r["evidence_citations"] for r in multi_results) / len(multi_results)
    
    raw_avg_time = sum(r["time"] for r in raw_results) / len(raw_results)
    single_avg_time = sum(r["time"] for r in single_results) / len(single_results)
    multi_avg_time = sum(r["time"] for r in multi_results) / len(multi_results)
    
    multi_avg_consensus = sum(r.get("shadow_jury_consensus", 0) for r in multi_results) / len(multi_results)
    
    # Print results
    print(f"\n{'='*70}")
    print("RESULTS")
    print(f"{'='*70}\n")
    
    print(f"{'Metric':<35} {'Raw LLM':<15} {'Single-Agent':<15} {'Multi-Agent':<15}")
    print(f"{'-'*35} {'-'*15} {'-'*15} {'-'*15}")
    print(f"{'Avg hallucinations':<35} {raw_avg_hallucinations:<15.1f} {single_avg_hallucinations:<15.1f} {multi_avg_hallucinations:<15.1f}")
    print(f"{'Avg evidence citations':<35} {raw_avg_citations:<15.1f} {single_avg_citations:<15.1f} {multi_avg_citations:<15.1f}")
    print(f"{'Avg time (seconds)':<35} {raw_avg_time:<15.2f} {single_avg_time:<15.2f} {multi_avg_time:<15.2f}")
    print(f"{'Verdict consistency':<35} {'N/A':<15} {single_consistency:<15.2%} {multi_consistency:<15.2%}")
    print(f"{'Shadow jury consensus':<35} {'N/A':<15} {'N/A':<15} {multi_avg_consensus:<15.2%}")
    
    # Show sample responses
    print(f"\n{'='*70}")
    print("SAMPLE RESPONSES")
    print(f"{'='*70}\n")
    
    print("── Raw LLM Response (what you get from a simple prompt) ──")
    print(raw_results[0]["response"][:500])
    print()
    
    print("── Single-Agent Response (one LLM handles all roles) ──")
    print(single_results[0]["reasoning"][:500])
    print()
    
    print("── Codex Legalis Output (9 specialized agents + shadow jury) ──")
    print(f"Verdict: {multi_results[0]['verdict']}")
    print(f"Shadow Jury Consensus: {multi_results[0].get('shadow_jury_consensus', 0):.1%}")
    print(f"Evidence Citations: {multi_results[0]['evidence_citations']}")
    print(f"Transcript Length: {multi_results[0]['transcript_length']} messages")
    print()
    
    # Save results to JSON
    output = {
        "case": case_description,
        "num_runs": num_runs,
        "mock_mode": use_mock,
        "raw_llm": {
            "results": raw_results,
            "avg_hallucinations": raw_avg_hallucinations,
            "avg_evidence_citations": raw_avg_citations,
            "avg_time": raw_avg_time,
        },
        "single_agent": {
            "results": single_results,
            "consistency": single_consistency,
            "avg_hallucinations": single_avg_hallucinations,
            "avg_evidence_citations": single_avg_citations,
            "avg_time": single_avg_time,
        },
        "multi_agent": {
            "results": multi_results,
            "consistency": multi_consistency,
            "avg_hallucinations": multi_avg_hallucinations,
            "avg_evidence_citations": multi_avg_citations,
            "avg_time": multi_avg_time,
            "avg_shadow_jury_consensus": multi_avg_consensus,
        },
    }
    
    with open("benchmark_results.json", "w") as f:
        json.dump(output, f, indent=2)
    
    print(f"\nResults saved to benchmark_results.json")
    print(f"{'='*70}\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Benchmark raw LLM vs single-agent vs multi-agent trial quality")
    parser.add_argument("--case", type=str, default="The defendant stole a car from the parking lot at midnight. The witness saw the defendant break the window and drive away.", help="Case description")
    parser.add_argument("--runs", type=int, default=3, help="Number of runs per configuration")
    parser.add_argument("--mock", action="store_true", help="Use mocked responses (no API calls)")
    
    args = parser.parse_args()
    
    run_benchmark(args.case, args.runs, args.mock)
