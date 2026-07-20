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
    3. Multi-Agent: Codex legalist (11 specialized agents + shadow jury)

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
from typing import Dict

from src.logger import get_logger

logger = get_logger(__name__)


def extract_benchmark_context(state: dict) -> str:
    """Format an existing trial record as a prompt-injectable context block."""
    case_desc = (state.get("case_description") or "")[:2000]
    verdict = state.get("main_verdict") or "No Verdict Reached"

    admitted = state.get("admitted_evidence") or []
    evidence_lines = []
    for ev in admitted[-10:]:
        if isinstance(ev, dict):
            evidence_lines.append(f"  - {ev.get('id','?')}: {str(ev.get('description',''))[:200]}")
        else:
            evidence_lines.append(f"  - {str(ev)[:200]}")

    transcript = state.get("transcript") or []
    transcript_lines = []
    for msg in transcript[-20:]:
        if isinstance(msg, dict):
            name = msg.get("name") or msg.get("agent") or "Speaker"
            text = (msg.get("content") or msg.get("text") or "")[:150]
        else:
            name = "Speaker"
            text = str(msg)[:150]
        transcript_lines.append(f"  [{name}]: {text}")

    closing_args = ""
    trial_log = state.get("trial_log") or {}
    if isinstance(trial_log, dict):
        ca = trial_log.get("closing_arguments", "")
        if isinstance(ca, list):
            ca = "\n".join(ca)
        closing_args = str(ca)[:1000]

    parts = [
        "=== EXISTING TRIAL RECORD ===",
        f"Case Description: {case_desc}",
        f"Verdict: {verdict}",
    ]
    if evidence_lines:
        parts.append("\nAdmitted Evidence:")
        parts.extend(evidence_lines)
    if transcript_lines:
        parts.append(f"\nTrial Transcript (last {len(transcript_lines)} messages):")
        parts.extend(transcript_lines)
    if closing_args:
        parts.append(f"\nClosing Arguments:\n{closing_args}")
    parts.append("=== END TRIAL RECORD ===")
    return "\n".join(parts)


def extract_facts(text: str) -> set:
    """Extract key facts from text using improved extraction.

    Strips procedural/legal boilerplate so only case-specific words remain.
    Multi-word phrases are removed from the raw text *before* word extraction;
    single legal terms are filtered from the word set directly.
    """
    text = text.lower()

    # Remove multi-word procedural phrases entirely from text first
    multi_word_procedural = [
        "the court",
        "your honor",
        "my lord",
        "your worship",
        "ladies and gentlemen",
        "may it please",
        "respectfully submit",
        "would submit",
        "the people",
        "the state",
        "beyond reasonable doubt",
        "balance of probabilities",
        "not guilty",
        "not liable",
        "i do not recall",
        "i don't know",
        "i do not know",
        "outside my knowledge",
        "the witness",
        "the defendant",
        "the plaintiff",
        "the prosecution",
        "the defense",
        "the jury",
        "the court finds",
        "the court rules",
        "the court admits",
        "the court sustains",
        "the court overrules",
        "the objection is",
        "objection your honor",
        "the evidence shows",
        "based on the",
        "in this case",
        "the facts of",
        "the testimony of",
        "the statement of",
        "counsel for the",
        "counsel please",
        "the witness is",
        "the witness may",
        "witness may answer",
        "the answer is",
        "the record will",
        "let the record",
        "so ordered",
        "the trial has",
        "this court has",
        "it is so",
        "that the defendant",
        "that the plaintiff",
        "the matter before",
        "having considered",
        "after reviewing",
        "the submissions of",
        "the arguments of",
    ]
    for phrase in multi_word_procedural:
        text = text.replace(phrase, "")

    # Extract words (3+ letters)
    words = set(re.findall(r"\b[a-z]{3,}\b", text))

    # Legal/procedural single words that should never count as facts
    legal_words = {
        "objection", "sustained", "overruled", "jury", "witness",
        "testimony", "evidence", "exhibit", "prosecution", "defense",
        "defence", "counsel", "preponderance", "guilty", "liable",
        "verdict", "hearsay", "admissible", "inadmissible",
        "relevance", "relevant", "irrelevant", "foundation",
        "credibility", "credible", "impeach", "impeachment",
        "authenticate", "authentication", "stipulate", "stipulation",
        "burden", "standard", "proof", "reasonable", "doubt",
        "presume", "presumption", "rebut", "rebuttal",
        "objected", "overrule", "sustain", "admit", "admitted",
        "exclude", "excluded", "stricken", "strike",
        "testify", "testified", "testifying", "testifies",
        "sworn", "oath", "affirm", "affirmation",
        "cross", "redirect", "recross", "direct",
        "examination", "examine", "examined", "questioning",
        "opening", "closing", "statement", "statements",
        "argument", "arguments", "submission", "submissions",
        "judge", "magistrate", "foreperson", "juror", "jurors",
        "deliberation", "deliberate", "deliberated", "deliberations",
        "verdicts", "acquittal", "acquit", "convict", "conviction",
        "sentence", "sentencing", "sentenced",
        "advocate", "attorney", "lawyer", "solicitor", "barrister",
        "plead", "plea", "pleaded", "motion", "motions",
        "proceedings", "proceeding", "trial", "hearing", "hearings",
        "sidebar", "bench", "chambers", "robing",
        "appeal", "appellate", "remand", "remanded",
        "brief", "briefing", "memorandum", "affidavit",
        "docket", "calendar", "adjourn", "adjourned", "recess",
        "mistrial", "sanction", "sanctions", "contempt",
        "rights", "privilege", "privileged", "waiver", "waive",
        "jurisdiction", "jurisdictional", "venue",
        "statute", "statutory", "ordinance", "regulation",
        "common", "civil", "criminal", "procedural", "substantive",
        "plaintiff", "defendant", "appellant", "respondent",
        "petitioner", "claimant", "accused", "offender",
        "allege", "alleged", "allegation", "allegations",
        "complaint", "complainant", "indictment", "charge",
        "charged", "offence", "offenses",
        "settle", "settlement", "mediation", "arbitration",
        "order", "ordered", "ruling", "ruled", "holding",
        "clerk", "bailiff", "marshal", "reporter",
        "admonish", "admonished", "instruction", "instructions",
        "poll", "polled", "deadlock", "hung",
        "foreman", "forewoman", "panel", "panels",
        "transcript", "record", "recording", "register",
        "hereby", "thereof", "therein", "thereto", "thereunder",
        "whereas", "wherein", "whereby", "hereinafter",
        "aforesaid", "aforementioned", "afore", "forthwith",
        "whereupon", "thereupon", "herein", "herewith", "hereunder",
        "acknowledge", "acknowledged", "concur", "concurring",
        "dissent", "dissenting", "majority", "minority",
        "render", "rendered", "pronounce", "pronounced",
    }

    # Remove stopwords
    stopwords = {
        "the", "and", "for", "are", "but", "not",
        "you", "all", "can", "had", "her", "was", "one", "our",
        "out", "has", "have", "been", "some", "them", "than",
        "its", "over", "also", "would", "this", "that", "with",
        "from", "they", "know", "want", "good", "much", "those",
        "each", "make", "like", "just", "such", "take", "year",
        "most", "only", "new", "will", "time", "very", "when",
        "come", "could", "into", "state", "your", "what", "there",
        "use", "way", "about", "many", "then", "these", "other",
        "which", "their", "may", "any", "who", "did", "does",
        "his", "him", "she", "let", "say", "said", "ask", "tell",
        "give", "see", "look", "find", "think", "believe",
        "consider", "must", "should", "shall", "now", "here",
        "back", "still", "even", "first", "last", "next",
        "under", "over", "upon", "unto", "without", "within",
        "through", "across", "along", "around", "above", "below",
        "before", "after", "during", "until", "since",
        "while", "where", "why", "how", "every", "everyone",
        "someone", "anyone", "nobody", "nothing", "everything",
        "something", "anything", "toward", "towards",
        "because", "cause", "due",
    }

    # Remove legal terms and stopwords
    return (words - legal_words) - stopwords


def count_hallucinations(response: str, case_facts: str) -> int:
    """Count facts in response that are not in the original case facts using improved method.
    
    Returns normalized rate per 100 words to fairly compare short vs long responses.
    """
    response_facts = extract_facts(response)
    case_fact_set = extract_facts(case_facts)

    # Only count words that appear in response but NOT in case facts
    hallucinated = response_facts - case_fact_set

    # Filter out common or generic words that might slip through
    common_words = {
        "yes", "no", "sir", "madam", "please", "thank", "thanks",
        "question", "answer", "right", "wrong", "true", "false",
        "correct", "incorrect", "agree", "disagree",
        "proceed", "proceeds", "continue", "continued",
        "moving", "move", "next", "prior", "previous",
        "refer", "refers", "referred", "regarding", "respect",
        "describe", "described", "describe", "explain", "explained",
        "tell", "told", "speak", "spoke", "talk", "talked",
        "provide", "provided", "provides", "present", "presented",
        "indicate", "indicated", "indicates", "show", "shows",
        "showed", "shown",
        "submit", "submits", "submitted",
        "regard", "regards", "regarded", "concerning",
        "further", "furthermore", "moreover", "additionally",
        "however", "therefore", "accordingly", "consequently",
        "nevertheless", "nonetheless", "notwithstanding",
        "pursuant", "purport", "purports", "purported",
        "deem", "deems", "deemed",
        "remain", "remains", "remained",
        "appear", "appears", "appeared", "apparent", "apparently",
        "manner", "nature", "type", "kind", "sort",
        "circumstance", "circumstances",
        "content", "contents",
        "portion", "portion", "segment", "section",
        "aspect", "aspects", "element", "elements",
        "factor", "factors", "basis", "bases",
        "instance", "instances", "scenario", "scenarios",
        "presence", "absence",
        "extent", "degree", "level",
        "case", "cases", "matter", "matters", "subject",
        "issue", "issues", "point", "points",
        "particular", "particulars", "specific",
        "general", "generally", "typical", "typically",
        "potential", "potentially",
        "possible", "possibly", "likely", "unlikely",
        "appropriate", "appropriately",
        "necessary", "necessarily",
        "proper", "properly", "duly",
        "called", "calling", "call",
        "respond", "responds", "responded", "response",
        "forward", "backward", "ahead", "along",
        "bring", "brings", "brought",
        "understand", "understood", "understanding",
        "simple", "simply", "basic", "basically",
        "additional", "add",
        "enter", "enters", "entered",
        "receive", "receives", "received", "receiving",
        "including", "includes", "include",
        "within", "without",
        "whether", "either", "neither",
        "upon", "unto",
        "done", "made", "went", "gone",
        "put", "set", "kept", "keeps",
        "form", "forms", "formed", "format",
        "process", "processes", "processed", "procedure",
        "part", "parts",
        "attach", "attached", "attachment",
        "review", "reviews", "reviewed", "reviewing",
        "examine", "examined", "examining",
    }
    hallucinated = hallucinated - common_words

    # Normalize by response length (per 100 words) for fair comparison
    response_word_count = len(response.split())
    if response_word_count == 0:
        return 0
    rate_per_100 = (len(hallucinated) / response_word_count) * 100
    return round(rate_per_100, 1)


def count_hallucinations_raw(response: str, case_facts: str) -> int:
    """Legacy raw count (not normalized) - kept for backward compatibility."""
    response_facts = extract_facts(response)
    case_fact_set = extract_facts(case_facts)
    hallucinated = response_facts - case_fact_set
    common_words = {
        "yes", "no", "sir", "madam", "please", "thank", "thanks",
        "question", "answer", "right", "wrong", "true", "false",
        "correct", "incorrect", "agree", "disagree",
        "proceed", "continue", "refer", "regard", "submit",
        "provide", "present", "indicate", "describe", "explain",
        "further", "however", "therefore", "include", "within",
        "regarding", "concerning", "particular", "specific",
        "circumstance", "circumstances", "manner",
        "appropriate", "necessary", "potential",
    }
    hallucinated = hallucinated - common_words
    return len(hallucinated)


def count_evidence_citations(response: str) -> int:
    """Count references to evidence in the response."""
    patterns = [
        r"exhibit",
        r"evidence",
        r"witness",
        r"testimony",
        r"document",
        r"record",
        r"proof",
    ]
    count = 0
    for pattern in patterns:
        count += len(re.findall(pattern, response, re.IGNORECASE))
    return count


def run_raw_llm_query(case_description: str, use_mock: bool = False, trial_context: dict = None) -> Dict:
    """Query a single LLM directly without any courtroom structure."""
    if use_mock:
        return {
            "response": "Based on the facts provided, the defendant appears guilty of theft. The evidence shows they took a car without permission.",
            "hallucinations": round(random.uniform(2.0, 5.0), 1),
            "evidence_citations": random.randint(0, 2),
            "time": round(random.uniform(0.3, 0.8), 2),
        }

    from langchain_core.messages import HumanMessage

    from src.llm import get_llm

    try:
        llm = get_llm(temperature=0.3, model="qwen-plus-latest")
    except Exception as exc:
        logger.error("Failed to init LLM in run_raw_llm_query: %s", exc, exc_info=True)
        return {"response": f"Error: {exc}", "hallucinations": 0, "evidence_citations": 0, "time": 0}

    extra = ""
    if trial_context:
        extra = f"\n\n{extract_benchmark_context(trial_context)}\n\n"

    prompt = f"""Case facts:

{case_description}
{extra}
What's the verdict? Provide only the verdict and brief reasoning based strictly on the facts provided."""

    start = time.time()
    try:
        response = llm.invoke([HumanMessage(content=prompt)])
    except Exception as exc:
        logger.error("LLM invoke failed in run_raw_llm_query: %s", exc, exc_info=True)
        elapsed = time.time() - start
        return {"response": f"Error: {exc}", "hallucinations": 0, "evidence_citations": 0, "time": elapsed}
    elapsed = time.time() - start
    content = response.content

    return {
        "response": content,
        "hallucinations": count_hallucinations(content, case_description),
        "evidence_citations": count_evidence_citations(content),
        "time": elapsed,
    }


def run_single_agent_trial(case_description: str, use_mock: bool = False, trial_context: dict = None) -> Dict:
    """Run a trial with a single agent handling all roles."""
    if use_mock:
        verdict = random.choice(["Guilty", "Guilty", "Not Guilty"])
        reasoning = "The evidence clearly shows the defendant committed the crime."
        return {
            "verdict": verdict,
            "reasoning": reasoning,
            "transcript_length": random.randint(8, 15),
            "hallucinations": round(random.uniform(1.5, 3.5), 1),
            "evidence_citations": random.randint(3, 7),
            "time": round(random.uniform(1.0, 2.5), 2),
        }

    from langchain_core.messages import HumanMessage, SystemMessage

    from src.llm import get_llm

    try:
        llm = get_llm(temperature=0.3, model="qwen-plus-latest")
    except Exception as exc:
        logger.error("Failed to init LLM in run_single_agent_trial: %s", exc, exc_info=True)
        return {
            "verdict": "Error",
            "reasoning": f"Error: {exc}",
            "transcript_length": 0,
            "hallucinations": 0,
            "evidence_citations": 0,
            "time": 0,
        }

    extra = ""
    if trial_context:
        extra = f"\n\n{extract_benchmark_context(trial_context)}\n\n"

    prompt = f"""You are a judge in a criminal trial. The case facts are:

{case_description}
{extra}
Based STRICTLY on these facts alone, provide:
1. A verdict (Guilty or Not Guilty)
2. Your reasoning (2-3 sentences citing only facts from the case)

Do not invent any facts, names, dates, or evidence not explicitly mentioned in the case description.

Respond in this exact format:
Verdict: [Your verdict]
Reasoning: [Your reasoning]
"""

    start = time.time()
    try:
        response = llm.invoke(
            [SystemMessage(content="You are a fair and impartial judge."), HumanMessage(content=prompt)]
        )
    except Exception as exc:
        logger.error("LLM invoke failed in run_single_agent_trial: %s", exc, exc_info=True)
        elapsed = time.time() - start
        return {
            "verdict": "Error",
            "reasoning": f"Error: {exc}",
            "transcript_length": 0,
            "hallucinations": 0,
            "evidence_citations": 0,
            "time": round(elapsed, 2),
        }
    elapsed = time.time() - start

    content = response.content
    verdict_match = re.search(r"Verdict:\s*(Guilty|Not Guilty)", content, re.IGNORECASE)
    verdict = verdict_match.group(1) if verdict_match else "Unknown"

    return {
        "verdict": verdict,
        "reasoning": content,
        "transcript_length": len(content),
        "hallucinations": count_hallucinations(content, case_description),
        "evidence_citations": count_evidence_citations(content),
        "time": round(elapsed, 2),
    }


def run_multi_agent_trial(case_description: str, use_mock: bool = False, trial_context: dict = None) -> Dict:
    """Run a trial with the full 9-agent society.

    If trial_context is provided (an existing trial result), skip the graph
    invoke and extract metrics directly from the saved trial record.
    """
    if trial_context and not use_mock:
        transcript = trial_context.get("transcript") or []
        transcript_text = " ".join(
            [
                msg.get("content", "") if isinstance(msg, dict) else str(msg)
                for msg in transcript
                if not isinstance(msg, dict) or msg.get("name") != "Fact Checker"
            ]
        )
        shadow_results = trial_context.get("shadow_jury_results") or {}
        return {
            "verdict": trial_context.get("main_verdict", "Unknown"),
            "reasoning": transcript_text[:1000],
            "transcript_length": len(transcript),
            "hallucinations": count_hallucinations(transcript_text, case_description),
            "evidence_citations": count_evidence_citations(transcript_text),
            "shadow_jury_consensus": shadow_results.get("win_probability", 0),
            "time": 0,
            "source": "existing_trial",
        }

    if use_mock:
        return {
            "verdict": "Guilty",
            "reasoning": "The multi-agent system reached a consensus based on thorough adversarial examination.",
            "transcript_length": random.randint(400, 600),
            "hallucinations": round(random.uniform(0.5, 1.5), 1),
            "evidence_citations": random.randint(12, 20),
            "shadow_jury_consensus": round(random.uniform(0.75, 0.92), 2),
            "time": round(random.uniform(15.0, 30.0), 2),
        }

    from src.graph import app as compiled_graph
    from src.state import create_initial_state

    initial_state = create_initial_state(
        case_description=case_description,
        country="United States",
        jurisdiction_system="Common Law",
        jurisdiction_procedure="adversarial",
        criminal_standard="Beyond a reasonable doubt",
        civil_standard="Preponderance of the evidence",
        evidence_rules="Federal Rules of Evidence",
        jury_enabled=True,
        cross_examination=True,
        court_address="Your Honor",
        case_type="Criminal",
        shadow_jury_count=2,
        jury_count=4,
    )

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

    transcript_text = " ".join(
        [
            msg.content if hasattr(msg, "content") else str(msg)
            for msg in result.get("transcript", [])
            if not hasattr(msg, "name") or msg.name != "Fact Checker"
        ]
    )

    return {
        "verdict": verdict,
        "reasoning": transcript_text,
        "transcript_length": len(result.get("transcript", [])),
        "hallucinations": count_hallucinations(transcript_text, case_description),
        "evidence_citations": count_evidence_citations(transcript_text),
        "shadow_jury_consensus": win_prob,
        "time": elapsed,
    }


def run_benchmark(case_description: str, num_runs: int = 3, use_mock: bool = False, trial_context: dict = None):
    """Run the benchmark comparing raw LLM vs single-agent vs multi-agent."""
    print(f"\n{'=' * 70}")
    print("BENCHMARK: Raw LLM vs Single-Agent vs Multi-Agent")
    print(f"Case: {case_description[:80]}...")
    print(f"Runs: {num_runs}")
    print(f"Mode: {'MOCK' if use_mock else 'LIVE (API calls)'}")
    print(f"{'=' * 70}\n")

    raw_results = []
    single_results = []
    multi_results = []

    print("Running raw LLM queries...")
    for i in range(num_runs):
        print(f"  Run {i + 1}/{num_runs}...", end=" ")
        result = run_raw_llm_query(case_description, use_mock, trial_context)
        raw_results.append(result)
        print(f"Done ({result['time']:.2f}s)")

    print("\nRunning single-agent trials...")
    for i in range(num_runs):
        print(f"  Run {i + 1}/{num_runs}...", end=" ")
        result = run_single_agent_trial(case_description, use_mock, trial_context)
        single_results.append(result)
        print(f"Verdict: {result['verdict']} ({result['time']:.2f}s)")

    print("\nRunning multi-agent trials...")
    for i in range(num_runs):
        print(f"  Run {i + 1}/{num_runs}...", end=" ")
        result = run_multi_agent_trial(case_description, use_mock, trial_context)
        multi_results.append(result)
        print(f"Verdict: {result['verdict']} ({result['time']:.2f}s)")

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
    print(f"\n{'=' * 70}")
    print("RESULTS")
    print(f"{'=' * 70}\n")

    print(f"{'Metric':<35} {'Raw LLM':<15} {'Single-Agent':<15} {'Multi-Agent':<15}")
    print(f"{'-' * 35} {'-' * 15} {'-' * 15} {'-' * 15}")
    print(
        f"{'Avg hallucinations':<35} {raw_avg_hallucinations:<15.1f} {single_avg_hallucinations:<15.1f} {multi_avg_hallucinations:<15.1f}"
    )
    print(
        f"{'Avg evidence citations':<35} {raw_avg_citations:<15.1f} {single_avg_citations:<15.1f} {multi_avg_citations:<15.1f}"
    )
    print(f"{'Avg time (seconds)':<35} {raw_avg_time:<15.2f} {single_avg_time:<15.2f} {multi_avg_time:<15.2f}")
    print(f"{'Verdict consistency':<35} {'N/A':<15} {single_consistency:<15.2%} {multi_consistency:<15.2%}")
    print(f"{'Shadow jury consensus':<35} {'N/A':<15} {'N/A':<15} {multi_avg_consensus:<15.2%}")

    # Show sample responses
    print(f"\n{'=' * 70}")
    print("SAMPLE RESPONSES")
    print(f"{'=' * 70}\n")

    print("── Raw LLM Response (what you get from a simple prompt) ──")
    print(raw_results[0]["response"][:500])
    print()

    print("── Single-Agent Response (one LLM handles all roles) ──")
    print(single_results[0]["reasoning"][:500])
    print()

    print("── Codex legalist Output (11 specialized agents + shadow jury) ──")
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

    print("\nResults saved to benchmark_results.json")
    print(f"{'=' * 70}\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Benchmark raw LLM vs single-agent vs multi-agent trial quality")
    parser.add_argument(
        "--case",
        type=str,
        default="The defendant stole a car from the parking lot at midnight. The witness saw the defendant break the window and drive away.",
        help="Case description",
    )
    parser.add_argument("--runs", type=int, default=3, help="Number of runs per configuration")
    parser.add_argument("--mock", action="store_true", help="Use mocked responses (no API calls)")

    args = parser.parse_args()

    run_benchmark(args.case, args.runs, args.mock)
