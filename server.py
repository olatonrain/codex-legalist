"""
server.py
─────────
FastAPI backend for Codex legalist.

Endpoints
─────────
GET  /                          → serves index.html
GET  /static/*                  → static assets
GET  /api/health                → health check
GET  /api/jurisdictions         → list supported countries + legal data
POST /api/demo                  → load a demo case, returns opening sequence
POST /api/trial/start           → start a live LLM trial, returns opening sequence
POST /api/trial/step            → run one phase step, returns new transcript entries
POST /api/trial/magistrate      → run magistrate clarifying-question node
POST /api/trial/human_question  → agent submits a question to the human during trial
POST /api/trial/human_answer    → human submits an answer to an agent's question
POST /api/upload                → parse an uploaded case file (PDF/DOCX/TXT, max 10 MB)
POST /api/upload_audio          → transcribe an uploaded audio file (max 10 MB)
POST /api/benchmark/run         → run benchmark comparing raw LLM vs single-agent vs multi-agent

Run
───
    uvicorn server:app --reload --port 8000
"""

from __future__ import annotations

import json as _json
import os
import re
import time
import uuid
from collections import defaultdict
from pathlib import Path
from typing import Dict, List

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from legalist.agents import generate_dramatic_opening, run_trial_step
from legalist.data import DEMO_CASES
from legalist.parser import extract_text
from src.config import COUNTRY_LIST, DEFAULT_COUNTRY, JURISDICTIONS
from src.insight import _compute_cache_key
from src.insight import generate_one as generate_insight
from src.logger import get_logger
from src.security import detect_prompt_injection

logger = get_logger(__name__)

# ── App ───────────────────────────────────────────────────────────────────────

app = FastAPI(title="Codex legalist API", version="1.0.0")

CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def check_api_key():
    """Warn if QWEN_API_KEY is missing — backend won't crash but LLM calls will fail."""
    if not os.getenv("QWEN_API_KEY"):
        logger.warning(
            "QWEN_API_KEY is not set. LLM calls will fail until a valid key is configured. "
            "Set it in .env or export QWEN_API_KEY=your_key"
        )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Catch-all handler that ensures all errors return JSON, never HTML."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(status_code=500, content={"detail": f"Internal server error: {str(exc)}"})


BASE_DIR = Path(__file__).parent

MAX_UPLOAD_BYTES = 10 * 1024 * 1024

_rate_limit_store: dict[str, list[float]] = defaultdict(list)
RATE_LIMIT_WINDOW = 60
RATE_LIMIT_MAX = 30

# In-memory insight cache: key = sha256(case_hash + "|" + perspective)
_insight_cache: dict[str, dict] = {}

# Serve static assets (JS, CSS, images) from /static
STATIC_DIR = BASE_DIR / "static"
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    client_ip = request.client.host if request.client else "unknown"
    now = time.time()
    window_start = now - RATE_LIMIT_WINDOW

    _rate_limit_store[client_ip] = [t for t in _rate_limit_store[client_ip] if t > window_start]

    if not _rate_limit_store[client_ip]:
        del _rate_limit_store[client_ip]

    if client_ip in _rate_limit_store and len(_rate_limit_store[client_ip]) >= RATE_LIMIT_MAX:
        return JSONResponse(status_code=429, content={"detail": "Rate limit exceeded. Try again later."})

    _rate_limit_store[client_ip].append(now)
    response = await call_next(request)
    return response


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
    demo_key: str  # "theft" | "contract"
    shadow_juries: int = 20


@app.post("/api/demo")
def load_demo(req: DemoRequest):
    case = DEMO_CASES.get(req.demo_key)
    if not case:
        raise HTTPException(404, f"Demo '{req.demo_key}' not found")

    script = case["trial_script"]

    return {
        "title": case["title"],
        "jurisdiction": case.get("jurisdiction", "—"),
        "description": case["description"],
        "questions": case["questions"],
        "verdict": case["verdict"],
        "win_probability": case["win_probability"],
        "sensitivity": case["sensitivity"],
        "shadow_jury_narrative": case.get("shadow_jury_narrative", []),
        "script": script,  # full script for the client to stream
        "total_steps": len(script),
    }


# ── File Upload ───────────────────────────────────────────────────────────────


@app.post("/api/upload")
async def upload_case_file(file: UploadFile = File(...)):
    raw = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(raw) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "File too large. Maximum 10 MB.")
    text = extract_text(raw, file.filename or "upload.txt")
    if not text.strip():
        raise HTTPException(400, "Could not extract text from file")
    if detect_prompt_injection(text):
        raise HTTPException(400, "[CONTEMPT OF COURT] Prompt injection detected in uploaded file.")
    return {"filename": file.filename, "text": text, "char_count": len(text)}


@app.post("/api/upload_audio")
async def upload_audio_file(file: UploadFile = File(...)):
    raw = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(raw) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "File too large. Maximum 10 MB.")
    from src.audio import transcribe_audio

    try:
        text = transcribe_audio(raw, file.filename or "audio.wav")
    except Exception as exc:
        raise HTTPException(400, f"Could not transcribe audio: {exc}")
    if not text.strip():
        raise HTTPException(
            400, "Could not transcribe audio from file. The audio service returned an empty transcript."
        )
    if detect_prompt_injection(text):
        raise HTTPException(400, "[CONTEMPT OF COURT] Prompt injection detected in audio transcript.")
    return {"filename": file.filename, "text": text, "char_count": len(text)}


# ── Magistrate Questions ──────────────────────────────────────────────────────


class MagistrateRequest(BaseModel):
    case_text: str
    country: str = DEFAULT_COUNTRY
    case_type: str = "Criminal"
    shadow_juries: int = 20
    jury_count: int = 12


@app.post("/api/trial/magistrate")
def run_magistrate(req: MagistrateRequest):
    jx = JURISDICTIONS.get(req.country, JURISDICTIONS[DEFAULT_COUNTRY])
    try:
        from src.nodes import magistrate_node
        from src.state import create_initial_state

        state = create_initial_state(
            case_description=req.case_text,
            country=req.country,
            jurisdiction_system=jx["system"],
            jurisdiction_procedure=jx["procedure"],
            criminal_standard=jx["criminal_standard"],
            civil_standard=jx["civil_standard"],
            evidence_rules=jx["evidence_rules"],
            jury_enabled=jx["jury"],
            cross_examination=jx["cross"],
            court_address=jx["address"],
            case_type=req.case_type,
            shadow_jury_count=req.shadow_juries,
            jury_count=req.jury_count,
        )
        result = magistrate_node(state)
        questions = [item["question"] for item in result.get("clarifying_questions", [])]
        witnesses = result.get("witness_queue", [])
        missing_evidence = result.get("missing_evidence", [])
        missing_witnesses = result.get("missing_witnesses", [])
        identified_evidence = result.get("identified_evidence", [])
        return {
            "questions": questions,
            "witness_queue": witnesses,
            "missing_evidence": missing_evidence,
            "missing_witnesses": missing_witnesses,
            "identified_evidence": identified_evidence,
        }
    except Exception as exc:
        logger.error(f"[magistrate] Error: {exc}", exc_info=True)
        return _magistrate_fallback(req.case_text)


def _magistrate_fallback(case_text: str) -> dict:
    """Keyword-based fallback when the LLM magistrate call fails.
    Only asks about information the text genuinely doesn't mention.
    """
    lower = case_text.lower()

    # ── Detect timeline mentions ──────────────────────────────────
    has_timeline = any(
        w in lower
        for w in [
            "date",
            "time",
            "when",
            "day",
            "month",
            "year",
            "week",
            "hour",
            "minute",
            "midnight",
            "noon",
            "morning",
            "afternoon",
            "evening",
            "january",
            "february",
            "march",
            "april",
            "may",
            "june",
            "july",
            "august",
            "september",
            "october",
            "november",
            "december",
            "jan",
            "feb",
            "mar",
            "apr",
            "jun",
            "jul",
            "aug",
            "sep",
            "oct",
            "nov",
            "dec",
            "2020",
            "2021",
            "2022",
            "2023",
            "2024",
            "2025",
            "2026",
            "yesterday",
            "today",
            "last night",
            "this morning",
            "o'clock",
            "pm",
            "am",
        ]
    ) or bool(re.search(r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b", lower))

    # ── Detect evidence mentions ──────────────────────────────────
    has_evidence = any(
        w in lower
        for w in [
            "evidence",
            "document",
            "exhibit",
            "photo",
            "video",
            "record",
            "cctv",
            "footage",
            "camera",
            "recording",
            "audio",
            "image",
            "contract",
            "agreement",
            "nda",
            "email",
            "letter",
            "report",
            "fingerprint",
            "dna",
            "forensic",
            "medical",
            "receipt",
            "statement",
            "affidavit",
            "screenshot",
            "log",
            "database",
            "file",
            "archive",
            "subpoena",
            "warrant",
        ]
    )

    # ── Detect person / witness mentions ──────────────────────────
    has_witness = any(
        w in lower
        for w in [
            "witness",
            "testimony",
            "saw",
            "heard",
            "observed",
            "plaintiff",
            "defendant",
            "victim",
            "accused",
            "complainant",
            "respondent",
            "claimant",
            "doctor",
            "nurse",
            "officer",
            "detective",
            "agent",
            "manager",
            "owner",
            "employee",
            "director",
            "ceo",
            "expert",
            "specialist",
            "consultant",
            "analyst",
            "bystander",
            "neighbour",
            "neighbor",
            "friend",
            "colleague",
            "eyewitness",
            "witnesses",
        ]
    ) or bool(re.search(r"\b[A-Z][a-z]+ [A-Z][a-z]+\b", case_text))

    # ── Detect relationship mentions ──────────────────────────────
    has_relationship = any(
        w in lower
        for w in [
            "relationship",
            "prior",
            "previous",
            "knew",
            "acquaintance",
            "married",
            "spouse",
            "husband",
            "wife",
            "partner",
            "brother",
            "sister",
            "mother",
            "father",
            "parent",
            "friend",
            "enemy",
            "stranger",
            "colleague",
            "coworker",
            "boss",
            "subordinate",
            "client",
            "customer",
            "tenant",
            "landlord",
            "neighbour",
            "neighbor",
            "relative",
            "family",
        ]
    )

    questions = []
    if not has_timeline:
        questions.append("What is the timeline of the key events?")
    if not has_evidence:
        questions.append("Are there any physical evidence items?")
    if not has_witness:
        questions.append("Who are the key witnesses in this case?")
    if not has_relationship:
        questions.append("Is there a prior relationship between the parties?")

    if len(questions) == 0:
        # Everything seems covered, but add a generic opener
        questions.append("Can you confirm the above facts are accurate?")
    elif len(questions) < 2:
        questions.append("What specific legal outcome is being sought?")

    return {
        "questions": questions[:5],
        "witness_queue": [],
        "missing_evidence": [],
        "missing_witnesses": [],
    }


# ── Live Trial: Start ─────────────────────────────────────────────────────────


class TrialStartRequest(BaseModel):
    case_text: str
    case_title: str = "Custom Case"
    country: str = DEFAULT_COUNTRY
    case_type: str = "Criminal"
    human_answers: Dict[str, str] = {}
    missing_evidence_answers: Dict[str, str] = {}
    missing_witnesses_answers: Dict[str, str] = {}
    witness_queue: List[str] = []
    shadow_juries: int = 20
    jury_count: int = 12


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

    jx = JURISDICTIONS.get(req.country, JURISDICTIONS[DEFAULT_COUNTRY])

    enriched_case = req.case_text
    if req.missing_evidence_answers:
        enriched_case += "\n\n[Additional Evidence Provided During Pre-Trial:]\n"
        for item, details in req.missing_evidence_answers.items():
            enriched_case += f"- {item}: {details}\n"
    if req.missing_witnesses_answers:
        enriched_case += "\n\n[Additional Witnesses Provided During Pre-Trial:]\n"
        for item, details in req.missing_witnesses_answers.items():
            enriched_case += f"- {item}: {details}\n"

    opening_lines = generate_dramatic_opening(
        case_title=req.case_title,
        country=req.country,
        system=jx["system"],
        procedure=jx["procedure"],
        case_type=req.case_type,
        address=jx["address"],
    )

    from src.state import create_initial_state

    graph_state = create_initial_state(
        case_description=enriched_case,
        country=req.country,
        jurisdiction_system=jx["system"],
        jurisdiction_procedure=jx["procedure"],
        criminal_standard=jx["criminal_standard"],
        civil_standard=jx["civil_standard"],
        evidence_rules=jx["evidence_rules"],
        jury_enabled=jx["jury"],
        cross_examination=jx["cross"],
        court_address=jx["address"],
        case_type=req.case_type,
        shadow_jury_count=req.shadow_juries,
        jury_count=req.jury_count,
        human_answers=req.human_answers,
        missing_evidence_answers=req.missing_evidence_answers,
        missing_witnesses_answers=req.missing_witnesses_answers,
        witness_queue=req.witness_queue,
    )

    if graph_state["jury_enabled"]:
        try:
            from src.nodes import generate_dynamic_jury_profiles

            graph_state["jury_profiles"] = generate_dynamic_jury_profiles(graph_state)
        except Exception as exc:
            logger.error(f"[trial_start] Jury profile generation skipped: {exc}", exc_info=True)
            graph_state.setdefault("errors", []).append(f"Jury profile generation failed: {exc}")

    return {
        "opening_lines": opening_lines,  # dramatic courtroom opening
        "graph_state": graph_state,
        "live_step": "discovery",
        "jurisdiction": f"{jx['flag']} {req.country} · {jx['system']}",
    }


def _deserialize_transcript(entries: list) -> list[BaseMessage]:
    """Restore BaseMessage objects from dict transcript entries.
    Keeps the server-side state with real BaseMessage objects
    while the wire format uses plain dicts.
    """
    _type_map = {
        "human": HumanMessage,
        "system": SystemMessage,
        "ai": AIMessage,
    }
    result: list[BaseMessage] = []
    for msg in entries:
        if isinstance(msg, BaseMessage):
            result.append(msg)
        elif isinstance(msg, dict):
            msg_type = msg.get("type", "ai").lower()
            cls = _type_map.get(msg_type, AIMessage)
            result.append(
                cls(
                    content=msg.get("content", ""),
                    name=msg.get("name") or msg.get("agent") or "System",
                )
            )
        elif isinstance(msg, str):
            result.append(AIMessage(content=msg, name="System"))
        else:
            result.append(AIMessage(content=str(msg), name="System"))
    return result


def _serialize_transcript(entries: list) -> list[dict]:
    """Convert transcript entries (AIMessage or dict) to JSON-safe dicts."""
    serialized = []
    for msg in entries:
        if isinstance(msg, dict):
            serialized.append(msg)
        else:
            type_name = "ai"
            if isinstance(msg, HumanMessage):
                type_name = "human"
            elif isinstance(msg, SystemMessage):
                type_name = "system"
            serialized.append(
                {
                    "type": type_name,
                    "name": getattr(msg, "name", None) or "System",
                    "content": getattr(msg, "content", str(msg)),
                }
            )
    return serialized


# ── Live Trial: Step ──────────────────────────────────────────────────────────


class TrialStepRequest(BaseModel):
    live_step: str
    graph_state: dict


@app.post("/api/trial/step")
def trial_step(req: TrialStepRequest):
    try:
        # Restore BaseMessage objects in transcript before passing to node functions
        if isinstance(req.graph_state.get("transcript"), list):
            req.graph_state["transcript"] = _deserialize_transcript(req.graph_state["transcript"])

        pending_q = req.graph_state.get("pending_human_question")
        if pending_q:
            # Serialize transcript back to dicts for the response
            serialized = _serialize_transcript(req.graph_state.get("transcript", []))
            req.graph_state["transcript"] = serialized
            return {
                "messages": [],
                "graph_state": req.graph_state,
                "current_step": req.live_step,
                "next_step": req.live_step,
                "pending_human_question": pending_q,
            }

        messages, new_state, next_step = run_trial_step(req.live_step, req.graph_state)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    except Exception as exc:
        raise HTTPException(500, f"Trial step failed: {exc}")

    # Serialize transcript to dicts for the JSON response
    transcript = new_state.get("transcript", [])
    serialized = _serialize_transcript(transcript)
    new_state["transcript"] = serialized

    response: dict = {
        "messages": messages,
        "graph_state": new_state,
        "current_step": req.live_step,
        "next_step": next_step,
    }

    if next_step == "done":
        sjr = new_state.get("shadow_jury_results", {})
        snapshot = new_state.get("deliberation_snapshot", {})
        verdict_str = new_state.get("main_verdict") or "No Verdict Reached"

        actual_jury = {
            "verdict": verdict_str,
            "type": snapshot.get("type", "unknown"),
            "round": snapshot.get("round", 0),
            "total": snapshot.get("total", 0),
            "guilty_or_liable_count": snapshot.get("guilty_or_liable_count", 0),
            "not_guilty_or_not_liable_count": snapshot.get("not_guilty_or_not_liable_count", 0),
            "undecided_count": snapshot.get("undecided_count", 0),
            "rationale": snapshot.get("rationale", ""),
            "positions": snapshot.get("positions", []),
        }

        if snapshot.get("total"):
            total_actual = snapshot["total"]
            burden_met = snapshot.get("guilty_or_liable_count", 0)
            burden_not = snapshot.get("not_guilty_or_not_liable_count", 0)
            undecided = snapshot.get("undecided_count", 0)
            win_prob = burden_met / total_actual if total_actual > 0 else 0.0
            sensitivity = (
                f"The jury voted {burden_met}-{burden_not}"
                + (f" with {undecided} undecided" if undecided > 0 else "")
                + f". {snapshot.get('rationale', '')}"
            )
        elif sjr.get("total_juries"):
            win_prob = sjr.get("win_probability", 0.5)
            total_actual = sjr.get("total_juries", 20)
            burden_met = sjr.get("burden_met_votes", 0)
            sensitivity = (
                f"{burden_met} of {total_actual} shadow juries found the evidence met the burden of proof. "
                + (
                    "The defence successfully raised doubt."
                    if win_prob < 0.5
                    else "The prosecution's evidence was compelling."
                )
            )
        else:
            win_prob = 0.0 if verdict_str in ("Not Guilty", "Not Liable") else 1.0
            total_actual = 0
            sensitivity = "No-case submission or early termination — no jury analysis was reached."

        response["verdict_data"] = {
            "verdict": verdict_str,
            "probability": win_prob,
            "sensitivity": sensitivity,
            "juries": total_actual,
            "actual_jury": actual_jury,
            "shadow_jury": sjr if sjr else None,
        }
        sentence_data = new_state.get("sentence")
        if sentence_data:
            response["verdict_data"]["sentence"] = sentence_data

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
    if detect_prompt_injection(req.answer):
        raise HTTPException(400, "[CONTEMPT OF COURT] Prompt injection detected in human answer.")
    try:
        pending = req.graph_state.get("pending_human_question", {})
        if not pending:
            raise HTTPException(400, "No pending question to answer")

        if "human_input_buffer" not in req.graph_state:
            req.graph_state["human_input_buffer"] = []
        req.graph_state["human_input_buffer"].append(
            {
                "agent": pending.get("agent", "Unknown"),
                "question": pending.get("question", ""),
                "answer": req.answer,
                "context": pending.get("context", ""),
            }
        )

        req.graph_state["pending_human_question"] = None

        return {"status": "answer_recorded", "graph_state": req.graph_state}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(500, f"Failed to record answer: {exc}")


# ── Save / Load ────────────────────────────────────────────────────────────────

SAVES_DIR = BASE_DIR / "output" / "saves"


class SaveRequest(BaseModel):
    graph_state: dict
    case_title: str = "Untitled Case"
    country: str = DEFAULT_COUNTRY
    current_step: str = "discovery"
    elapsed_seconds: float = 0.0
    phase_timings: dict = {}


@app.post("/api/trial/save")
def save_trial(req: SaveRequest):
    SAVES_DIR.mkdir(parents=True, exist_ok=True)
    save_id = uuid.uuid4().hex[:8]

    transcript = req.graph_state.get("transcript", [])
    req.graph_state["transcript"] = _serialize_transcript(transcript)

    payload = {
        "save_id": save_id,
        "case_title": req.case_title,
        "country": req.country,
        "saved_at": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
        "verdict": req.graph_state.get("main_verdict") or "In Progress",
        "current_step": req.current_step,
        "elapsed_seconds": req.elapsed_seconds,
        "phase_timings": req.phase_timings,
        "graph_state": req.graph_state,
    }

    save_path = SAVES_DIR / f"{save_id}.json"
    try:
        with open(save_path, "w") as f:
            _json.dump(payload, f, indent=2)
    except OSError as exc:
        raise HTTPException(500, f"Failed to save trial: {exc}")

    return {"save_id": save_id, "saved_at": payload["saved_at"]}


@app.get("/api/trial/saves")
def list_saves():
    SAVES_DIR.mkdir(parents=True, exist_ok=True)
    saves = []
    for path in sorted(SAVES_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            with open(path) as f:
                data = _json.load(f)
            saves.append(
                {
                    "save_id": data.get("save_id", path.stem),
                    "case_title": data.get("case_title", "Untitled"),
                    "saved_at": data.get("saved_at", "Unknown"),
                    "verdict": data.get("verdict", "In Progress"),
                    "country": data.get("country", ""),
                }
            )
        except Exception:
            saves.append(
                {
                    "save_id": path.stem,
                    "case_title": path.stem,
                    "saved_at": "Unknown",
                    "verdict": "Unknown",
                    "country": "",
                }
            )
    return {"saves": saves}


@app.get("/api/trial/load/{save_id}")
def load_trial(save_id: str):
    save_path = SAVES_DIR / f"{save_id}.json"
    if not save_path.exists():
        raise HTTPException(404, f"Save '{save_id}' not found.")
    try:
        with open(save_path) as f:
            data = _json.load(f)
    except Exception as exc:
        raise HTTPException(500, f"Failed to load save: {exc}")
    graph_state = data.get("graph_state", {})
    graph_state["transcript"] = _deserialize_transcript(graph_state.get("transcript", []))
    return {
        "graph_state": graph_state,
        "case_title": data.get("case_title", ""),
        "country": data.get("country", DEFAULT_COUNTRY),
        "current_step": data.get("current_step", "discovery"),
        "elapsed_seconds": data.get("elapsed_seconds", 0.0),
        "phase_timings": data.get("phase_timings", {}),
        "verdict": data.get("verdict", "In Progress"),
    }


@app.delete("/api/trial/save/{save_id}")
def delete_trial_save(save_id: str):
    save_path = SAVES_DIR / f"{save_id}.json"
    if not save_path.exists():
        raise HTTPException(404, f"Save '{save_id}' not found.")
    try:
        save_path.unlink()
    except OSError as exc:
        raise HTTPException(500, f"Failed to delete save: {exc}")
    return {"deleted": save_id}


# ── Transcript Export ─────────────────────────────────────────────────────────


@app.api_route("/api/trial/transcript", methods=["GET", "POST"])
async def export_transcript(request: Request):
    body = {}
    if request.method == "POST":
        try:
            body = await request.json()
        except Exception:
            pass

    format_type = request.query_params.get("format", "json") or body.get("format", "json")
    graph_state = body.get("graph_state", {})

    if not graph_state.get("transcript"):
        raise HTTPException(400, "No transcript data provided.")

    transcript = graph_state.get("transcript", [])
    entries = []
    for msg in transcript:
        if isinstance(msg, dict):
            entries.append(
                {
                    "agent": msg.get("name") or msg.get("agent") or "System",
                    "text": msg.get("content") or msg.get("text", ""),
                }
            )
        else:
            entries.append(
                {"agent": getattr(msg, "name", "System") or "System", "text": getattr(msg, "content", str(msg))}
            )

    if format_type == "markdown":
        md = f"# Trial Transcript\n\n**Case:** {graph_state.get('case_title', 'Untitled')}\n"
        md += f"**Country:** {graph_state.get('country', 'Unknown')}\n"
        md += f"**Verdict:** {graph_state.get('main_verdict', 'In Progress')}\n\n---\n\n"
        for e in entries:
            md += f"**[{e['agent']}]** {e['text']}\n\n"
        return {"transcript": md, "format": "markdown", "entry_count": len(entries)}

    if format_type == "txt":
        txt = ""
        for e in entries:
            txt += f"[{e['agent']}]: {e['text']}\n"
        return {"transcript": txt, "format": "txt", "entry_count": len(entries)}

    return {"transcript": entries, "format": "json", "entry_count": len(entries)}


# ── Benchmark ─────────────────────────────────────────────────────────────────


class BenchmarkRequest(BaseModel):
    case_description: str
    trial_context: dict = None
    num_runs: int = 3
    use_mock: bool = False


@app.post("/api/benchmark/run")
def run_benchmark(req: BenchmarkRequest):
    try:
        from legalist.benchmark import run_multi_agent_trial, run_raw_llm_query, run_single_agent_trial

        raw_results = []
        single_results = []
        multi_results = []
        errors = []

        ctx = req.trial_context

        for i in range(req.num_runs):
            try:
                raw_results.append(run_raw_llm_query(req.case_description, req.use_mock, ctx))
                single_results.append(run_single_agent_trial(req.case_description, req.use_mock, ctx))
                multi_result = run_multi_agent_trial(req.case_description, req.use_mock, ctx)

                if multi_result.get("error"):
                    errors.append(f"Run {i + 1}: {multi_result.get('reasoning', 'Unknown error')}")
                    break

                multi_results.append(multi_result)
            except Exception as run_exc:
                errors.append(f"Run {i + 1}: {str(run_exc)[:200]}")
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


@app.get("/api/benchmark/run-stream")
def run_benchmark_stream(
    case_description: str = "",
    num_runs: int = 3,
    use_mock: bool = False,
    trial_context: str = None,
):
    """SSE streaming endpoint for benchmark progress.

    Yields events as each run of each approach completes so the frontend can
    display real-time progress.
    """
    import json as _json_mod

    from legalist.benchmark import (
        run_multi_agent_trial as _run_multi,
        run_raw_llm_query as _run_raw,
        run_single_agent_trial as _run_single,
    )

    ctx = _json_mod.loads(trial_context) if trial_context else None

    def event_stream():
        raw_results = []
        single_results = []
        multi_results = []
        errors = []

        for i in range(num_runs):
            # ── Raw LLM ──
            yield f"event: raw_llm_start\ndata: {_json_mod.dumps({'run': i + 1, 'total': num_runs})}\n\n"
            try:
                raw = _run_raw(case_description, use_mock, ctx)
                raw_results.append(raw)
                yield f"event: raw_llm_done\ndata: {_json_mod.dumps(raw)}\n\n"
            except Exception as exc:
                err = {"run": i + 1, "error": str(exc)[:200]}
                yield f"event: raw_llm_done\ndata: {_json_mod.dumps(err)}\n\n"

            # ── Single-Agent ──
            yield f"event: single_start\ndata: {_json_mod.dumps({'run': i + 1})}\n\n"
            try:
                single = _run_single(case_description, use_mock, ctx)
                single_results.append(single)
                yield f"event: single_done\ndata: {_json_mod.dumps(single)}\n\n"
            except Exception as exc:
                err = {"run": i + 1, "error": str(exc)[:200]}
                yield f"event: single_done\ndata: {_json_mod.dumps(err)}\n\n"

            # ── Multi-Agent ──
            try:
                multi = _run_multi(case_description, use_mock, ctx)
                multi_results.append(multi)
                yield f"event: multi_result\ndata: {_json_mod.dumps(multi)}\n\n"
            except Exception as exc:
                err = {"run": i + 1, "error": str(exc)[:200]}
                yield f"event: multi_result\ndata: {_json_mod.dumps(err)}\n\n"

        # Build final aggregate (same shape as POST /api/benchmark/run)
        def safe_avg(results, key, default=0):
            if not results:
                return default
            return sum(r.get(key, default) for r in results) / len(results)

        aggregate = {
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
        yield f"event: complete\ndata: {_json_mod.dumps(aggregate)}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


# ── Counsel Insights ───────────────────────────────────────────────────────────


class InsightRequest(BaseModel):
    graph_state: dict
    perspectives: list[str] = ["defense", "prosecution", "judge"]


@app.post("/api/trial/insight")
def trial_insight(req: InsightRequest):
    valid = {"defense", "prosecution", "judge"}
    requested = [p for p in req.perspectives if p in valid]
    if not requested:
        raise HTTPException(400, "At least one valid perspective required: defense, prosecution, or judge.")

    results: dict[str, dict] = {}
    state = req.graph_state

    for perspective in requested:
        cache_key = _compute_cache_key(state, perspective)
        cached = _insight_cache.get(cache_key)
        if cached:
            results[perspective] = cached
            continue

        try:
            result = generate_insight(state, perspective)
            if isinstance(result, dict) and "error" not in result:
                _insight_cache[cache_key] = result
            results[perspective] = result
        except Exception as exc:
            logger.error("[insight] %s failed: %s", perspective, exc, exc_info=True)
            results[perspective] = {"error": str(exc)}

    return {"insights": results}
