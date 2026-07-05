"""
server.py
─────────
FastAPI backend for Codex Legalis.

Endpoints
─────────
GET  /                     → serves index.html
GET  /static/*             → static assets
POST /api/demo             → load a demo case, returns opening sequence
POST /api/trial/start      → start a live LLM trial, returns opening sequence
POST /api/trial/step       → run one phase step, returns new transcript entries
POST /api/trial/magistrate → run magistrate clarifying-question node
POST /api/upload           → parse an uploaded case file

Run
───
    uvicorn server:app --reload --port 8000
"""
from __future__ import annotations

import os
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from legalis.data import DEMO_CASES, AGENT_STYLE, AGENT_NAME_COLOR
from legalis.parser import extract_text
from legalis.agents import generate_dramatic_opening, run_trial_step, sanitise_content, norm_agent
from src.config import JURISDICTIONS, COUNTRY_LIST
from src.security import detect_prompt_injection
from src.logger import get_logger

logger = get_logger(__name__)

# ── App ───────────────────────────────────────────────────────────────────────

app = FastAPI(title="Codex Legalis API", version="1.0.0")

BASE_DIR = Path(__file__).parent

# Serve static assets (JS, CSS, images) from /static
STATIC_DIR = BASE_DIR / "static"
STATIC_DIR.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


# ── Root → serve the UI ──────────────────────────────────────────────────────

@app.get("/", include_in_schema=False)
def serve_ui():
    return FileResponse(str(BASE_DIR / "index.html"))


# ── Health ────────────────────────────────────────────────────────────────────

@app.get("/api/health")
def health():
    return {"status": "ok", "version": "1.0.0"}


# ── Jurisdiction list ─────────────────────────────────────────────────────────

@app.get("/api/jurisdictions")
def get_jurisdictions():
    return {"countries": COUNTRY_LIST, "data": JURISDICTIONS}


# ── Demo Case ─────────────────────────────────────────────────────────────────

class DemoRequest(BaseModel):
    demo_key: str           # "theft" | "contract"
    shadow_juries: int = 20


@app.post("/api/demo")
def load_demo(req: DemoRequest):
    case = DEMO_CASES.get(req.demo_key)
    if not case:
        raise HTTPException(404, f"Demo '{req.demo_key}' not found")

    script = case["trial_script"]

    return {
        "title":        case["title"],
        "jurisdiction": case.get("jurisdiction", "—"),
        "description":  case["description"],
        "questions":    case["questions"],
        "verdict":      case["verdict"],
        "win_probability": case["win_probability"],
        "sensitivity":  case["sensitivity"],
        "shadow_jury_narrative": case.get("shadow_jury_narrative", []),
        "script":       script,          # full script for the client to stream
        "total_steps":  len(script),
    }


# ── File Upload ───────────────────────────────────────────────────────────────

@app.post("/api/upload")
async def upload_case_file(file: UploadFile = File(...)):
    raw = await file.read()
    text = extract_text(raw, file.filename or "upload.txt")
    if not text.strip():
        raise HTTPException(400, "Could not extract text from file")
    if detect_prompt_injection(text):
        raise HTTPException(400, "[CONTEMPT OF COURT] Prompt injection detected in uploaded file.")
    return {"filename": file.filename, "text": text, "char_count": len(text)}


@app.post("/api/upload_audio")
async def upload_audio_file(file: UploadFile = File(...)):
    raw = await file.read()
    from src.audio import transcribe_audio
    try:
        text = transcribe_audio(raw, file.filename or "audio.wav")
    except Exception as exc:
        raise HTTPException(400, f"Could not transcribe audio: {exc}")
    if not text.strip():
        raise HTTPException(400, "Could not transcribe audio from file. The audio service returned an empty transcript.")
    if detect_prompt_injection(text):
        raise HTTPException(400, "[CONTEMPT OF COURT] Prompt injection detected in audio transcript.")
    return {"filename": file.filename, "text": text, "char_count": len(text)}


# ── Magistrate Questions ──────────────────────────────────────────────────────

class MagistrateRequest(BaseModel):
    case_text:    str
    country:      str  = "Nigeria"
    case_type:    str  = "Criminal"
    shadow_juries: int = 20
    jury_count:   int  = 12


@app.post("/api/trial/magistrate")
def run_magistrate(req: MagistrateRequest):
    jx = JURISDICTIONS.get(req.country, JURISDICTIONS["Nigeria"])
    try:
        from src.nodes import magistrate_node
        state = {
            "case_description":     req.case_text,
            "transcript":           [],
            "fact_sheet":           "",
            "admitted_evidence":    [],
            "excluded_evidence":    [],
            "clarifying_questions": [],
            "human_answers":        {},
            "missing_evidence_answers": {},
            "missing_witnesses_answers": {},
            "pending_human_question": None,
            "human_input_buffer":   [],
            "witness_queue":        [],
            "current_witness":      None,
            "examination_phase":    None,
            "shadow_jury_count":    req.shadow_juries,
            "shadow_jury_model":    "qwen-plus-latest",
            "jury_count":           req.jury_count,
            "audio_enabled":        False,
            "deliberation_rounds":  0,
            "jury_profiles":        [],
            "deliberation_snapshot": {},
            "main_verdict":         None,
            "shadow_jury_results":  {},
            "multimodal_evidence":  [],
            "errors":               [],
            "country":              req.country,
            "jurisdiction_system":  jx["system"],
            "jurisdiction_procedure": jx["procedure"],
            "criminal_standard":    jx["criminal_standard"],
            "civil_standard":       jx["civil_standard"],
            "evidence_rules":       jx["evidence_rules"],
            "jury_enabled":         jx["jury"],
            "cross_examination":    jx["cross"],
            "court_address":        jx["address"],
            "case_type":            req.case_type,
        }
        result = magistrate_node(state)
        questions = [item["question"] for item in result.get("clarifying_questions", [])]
        witnesses = result.get("witness_queue", [])
        missing_evidence = result.get("missing_evidence", [])
        missing_witnesses = result.get("missing_witnesses", [])
        if not questions:
            raise ValueError("No questions returned")
        return {
            "questions": questions,
            "witness_queue": witnesses,
            "missing_evidence": missing_evidence,
            "missing_witnesses": missing_witnesses,
        }
    except Exception as exc:
        logger.error(f"[magistrate] Error: {exc}")
        case_lower = req.case_text.lower()
        questions = []
        if not any(w in case_lower for w in ["date", "time", "when", "day", "month", "year"]):
            questions.append("What is the timeline of the key events?")
        if not any(w in case_lower for w in ["evidence", "document", "exhibit", "photo", "video", "record"]):
            questions.append("Are there any physical evidence items?")
        if not any(w in case_lower for w in ["witness", "testimony", "saw", "heard", "observed"]):
            questions.append("Who are the key witnesses in this case?")
        if not any(w in case_lower for w in ["relationship", "prior", "previous", "knew", "acquaintance"]):
            questions.append("Is there a prior relationship between the parties?")
        if len(questions) < 2:
            questions.append("What specific legal outcome is being sought?")
        return {
            "questions": questions[:5] if questions else ["Can you provide more details about the key events?"],
            "witness_queue": [],
        }


# ── Live Trial: Start ─────────────────────────────────────────────────────────

class TrialStartRequest(BaseModel):
    case_text:      str
    case_title:     str  = "Custom Case"
    country:        str  = "Nigeria"
    case_type:      str  = "Criminal"
    human_answers:  dict = {}
    missing_evidence_answers: dict = {}
    missing_witnesses_answers: dict = {}
    witness_queue:  list = []
    shadow_juries:  int  = 20
    jury_count:     int  = 12


@app.post("/api/trial/start")
def trial_start(req: TrialStartRequest):
    if detect_prompt_injection(req.case_text):
        raise HTTPException(400, "[CONTEMPT OF COURT] Prompt injection detected in case facts.")
    for answer in req.human_answers.values():
        if detect_prompt_injection(str(answer)):
            raise HTTPException(400, "[CONTEMPT OF COURT] Prompt injection detected in magistrate answers.")
    for answer in req.missing_evidence_answers.values():
        if detect_prompt_injection(str(answer)):
            raise HTTPException(400, "[CONTEMPT OF COURT] Prompt injection detected in evidence answers.")
    for answer in req.missing_witnesses_answers.values():
        if detect_prompt_injection(str(answer)):
            raise HTTPException(400, "[CONTEMPT OF COURT] Prompt injection detected in witness answers.")

    jx = JURISDICTIONS.get(req.country, JURISDICTIONS["Nigeria"])

    # Enrich case description with human-provided missing items
    enriched_case = req.case_text
    if req.missing_evidence_answers:
        enriched_case += "\n\n[Additional Evidence Provided During Pre-Trial:]\n"
        for item, details in req.missing_evidence_answers.items():
            enriched_case += f"- {item}: {details}\n"
    if req.missing_witnesses_answers:
        enriched_case += "\n\n[Additional Witnesses Provided During Pre-Trial:]\n"
        for item, details in req.missing_witnesses_answers.items():
            enriched_case += f"- {item}: {details}\n"

    # 1. Generate dramatic AI opening
    opening_lines = generate_dramatic_opening(
        case_title=req.case_title,
        country=req.country,
        system=jx["system"],
        procedure=jx["procedure"],
        case_type=req.case_type,
        address=jx["address"],
    )

    # 2. Build graph state to return to client
    graph_state = {
        "case_description":     enriched_case,
        "transcript":           [],
        "fact_sheet":           "",
        "admitted_evidence":    [],
        "excluded_evidence":    [],
        "clarifying_questions": [],
        "human_answers":        req.human_answers,
        "missing_evidence_answers": req.missing_evidence_answers,
        "missing_witnesses_answers": req.missing_witnesses_answers,
        "witness_queue":        req.witness_queue,
        "current_witness":      None,
        "examination_phase":    None,
        "shadow_jury_count":    req.shadow_juries,
        "shadow_jury_model":    "qwen-plus-latest",
        "jury_count":           req.jury_count,
        "audio_enabled":        False,
        "deliberation_rounds":  0,
        "jury_profiles":        [],
        "deliberation_snapshot": {},
        "main_verdict":         None,
        "shadow_jury_results":  {},
        "multimodal_evidence":  [],
        "errors":               [],
        "country":              req.country,
        "jurisdiction_system":  jx["system"],
        "jurisdiction_procedure": jx["procedure"],
        "criminal_standard":    jx["criminal_standard"],
        "civil_standard":       jx["civil_standard"],
        "evidence_rules":       jx["evidence_rules"],
        "jury_enabled":         jx["jury"],
        "cross_examination":    jx["cross"],
        "court_address":        jx["address"],
        "case_type":            req.case_type,
    }

    if graph_state["jury_enabled"]:
        try:
            from src.nodes import generate_dynamic_jury_profiles
            graph_state["jury_profiles"] = generate_dynamic_jury_profiles(graph_state)
        except Exception as exc:
            logger.error(f"[trial_start] Jury profile generation skipped: {exc}")

    return {
        "opening_lines": opening_lines,   # dramatic courtroom opening
        "graph_state":   graph_state,
        "live_step":     "opening",
        "jurisdiction":  f"{jx['flag']} {req.country} · {jx['system']}",
    }


# ── Live Trial: Step ──────────────────────────────────────────────────────────

class TrialStepRequest(BaseModel):
    live_step:   str
    graph_state: dict


@app.post("/api/trial/step")
def trial_step(req: TrialStepRequest):
    try:
        # Check if there's a pending human question - if so, don't proceed
        pending_q = req.graph_state.get("pending_human_question")
        if pending_q:
            return {
                "messages": [],
                "graph_state": req.graph_state,
                "current_step": req.live_step,
                "next_step": req.live_step,  # Stay on same step
                "pending_human_question": pending_q,
            }
        
        messages, new_state, next_step = run_trial_step(req.live_step, req.graph_state)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    except Exception as exc:
        raise HTTPException(500, f"Trial step failed: {exc}")

    response: dict = {
        "messages":    messages,
        "graph_state": new_state,
        "current_step": req.live_step,
        "next_step":   next_step,
    }

    if next_step == "done":
        sjr       = new_state.get("shadow_jury_results", {})
        verdict_str = new_state.get("main_verdict") or "No Verdict Reached"
        if sjr.get("total_juries"):
            win_prob  = sjr.get("win_probability", 0.5)
            total_j   = sjr.get("total_juries", 20)
            guilty    = sjr.get("guilty_votes", 0)
            sensitivity = (
                f"{guilty} of {total_j} shadow juries found the evidence met the burden of proof. "
                + ("The defence successfully raised doubt." if win_prob < 0.5 else "The prosecution's evidence was compelling.")
            )
        else:
            win_prob  = 0.0 if verdict_str in ("Not Guilty", "Not Liable") else 1.0
            total_j   = 0
            sensitivity = "No-case submission or early termination — shadow jury analysis was not reached."
        response["verdict_data"] = {
            "verdict":     verdict_str,
            "probability": win_prob,
            "sensitivity": sensitivity,
            "juries":      total_j,
        }

    return response


# ── Live Human Input ──────────────────────────────────────────────────────────

class HumanQuestionRequest(BaseModel):
    graph_state: dict
    agent: str
    question: str
    context: str = ""


class HumanAnswerRequest(BaseModel):
    graph_state: dict
    answer: str


@app.post("/api/trial/human_question")
def submit_human_question(req: HumanQuestionRequest):
    """Agent submits a question to the human during trial."""
    try:
        req.graph_state["pending_human_question"] = {
            "agent": req.agent,
            "question": req.question,
            "context": req.context,
        }
        return {"status": "question_pending", "graph_state": req.graph_state}
    except Exception as exc:
        raise HTTPException(500, f"Failed to submit question: {exc}")


@app.post("/api/trial/human_answer")
def submit_human_answer(req: HumanAnswerRequest):
    """Human submits an answer to an agent's question."""
    try:
        pending = req.graph_state.get("pending_human_question", {})
        if not pending:
            raise HTTPException(400, "No pending question to answer")
        
        # Record the Q&A in the human input buffer
        if "human_input_buffer" not in req.graph_state:
            req.graph_state["human_input_buffer"] = []
        req.graph_state["human_input_buffer"].append({
            "agent": pending.get("agent", "Unknown"),
            "question": pending.get("question", ""),
            "answer": req.answer,
            "context": pending.get("context", ""),
        })
        
        # Clear the pending question
        req.graph_state["pending_human_question"] = None
        
        return {"status": "answer_recorded", "graph_state": req.graph_state}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(500, f"Failed to record answer: {exc}")


# ── Benchmark ─────────────────────────────────────────────────────────────────

class BenchmarkRequest(BaseModel):
    case_description: str
    num_runs: int = 3
    use_mock: bool = False


@app.post("/api/benchmark/run")
def run_benchmark(req: BenchmarkRequest):
    try:
        from benchmark import run_raw_llm_query, run_single_agent_trial, run_multi_agent_trial
        
        raw_results = []
        single_results = []
        multi_results = []
        errors = []
        
        for i in range(req.num_runs):
            try:
                raw_results.append(run_raw_llm_query(req.case_description, req.use_mock))
                single_results.append(run_single_agent_trial(req.case_description, req.use_mock))
                multi_result = run_multi_agent_trial(req.case_description, req.use_mock)
                
                if multi_result.get("error"):
                    errors.append(f"Run {i+1}: {multi_result.get('reasoning', 'Unknown error')}")
                    break
                
                multi_results.append(multi_result)
            except Exception as run_exc:
                errors.append(f"Run {i+1}: {str(run_exc)[:200]}")
                break
        
        if not multi_results and errors:
            raise HTTPException(500, f"Benchmark failed: {errors[0]}")
        
        def safe_avg(results, key, default=0):
            if not results:
                return default
            return sum(r.get(key, default) for r in results) / len(results)
        
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
            "total_runs": req.num_runs,
            "errors": errors if errors else None,
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(500, f"Benchmark failed: {exc}")
