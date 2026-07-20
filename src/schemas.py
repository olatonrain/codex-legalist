"""Pydantic schemas — structured output models for LLM agent responses."""
from pydantic import BaseModel, Field


class MagistrateOutput(BaseModel):
    clarifying_questions: list[str] = Field(
        default_factory=list,
        description="Between 0 and 5 critical clarifying questions. Return an EMPTY list if the case facts are complete enough. Never ask about information already present in the facts.",
    )
    witnesses: list[str] = Field(
        default_factory=list,
        description="Named individuals in the case facts who should be called as witnesses. Empty list if none are named. Do NOT invent names. List every named person with a specific role.",
    )
    missing_evidence: list[str] = Field(
        default_factory=list,
        description="Evidence types that are NOT MENTIONED ANYWHERE in the case facts. If the facts describe or reference an evidence item, do NOT list it. Empty list if evidence seems sufficient (preferred).",
    )
    missing_witnesses: list[str] = Field(
        default_factory=list,
        description="Witness types that are NOT MENTIONED ANYWHERE in the case facts. If the facts name an individual or describe a role, do NOT list it. Empty list if witnesses seem sufficient (preferred).",
    )


class ClerkOutput(BaseModel):
    fact_sheet: str = Field(description="Compressed summary of established facts.")
    admitted_evidence: list[str] = Field(description="Formally admitted evidence items.")
    excluded_evidence: list[str] = Field(description="Excluded evidence items (inadmissible).")


class JudgeRuling(BaseModel):
    ruling: str = Field(description="Must be exactly 'SUSTAINED' or 'OVERRULED' or 'SUSTAINED IN PART'.")
    rationale: str = Field(default="", description="Legal basis for the ruling, citing the specific rule of evidence.")
    objection_type: str = Field(
        default="",
        description="The type of objection raised (e.g. hearsay, relevance, speculation, leading, foundation, etc.).",
    )
    limiting_instruction: str = Field(
        default="",
        description="If the ruling is partial (SUSTAINED IN PART), provide a limiting instruction specifying what part is admissible and for what limited purpose. Empty string if not needed.",
    )


class ObjectionOutput(BaseModel):
    objection_type: str = Field(
        description="The specific type of objection: hearsay, relevance, speculation, leading, compound, foundation, narrative, privilege, character, prejudice, best_evidence, authentication, or cumulative."
    )
    rule_cited: str = Field(description="The specific rule number or section from the governing evidence rules.")
    rationale: str = Field(description="Brief explanation of why the evidence should be excluded under this rule.")


class ExaminationObjection(BaseModel):
    should_object: bool = Field(
        default=False, description="Whether to raise an objection to this question during examination"
    )
    objection_type: str = Field(
        default="",
        description="Type of objection: leading, hearsay, speculation, compound, relevance, foundation, argumentative, asked_and_answered, narrative, badgering, or none",
    )
    rule_cited: str = Field(
        default="", description="The specific evidence rule being violated — only required if should_object is true"
    )
    rationale: str = Field(
        default="", description="Brief legal basis for the objection — only required if should_object is true"
    )


class EvidenceObjectionDecision(BaseModel):
    should_object: bool = Field(
        default=False,
        description="True only if the evidence has a genuine, clear admissibility defect. False if the evidence appears admissible — do NOT object just because it is unfavorable.",
    )
    objection_type: str = Field(
        default="",
        description="The specific type of objection if should_object is True: hearsay, relevance, speculation, foundation, privilege, character, prejudice, best_evidence, authentication, or cumulative.",
    )
    rule_cited: str = Field(
        default="",
        description="The specific rule from the governing evidence rules — required only if should_object is True.",
    )
    rationale: str = Field(
        default="",
        description="Brief explanation of the admissibility defect — required only if should_object is True.",
    )
    foundation_missing: str = Field(
        default="",
        description="If foundation is the objection, specify exactly what foundation step is missing (e.g. 'no chain of custody', 'witness cannot identify the document', 'no business records certification').",
    )


class JuryVerdict(BaseModel):
    verdict: str = Field(description="'Guilty', 'Not Guilty', 'Liable', or 'Not Liable'.")
    rationale: str = Field(
        description="Which admitted evidence led to this verdict and whether the legal standard was met."
    )


class JurorProfile(BaseModel):
    juror_id: int = Field(description="Juror number, starting from 1.")
    name: str = Field(description="A plausible juror name.")
    occupation: str = Field(description="Occupation or life experience tied to a case issue.")
    persona: str = Field(description="Short persona label grounded in admitted case issues.")
    bias: str = Field(description="Case-specific lens or concern. Must not invent facts.")


class JuryPanelOutput(BaseModel):
    jurors: list[JurorProfile] = Field(
        description="Juror profiles for a jury trial — exact count specified in the prompt."
    )


class JurorPosition(BaseModel):
    juror_id: int = Field(description="Juror number matching the generated jury panel.")
    stance: str = Field(description="'Guilty', 'Not Guilty', 'Liable', 'Not Liable', or 'Undecided'.")
    quote: str = Field(description="One concise deliberation statement based only on admitted evidence.")


class DeliberationOutput(BaseModel):
    positions: list[JurorPosition] = Field(description="Exactly one position for each juror profile.")
    guilty_or_liable_count: int = Field(description="Number voting Guilty or Liable.")
    not_guilty_or_not_liable_count: int = Field(description="Number voting Not Guilty or Not Liable.")
    undecided_count: int = Field(description="Number still undecided.")
    verdict: str = Field(description="'Guilty', 'Not Guilty', 'Liable', 'Not Liable', or 'Hung'.")
    rationale: str = Field(description="Consensus or deadlock rationale using admitted evidence only.")


class SentencingDecision(BaseModel):
    sentence: str = Field(description="The formal pronouncement of sentence by the judge.")
    rationale: str = Field(
        description="Legal basis for the sentence, citing aggravating and mitigating factors considered."
    )
    term: str = Field(
        default="",
        description="Specific concrete term e.g. '5 years imprisonment', '$50,000 in damages', '3 years probation'.",
    )


class DiscoveryItems(BaseModel):
    items: list[str] = Field(description="List of disclosed evidence items, each described in one sentence.")


class MotionFiling(BaseModel):
    motion_type: str = Field(description="Type of motion: Motion to Suppress, Motion in Limine, or Motion to Dismiss.")
    relief_sought: str = Field(description="What relief is being requested.")
    legal_basis: str = Field(description="Legal rule or authority supporting the motion.")
    argument: str = Field(description="Factual justification for the motion.")


class MotionOpposition(BaseModel):
    argument: str = Field(description="Argument opposing the motion.")
    rule_cited: str = Field(description="Rule or authority supporting the opposition.")


class MotionRulingResult(BaseModel):
    ruling: str = Field(description="Must be exactly 'GRANTED' or 'DENIED'.")
    rationale: str = Field(description="Legal basis for the ruling.")


class TrialLogOutput(BaseModel):
    case_info: str = Field(description="Brief case identification.")
    procedural_timeline: list[str] = Field(description="Chronological list of phases completed.")
    witnesses: list[str] = Field(description="Witnesses called and testimony summaries.")
    evidence_log: str = Field(description="Admitted vs excluded evidence counts.")
    key_rulings: list[str] = Field(description="Most important judicial rulings, 3-5 max.")
    verdict_summary: str = Field(description="Final verdict and basis.")


class ExpertQualRuling(BaseModel):
    qualified: bool = Field(description="True if the witness qualifies as an expert.")
    rationale: str = Field(description="Legal basis for the ruling.")


class CounselInsight(BaseModel):
    summary: str = Field(description="Big-picture analysis from this counsel's perspective.")
    key_strengths: list[str] = Field(description="What was done well or favourable aspects of the case.")
    key_weaknesses: list[str] = Field(description="What needs improvement or what was unfavourable.")
    recommendations: list[str] = Field(description="Actionable advice to improve the case position.")


class InsightResponse(BaseModel):
    insights: dict[str, CounselInsight | dict] = Field(
        description="Per-perspective insights. Keys are 'defense', 'prosecution', 'judge'. "
        "Value is a CounselInsight on success, or {'error': str} on failure."
    )


def _pydantic_to_dict(model: BaseModel) -> dict:
    """Support both Pydantic v1 and v2 in local/dev environments."""
    if hasattr(model, "model_dump"):
        return model.model_dump()
    return model.dict()
