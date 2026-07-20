"""Jury deliberation and verdict nodes — juror discussion, voting, unanimous verdict."""
import random
import re

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

import src.prompts as p
from src.config import AGENT_MODELS
from src.llm import get_llm, get_structured_llm
from src.logger import get_logger
from src.schemas import (
    JuryPanelOutput,
    JuryVerdict,
    SentencingDecision,
    _pydantic_to_dict,
)
from src.state import TrialState
from src.trial_phases import _get_jx

logger = get_logger(__name__)

# ── Model Pool for Jurors ─────────────────────────────────────────────────────

_JUROR_MODEL_POOL = [
    AGENT_MODELS["Magistrate"],  # qwen-max
    AGENT_MODELS["Prosecutor"],  # qwen-plus-latest
    AGENT_MODELS["Jury Foreperson"],  # qwen-plus-latest
    AGENT_MODELS["Defense Counsel"],  # qwen-plus-latest
]


def generate_dynamic_jury_profiles(state: TrialState) -> list[dict]:
    """Generate case-specific juror profiles for jury jurisdictions.
    Panel size is read from state['jury_count'] (default 12).
    """
    jx = _get_jx(state)
    if not jx["jury_enabled"]:
        return []

    existing = state.get("jury_profiles", [])
    if existing:
        return existing

    n = state.get("jury_count", 12)
    facts = state.get("case_description", "")
    admitted = state.get("admitted_evidence", [])
    fact_sheet = state.get("fact_sheet", "")
    try:
        llm = get_structured_llm(JuryPanelOutput, temperature=0.4, model=AGENT_MODELS["Jury Foreperson"])
        result = llm.invoke(
            [
                SystemMessage(content=p.jury_panel_prompt(jx, n)),
                HumanMessage(
                    content=(
                        f"Generate exactly {n} juror profiles for this case. Each profile must be tied to "
                        "issues visible in the case facts, fact sheet, or admitted evidence. Do not invent "
                        "new case facts, new witnesses, excluded evidence, or external research.\n\n"
                        f"Case facts:\n{facts}\n\n"
                        f"Fact sheet:\n{fact_sheet}\n\n"
                        f"Admitted evidence:\n{admitted}"
                    )
                ),
            ]
        )
        profiles = [_pydantic_to_dict(profile) for profile in result.jurors[:n]]
        if len(profiles) < n:
            # Pad with generic profiles if LLM didn't generate enough
            for juror_id in range(len(profiles) + 1, n + 1):
                profiles.append(
                    {
                        "juror_id": juror_id,
                        "name": f"Juror {juror_id}",
                        "occupation": "Citizen juror",
                        "persona": "Evidence-focused juror",
                        "bias": "Reviews only admitted evidence and the legal standard",
                    }
                )
        # Assign random model to each juror for diversity
        for profile in profiles:
            profile["model"] = random.choice(_JUROR_MODEL_POOL)
        return profiles
    except Exception as e:
        logger.error(f"Jury Profile Generation Error: {e}", exc_info=True)
        fallback_profiles = [
            {
                "juror_id": juror_id,
                "name": f"Juror {juror_id}",
                "occupation": "Citizen juror",
                "persona": "Evidence-focused juror",
                "bias": "Reviews only admitted evidence and the legal standard",
            }
            for juror_id in range(1, n + 1)
        ]
        for profile in fallback_profiles:
            profile["model"] = random.choice(_JUROR_MODEL_POOL)
        return fallback_profiles


# ── Jury Instructions ─────────────────────────────────────────────────────────


def jury_instructions_node(state: TrialState) -> dict:
    """Judge instructs the jury (or, in bench trials, summarises the law for themselves)."""
    logger.info("--- JURY INSTRUCTIONS ---")
    jx = _get_jx(state)
    try:
        judge_llm = get_llm(temperature=0.1, model=AGENT_MODELS["Judge"])
        msg = judge_llm.invoke(
            [
                SystemMessage(content=p.judge_prompt(jx)),
                HumanMessage(
                    content=(
                        f"{'Instruct the jury' if jx['jury_enabled'] else 'Summarise the applicable law for the bench deliberation'}. "
                        f"Clearly state:\n"
                        f"1. The applicable standard of proof: {jx['legal_standard']}\n"
                        f"2. The specific elements that must be proven\n"
                        f"3. That the {'jury' if jx['jury_enabled'] else 'court'} must consider ONLY the admitted evidence\n"
                        f"4. The excluded evidence that must be disregarded\n\n"
                        f"Case facts summary:\n{state.get('fact_sheet', state.get('case_description', ''))}"
                    )
                ),
            ]
        )
        return {"transcript": [AIMessage(content=msg.content, name="Judge")]}
    except Exception as e:
        logger.error(f"Jury Instructions Error: {e}", exc_info=True)
        return {
            "transcript": [
                AIMessage(content=f"[Jury instructions could not be generated: {e}]", name="System"),
            ]
        }


# ── Jury Deliberation ─────────────────────────────────────────────────────────


def _parse_juror_vote(raw_text: str) -> tuple[str, str]:
    """
    Parse a juror's response to extract their statement and vote.
    Returns (statement, vote) where vote is one of:
    'Guilty', 'Not Guilty', 'Liable', 'Not Liable', 'Undecided'
    """
    lines = [line.strip() for line in raw_text.split("\n") if line.strip()]
    vote = "Undecided"
    statement = raw_text

    vote_patterns = [
        r"vote:\s*(.+)$",
        r"^(guilty|not guilty|liable|not liable|undecided)\s*[.!?]?\s*$",
        r"i\s+(?:find\s+the\s+defendant\s+)?(guilty|not guilty|liable|not liable)",
        r"(?:my\s+vote\s+is|i\s+vote\s*:?)\s*(guilty|not guilty|liable|not liable|undecided)",
        r"(?:i\s+(?:believe|conclude|determine)\s+(?:the\s+defendant\s+is|that\s+the\s+defendant\s+is))\s*(guilty|not guilty|liable|not liable)",
        r"(?:the\s+(?:defendant|accused)\s+is)\s*(guilty|not guilty|liable|not liable)",
        r"(?:burden\s+(?:met|not\s+met|satisfied|not\s+satisfied))",
        r"(?:evidence\s+(?:sufficient|insufficient|meets\s+the\s+standard|does\s+not\s+meet))",
    ]

    for line in reversed(lines):
        line_lower = line.lower()

        for pattern in vote_patterns:
            match = re.search(pattern, line_lower)
            if match:
                vote_text = match.group(1) if match.lastindex else line_lower
                vote_text = vote_text.strip()

                if "not guilty" in vote_text or "not liable" in vote_text:
                    if "not guilty" in vote_text:
                        vote = "Not Guilty"
                    else:
                        vote = "Not Liable"
                elif "guilty" in vote_text:
                    vote = "Guilty"
                elif "liable" in vote_text:
                    vote = "Liable"
                elif "undecided" in vote_text:
                    vote = "Undecided"
                elif "not met" in vote_text or "insufficient" in vote_text or "does not meet" in vote_text:
                    vote = "Not Guilty"
                elif "met" in vote_text or "sufficient" in vote_text or "meets" in vote_text:
                    vote = "Guilty"

                statement = "\n".join(line for line in lines if not re.search(pattern, line.lower())).strip()
                if not statement:
                    statement = raw_text
                return statement, vote

    for line in lines:
        line_lower = line.lower()
        if "not guilty" in line_lower:
            return raw_text, "Not Guilty"
        if "not liable" in line_lower:
            return raw_text, "Not Liable"

    return statement, vote


def _call_single_juror(
    juror_profile: dict,
    jx: dict,
    admitted: list,
    excluded: list,
    fact_sheet: str,
    prior_statements: list[str],
    round_num: int,
) -> tuple[str, str]:
    """
    Call a single juror as their own LLM agent.
    Returns (statement_text, vote_string).
    """
    from src.llm import get_llm

    juror_llm = get_llm(
        temperature=0.4, model=juror_profile.get("model", AGENT_MODELS.get("Jury Foreperson", "qwen-plus-latest"))
    )

    prior_block = ""
    if prior_statements:
        prior_block = "\n\nFellow jurors have said:\n" + "\n".join(f"  - {s}" for s in prior_statements[-8:])

    name = juror_profile.get("name", f"Juror {juror_profile.get('juror_id', '?')}")
    occupation = juror_profile.get("occupation", "Citizen juror")
    persona = juror_profile.get("persona", "Impartial juror")
    bias = juror_profile.get("bias", "Evidence-focused")

    try:
        resp = juror_llm.invoke(
            [
                SystemMessage(content=p.juror_prompt(jx, juror_profile)),
                HumanMessage(
                    content=(
                        f"Round {round_num} of jury deliberation.\n\n"
                        f"Your profile: {name}, {occupation}. Persona: {persona}. Lens: {bias}\n\n"
                        f"Admitted evidence:\n{admitted}\n\n"
                        f"Excluded evidence (do NOT consider):\n{excluded}\n\n"
                        f"Case summary:\n{fact_sheet}"
                        f"{prior_block}\n\n"
                        f"In 2-4 sentences, state your deliberation position grounded in the admitted evidence. "
                        f"Then on a new line, clearly state your vote as: Vote: Guilty / Not Guilty / Liable / Not Liable / Undecided"
                    )
                ),
            ]
        )
        raw = resp.content.strip()
        return _parse_juror_vote(raw)
    except Exception as e:
        logger.error(f"[Juror {juror_profile.get('juror_id')} call error] {e}", exc_info=True)
        return "Based on the admitted evidence, I am deliberating carefully.", "Undecided"


def jury_deliberation_node(state: TrialState) -> dict:
    """
    Standards-based deliberation.
    - Jury trials: each juror is called as an INDIVIDUAL LLM agent (up to _MAX_INDIVIDUAL_JUROR_CALLS).
      Each reads what prior jurors said, building a real debate. Foreperson then summarises.
    - Bench trials: Judge renders a single reasoned verdict.
    """
    logger.info("--- JURY DELIBERATION ---")
    jx = _get_jx(state)
    rounds = state.get("deliberation_rounds", 0) + 1
    admitted = state.get("admitted_evidence", [])
    excluded = state.get("excluded_evidence", [])
    fact_sheet = state.get("fact_sheet", state.get("case_description", ""))
    transcript = []
    prev_snapshot = state.get("deliberation_snapshot", {})

    try:
        # ── BENCH TRIAL ───────────────────────────────────────────────────────
        if not jx["jury_enabled"]:
            judge_llm = get_structured_llm(JuryVerdict, temperature=0.1, model=AGENT_MODELS["Judge"])
            verdict_res = judge_llm.invoke(
                [
                    SystemMessage(content=p.judge_prompt(jx)),
                    HumanMessage(
                        content=(
                            "Render the bench verdict as the finder of fact. Apply only the admitted evidence "
                            f"to the standard of {jx['legal_standard']}. Do not consider excluded evidence.\n\n"
                            f"Admitted evidence:\n{admitted}\n\n"
                            f"Excluded evidence:\n{excluded}\n\n"
                            f"Case summary:\n{fact_sheet}\n\n"
                            "Return your verdict as a JSON object."
                        )
                    ),
                ]
            )
            snapshot = {
                "type": "bench",
                "round": rounds,
                "total": 1,
                "guilty_or_liable_count": 1 if verdict_res.verdict in ["Guilty", "Liable"] else 0,
                "not_guilty_or_not_liable_count": 1 if verdict_res.verdict in ["Not Guilty", "Not Liable"] else 0,
                "undecided_count": 0,
                "verdict": verdict_res.verdict,
                "rationale": verdict_res.rationale,
                "positions": [
                    {
                        "juror_id": 1,
                        "name": "Bench",
                        "occupation": "Presiding judge",
                        "persona": "Finder of fact",
                        "bias": "Bound by admitted evidence and the governing standard",
                        "stance": verdict_res.verdict,
                        "quote": verdict_res.rationale,
                    }
                ],
            }
            transcript.append(
                AIMessage(
                    content=f"Bench verdict: {verdict_res.verdict}. {verdict_res.rationale}",
                    name="Judge",
                )
            )
            return {
                "deliberation_rounds": rounds,
                "jury_profiles": snapshot.get("positions", []),
                "deliberation_snapshot": snapshot,
                "main_verdict": verdict_res.verdict,
                "transcript": transcript,
            }

        # ── JURY TRIAL — Individual juror calls ───────────────────────────────
        n = state.get("jury_count", 12)
        profiles = generate_dynamic_jury_profiles(state)
        if not profiles:
            profiles = [
                {
                    "juror_id": juror_id,
                    "name": f"Juror {juror_id}",
                    "occupation": "Citizen juror",
                    "persona": "Evidence-focused juror",
                    "bias": "Reviews only admitted evidence and the governing standard",
                    "model": random.choice(_JUROR_MODEL_POOL),
                }
                for juror_id in range(1, n + 1)
            ]
        jx["jury_profiles"] = profiles

        # Announce deliberation round
        if rounds == 1:
            transcript.append(
                AIMessage(
                    content=(
                        f"Members of the jury, we will now deliberate. Remember the Judge's instructions: "
                        f"apply ONLY the admitted evidence to the standard of '{jx['legal_standard']}'. "
                        f"We have {len(profiles)} jurors. Let us hear each voice."
                    ),
                    name="Foreperson",
                )
            )
        else:
            prev_guilty = prev_snapshot.get("guilty_or_liable_count", 0)
            prev_not_guilty = prev_snapshot.get("not_guilty_or_not_liable_count", 0)
            prev_undecided = prev_snapshot.get("undecided_count", 0)
            transcript.append(
                AIMessage(
                    content=(
                        f"The jury is deliberating further. Round {rounds}. "
                        f"Previous tally: {prev_guilty} for burden met, {prev_not_guilty} for burden not met, "
                        f"{prev_undecided} undecided. Jurors, please reconsider your positions in light of "
                        f"the discussion so far. If you remain unconvinced, state why clearly."
                    ),
                    name="Foreperson",
                )
            )

        prior_statements: list[str] = []
        juror_votes: dict[int, str] = {}
        juror_positions: list[dict] = []

        prev_positions = prev_snapshot.get("positions", [])
        for pp in prev_positions:
            prior_statements.append(
                f"{pp.get('name', 'Juror')}: {pp.get('quote', '')} [Vote: {pp.get('stance', 'Undecided')}]"
            )

        for i, profile in enumerate(profiles):
            juror_id = profile.get("juror_id", i + 1)
            name = profile.get("name", f"Juror {juror_id}")
            statement, vote = _call_single_juror(profile, jx, admitted, excluded, fact_sheet, prior_statements, rounds)
            prior_statements.append(f"{name}: {statement} [Vote: {vote}]")
            juror_votes[juror_id] = vote
            juror_positions.append(
                {
                    **profile,
                    "stance": vote,
                    "quote": statement,
                }
            )
            transcript.append(
                AIMessage(
                    content=statement,
                    name=f"Juror {juror_id}",
                )
            )

        all_votes = list(juror_votes.values())
        guilty_count = sum(1 for v in all_votes if v in ["Guilty", "Liable"])
        not_guilty_count = sum(1 for v in all_votes if v in ["Not Guilty", "Not Liable"])
        undecided_count = sum(1 for v in all_votes if v == "Undecided")

        # Determine verdict from tally
        total = len(all_votes) or n
        # Supermajority required (75% threshold)
        threshold = max(int(total * 0.75), 1)
        if guilty_count >= threshold:
            final_verdict = "Guilty" if jx.get("case_type") == "Criminal" else "Liable"
        elif not_guilty_count >= threshold:
            final_verdict = "Not Guilty" if jx.get("case_type") == "Criminal" else "Not Liable"
        else:
            final_verdict = "Hung"

        reached_verdict = final_verdict != "Hung"
        if rounds >= 3 and final_verdict == "Hung":
            if guilty_count > not_guilty_count:
                final_verdict = "Guilty" if jx.get("case_type") == "Criminal" else "Liable"
                reached_verdict = True
            elif not_guilty_count > guilty_count:
                final_verdict = "Not Guilty" if jx.get("case_type") == "Criminal" else "Not Liable"
                reached_verdict = True
            else:
                final_verdict = "Hung"

        # ── Foreperson delivers verdict ────────────────────────────────────────
        vote_summary = (
            f"{guilty_count} for burden met, {not_guilty_count} for burden not met, {undecided_count} undecided."
        )
        if reached_verdict:
            verdict_msg = f"Round {rounds}: {vote_summary} The jury reaches a verdict: {final_verdict}."
        elif rounds >= 3:
            verdict_msg = f"Round {rounds} (final): {vote_summary} The jury remains deadlocked. Declaring mistrial due to hung jury."
            final_verdict = "Hung"
        else:
            verdict_msg = f"Round {rounds}: {vote_summary} The jury continues deliberation."

        transcript.append(
            AIMessage(
                content=verdict_msg,
                name="Foreperson",
            )
        )

        snapshot = {
            "type": "jury",
            "round": rounds,
            "total": total,
            "guilty_or_liable_count": guilty_count,
            "not_guilty_or_not_liable_count": not_guilty_count,
            "undecided_count": undecided_count,
            "verdict": final_verdict,
            "rationale": verdict_msg,
            "positions": juror_positions,
        }

        return {
            "deliberation_rounds": rounds,
            "jury_profiles": profiles,
            "deliberation_snapshot": snapshot,
            "main_verdict": final_verdict if reached_verdict else None,
            "transcript": transcript,
        }

    except Exception as e:
        logger.error(f"Jury Deliberation Error: {e}", exc_info=True)
        fallback_msg = AIMessage(content=f"[Jury deliberation error: {e}]", name="System")
        return {
            "deliberation_rounds": rounds,
            "transcript": transcript + [fallback_msg],
        }


# ── Shadow Jury ───────────────────────────────────────────────────────────────


async def async_shadow_jury(jury_id: int, case_facts: str, admitted: list, legal_standard: str, model: str):
    """Async single shadow jury evaluation."""
    llm = get_structured_llm(JuryVerdict, temperature=0.4, model=model)
    try:
        res = await llm.ainvoke(
            [
                SystemMessage(
                    content=(
                        f"You are an independent shadow juror in a {legal_standard} case. "
                        f"Apply the standard '{legal_standard}' to the admitted evidence only. "
                        f"Cite specific evidence items by name in your rationale. "
                        f"Provide a clear rationale and return your verdict as a json object."
                    )
                ),
                HumanMessage(
                    content=(
                        f"Admitted evidence:\n{admitted}\n\n"
                        f"Case summary:\n{case_facts}\n\n"
                        f"Return your verdict as a JSON object."
                    )
                ),
            ]
        )
        return {"vote": res.verdict, "rationale": res.rationale, "id": jury_id}
    except Exception as e:
        logger.error(f"Shadow Jury {jury_id} Error: {e}", exc_info=True)
        return {"vote": "Hung", "rationale": "I could not reach a decision.", "id": jury_id}


def shadow_jury_node(state: TrialState) -> dict:
    """Spawns N independent shadow juries to estimate verdict probability."""
    logger.info("--- SHADOW JURIES ---")
    jx = _get_jx(state)
    jury_count = state.get("shadow_jury_count", 20)
    case_facts = state.get("fact_sheet", state.get("case_description", ""))
    admitted = state.get("admitted_evidence", [])
    legal_standard = jx["legal_standard"]

    import asyncio as _asyncio

    async def run_all():
        chunk_size = 5
        results = []
        for i in range(0, jury_count, chunk_size):
            chunk = range(i, min(i + chunk_size, jury_count))
            tasks = [
                async_shadow_jury(j, case_facts, admitted, legal_standard, random.choice(_JUROR_MODEL_POOL))
                for j in chunk
            ]
            results.extend(await _asyncio.gather(*tasks))
            await _asyncio.sleep(1)
        return results

    all_verdicts = _asyncio.run(run_all())
    burden_met_votes = sum(1 for v in all_verdicts if v["vote"] in ["Guilty", "Liable"])
    burden_not_met_votes = sum(1 for v in all_verdicts if v["vote"] in ["Not Guilty", "Not Liable"])
    hung_votes = sum(1 for v in all_verdicts if v["vote"] == "Hung")
    win_prob = burden_met_votes / jury_count if jury_count > 0 else 0.0

    narrative = []
    show_count = jury_count
    for v in all_verdicts[:show_count]:
        narrative.append({"name": f"Shadow Juror {v['id'] + 1}", "content": f"{v['rationale']} [Vote: {v['vote']}]"})

    return {
        "shadow_jury_results": {
            "win_probability": win_prob,
            "burden_met_votes": burden_met_votes,
            "burden_not_met_votes": burden_not_met_votes,
            "hung_votes": hung_votes,
            "total_juries": jury_count,
            "narrative": narrative,
        }
    }


# ── Sentencing ─────────────────────────────────────────────────────────────────


def sentencing_node(state: TrialState) -> dict:
    """Runs after a Guilty/Liable verdict. Prosecution argues aggravation,
    defence argues mitigation, and the Judge pronounces sentence."""
    verdict = state.get("main_verdict")
    if verdict not in ("Guilty", "Liable"):
        logger.info("--- SENTENCING SKIPPED (no guilty/liable verdict) ---")
        return {"transcript": []}

    logger.info("--- SENTENCING ---")
    jx = _get_jx(state)
    fact_sheet = state.get("fact_sheet", state.get("case_description", ""))
    admitted = state.get("admitted_evidence", [])
    transcript = []

    try:
        pros_llm = get_llm(temperature=0.7, model=AGENT_MODELS["Prosecutor"])
        def_llm = get_llm(temperature=0.7, model=AGENT_MODELS["Defense Counsel"])
        judge_llm = get_structured_llm(SentencingDecision, temperature=0.1, model=AGENT_MODELS["Judge"])

        pros_msg = pros_llm.invoke(
            [
                SystemMessage(content=p.prosecutor_sentencing_prompt(jx)),
                HumanMessage(
                    content=(
                        f"Argue for the maximum sentence in 60 words or fewer.\n\n"
                        f"Admitted evidence:\n{admitted}\n\n"
                        f"Case summary:\n{fact_sheet}\n\n"
                        f"Verdict: {verdict}"
                    )
                ),
            ]
        )
        transcript.append(AIMessage(content=pros_msg.content, name="Prosecutor"))

        def_msg = def_llm.invoke(
            [
                SystemMessage(content=p.defense_sentencing_prompt(jx)),
                HumanMessage(
                    content=(
                        f"Argue for the minimum sentence in 60 words or fewer.\n\n"
                        f"Admitted evidence:\n{admitted}\n\n"
                        f"Case summary:\n{fact_sheet}\n\n"
                        f"Verdict: {verdict}\n\n"
                        f'Prosecution argued:\n"{pros_msg.content}"'
                    )
                ),
            ]
        )
        transcript.append(AIMessage(content=def_msg.content, name="Defense Counsel"))

        result = judge_llm.invoke(
            [
                SystemMessage(content=p.judge_sentencing_prompt(jx)),
                HumanMessage(
                    content=(
                        f"Prosecution aggravation: {pros_msg.content}\n\n"
                        f"Defence mitigation: {def_msg.content}\n\n"
                        f'Pronounce sentence. Return JSON with "sentence", "rationale", and "term".'
                    )
                ),
            ]
        )
        sentence_text = result.sentence
        if result.term:
            sentence_text += f"\n\n{result.term}"
        transcript.append(AIMessage(content=sentence_text, name="Judge"))

        return {"transcript": transcript, "sentence": _pydantic_to_dict(result)}
    except Exception as e:
        logger.error(f"Sentencing Error: {e}", exc_info=True)
        return {
            "transcript": [
                AIMessage(content=f"[Sentencing could not be completed: {e}]", name="System"),
            ]
        }
