import streamlit as st
import time
import io
import html as _html

st.warning(
    "⚠️ **Deprecated UI** — This Streamlit frontend is no longer actively maintained. "
    "Please use the FastAPI frontend at [http://localhost:8000](http://localhost:8000) for the full experience."
)
try:
    from dotenv import load_dotenv
    load_dotenv()   # loads .env from the project root
except ImportError:
    pass  # python-dotenv not installed; env vars must be set externally

# ─── Page Config ───────────────────────────────────────────────
st.set_page_config(
    page_title="Codex legalist",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ─── Apple-style CSS ───────────────────────────────────────────
st.markdown("""
<style>
/* SF Pro stack — closest Google Fonts equivalent */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

:root {
    --bg:           #0a0a0a;
    --bg-elevated:  #141414;
    --bg-card:      rgba(255,255,255,0.04);
    --bg-card-hover:rgba(255,255,255,0.07);
    --border:       rgba(255,255,255,0.08);
    --border-strong:rgba(255,255,255,0.14);
    --text-primary: #f5f5f7;
    --text-secondary:#86868b;
    --text-tertiary: #48484a;
    --accent:        #0a84ff;
    --accent-warm:   #ff9f0a;
    --green:         #30d158;
    --red:           #ff453a;
    --purple:        #bf5af2;
    --teal:          #5ac8fa;
    --radius-sm:     10px;
    --radius-md:     14px;
    --radius-lg:     20px;
    --blur:          blur(20px) saturate(180%);
}

/* ── Base ── */
* { box-sizing: border-box; }
html, body, .stApp {
    background: var(--bg) !important;
    color: var(--text-primary) !important;
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'SF Pro Text', sans-serif !important;
    -webkit-font-smoothing: antialiased;
}
.block-container { padding: 1.5rem 2rem 2rem !important; max-width: 1400px !important; }
section[data-testid="stSidebar"] {
    background: #0d0d0d !important;
    border-right: 1px solid var(--border) !important;
    padding-top: 1rem;
}
section[data-testid="stSidebar"] > div { padding: 1rem 1rem !important; }
#MainMenu, footer, header { visibility: hidden; }

/* ── Sidebar toggle: always visible so users can re-open after collapsing ── */
[data-testid="collapsedControl"] {
    visibility: visible !important;
    display: flex !important;
    opacity: 1 !important;
    background: rgba(255,255,255,0.05) !important;
    border: 1px solid var(--border) !important;
    border-radius: 8px !important;
    color: var(--text-secondary) !important;
    transition: background 0.15s ease !important;
}
[data-testid="collapsedControl"]:hover {
    background: rgba(255,255,255,0.1) !important;
    color: var(--text-primary) !important;
}


/* ── Scrollbar ── */
::-webkit-scrollbar { width: 4px; height: 4px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: var(--text-tertiary); border-radius: 2px; }

/* ── Top Nav Bar ── */
.nav-bar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0 0 1.5rem 0;
    border-bottom: 1px solid var(--border);
    margin-bottom: 1.5rem;
}
.nav-logo {
    display: flex;
    align-items: center;
    gap: 0.7rem;
}
.nav-logo-icon {
    width: 34px; height: 34px;
    background: linear-gradient(135deg, #1c1c1e, #3a3a3c);
    border-radius: 8px;
    display: flex; align-items: center; justify-content: center;
    font-size: 1.1rem;
    box-shadow: 0 1px 4px rgba(0,0,0,0.5), inset 0 1px 0 rgba(255,255,255,0.06);
}
.nav-logo-text {
    font-size: 1.1rem;
    font-weight: 600;
    color: var(--text-primary);
    letter-spacing: -0.3px;
}
.nav-logo-sub {
    font-size: 0.7rem;
    font-weight: 400;
    color: var(--text-secondary);
    letter-spacing: 0.5px;
    text-transform: uppercase;
    margin-top: -2px;
}
.nav-pill {
    display: inline-flex;
    align-items: center;
    gap: 0.35rem;
    padding: 0.3rem 0.9rem;
    border-radius: 20px;
    font-size: 0.72rem;
    font-weight: 500;
    letter-spacing: 0.3px;
    text-transform: uppercase;
}
.pill-setup    { background: rgba(10,132,255,0.12); color: #0a84ff; border: 1px solid rgba(10,132,255,0.25); }
.pill-pretrial { background: rgba(255,159,10,0.12); color: #ff9f0a; border: 1px solid rgba(255,159,10,0.25); }
.pill-trial    { background: rgba(48,209,88,0.12);  color: #30d158; border: 1px solid rgba(48,209,88,0.25); }
.pill-verdict  { background: rgba(191,90,242,0.12); color: #bf5af2; border: 1px solid rgba(191,90,242,0.25); }
.pill-dot { width: 6px; height: 6px; border-radius: 50%; background: currentColor; animation: pulse 2s ease-in-out infinite; }
@keyframes pulse { 0%,100%{opacity:1} 50%{opacity:0.4} }

/* ── Cards ── */
.card {
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: var(--radius-md);
    padding: 1.1rem 1.25rem;
    margin-bottom: 0.65rem;
    transition: background 0.15s ease;
}
.card:hover { background: var(--bg-card-hover); }
.card-label {
    font-size: 0.68rem;
    font-weight: 600;
    color: var(--text-secondary);
    text-transform: uppercase;
    letter-spacing: 0.8px;
    margin-bottom: 0.5rem;
}

/* ── Transcript ── */
.transcript-pane {
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: var(--radius-lg);
    padding: 0;
    overflow: hidden;
}
.transcript-header {
    padding: 0.85rem 1.25rem;
    border-bottom: 1px solid var(--border);
    display: flex;
    align-items: center;
    justify-content: space-between;
    background: rgba(255,255,255,0.02);
}
.transcript-header span {
    font-size: 0.78rem;
    font-weight: 600;
    color: var(--text-secondary);
    text-transform: uppercase;
    letter-spacing: 0.8px;
}
.transcript-body {
    padding: 1rem 1.25rem;
    min-height: 500px;
    max-height: 580px;
    overflow-y: auto;
    font-size: 0.88rem;
    line-height: 1.65;
}
.msg-row {
  display: flex;
  gap: 12px;
  padding: 10px 12px;
  border-bottom: 1px solid var(--border);
  animation: msgIn 0.25s ease-out;
  align-items: flex-start;
}
.msg-avatar {
  width: 36px;
  height: 36px;
  flex-shrink: 0;
  border-radius: 50%;
  font-size: 0.7rem;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  color: white;
}
.msg-content {
  flex: 1;
  min-width: 0;
}

.msg-name {
  font-size: 0.75rem;
  font-weight: 700;
  margin-bottom: 4px;
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.msg-name .role-tag {
  font-size: 0.6rem;
  font-weight: 600;
  padding: 2px 8px;
  border-radius: 10px;
  text-transform: uppercase;
  letter-spacing: 0.3px;
}

.msg-text {
  font-size: 0.9rem;
  line-height: 1.6;
  color: var(--text);
  word-wrap: break-word;
}
.msg-text .highlight {
  background: rgba(201, 168, 76, 0.15);
  padding: 0 4px;
  border-radius: 3px;
  font-weight: 600;
}

.msg-text .ruling-text {
  display: block;
  margin-top: 6px;
  padding-top: 6px;
  border-top: 1px dashed var(--border);
  font-size: 0.8rem;
  color: var(--muted);
}
/* ===== OBJECTION ITEMS ===== */
.obj-item {
  background: var(--bg);
  border-left: 4px solid #e67e22;
  border-radius: 6px;
  padding: 10px 12px;
  margin-bottom: 8px;
  font-size: 0.8rem;
  line-height: 1.5;
}

.obj-item .obj-who {
  font-weight: 700;
  color: var(--prosecutor);
  font-size: 0.7rem;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.obj-item .obj-ruling {
  margin-top: 4px;
  font-size: 0.7rem;
  color: var(--muted);
  display: flex;
  gap: 8px;
  align-items: center;
}

.obj-item .obj-ruling .ruling-result {
  font-weight: 700;
  padding: 2px 8px;
  border-radius: 10px;
  font-size: 0.65rem;
}

.obj-item .obj-ruling .sustained {
  background: rgba(192, 57, 43, 0.12);
  color: var(--prosecutor);
}

.obj-item .obj-ruling .overruled {
  background: rgba(39, 174, 96, 0.12);
  color: var(--defense);
}
/* agent colours */
.av-judge      { background: rgba(255,159,10,0.15); color: #ff9f0a; }
.av-prosecutor { background: rgba(255,69,58,0.15);  color: #ff453a; }
.av-defense    { background: rgba(10,132,255,0.15);  color: #0a84ff; }
.av-witness    { background: rgba(48,209,88,0.15);   color: #30d158; }
.av-magistrate { background: rgba(255,159,10,0.12);  color: #ff9f0a; }
.av-foreperson { background: rgba(191,90,242,0.15);  color: #bf5af2; }
.av-juror      { background: rgba(90,200,250,0.12);  color: #5ac8fa; }
.av-checker    { background: rgba(255,69,58,0.10);   color: #ff6961; }
.av-system     { background: rgba(255,255,255,0.04); color: #48484a; }

/* ── Verdict gauge ── */
.verdict-ring-wrap { text-align: center; padding: 1rem 0 0.5rem; }
.verdict-num {
    font-size: 3.2rem; font-weight: 700;
    letter-spacing: -2px; line-height: 1;
}
.verdict-sub {
    font-size: 0.68rem; font-weight: 500;
    color: var(--text-secondary);
    text-transform: uppercase; letter-spacing: 1px;
    margin-top: 0.2rem;
}

/* ── Sidebar labels ── */
.sidebar-section {
    font-size: 0.68rem; font-weight: 600;
    color: var(--text-secondary);
    text-transform: uppercase; letter-spacing: 1px;
    margin: 1.4rem 0 0.5rem;
}
.demo-btn-wrap button {
    background: var(--bg-card) !important;
    border: 1px solid var(--border) !important;
    color: var(--text-primary) !important;
    border-radius: var(--radius-sm) !important;
    font-size: 0.83rem !important;
    transition: all 0.15s ease !important;
}
.demo-btn-wrap button:hover {
    background: var(--bg-card-hover) !important;
    border-color: var(--border-strong) !important;
}

/* ── Empty state ── */
.empty-state {
    min-height: 500px;
    display: flex; flex-direction: column;
    align-items: center; justify-content: center;
    color: var(--text-tertiary);
    gap: 0.6rem;
}
.empty-icon {
    width: 56px; height: 56px;
    background: rgba(255,255,255,0.04);
    border-radius: 14px;
    display: flex; align-items: center; justify-content: center;
    font-size: 1.6rem;
    margin-bottom: 0.4rem;
}

/* ── Upload drop zone ── */
.stFileUploader { border-radius: var(--radius-md) !important; }
[data-testid="stFileUploaderDropzone"] {
    background: var(--bg-card) !important;
    border: 1.5px dashed var(--border-strong) !important;
    border-radius: var(--radius-md) !important;
    transition: all 0.2s ease !important;
}
[data-testid="stFileUploaderDropzone"]:hover {
    border-color: var(--accent) !important;
    background: rgba(10,132,255,0.04) !important;
}

/* ── Form inputs ── */
.stTextInput input, .stTextArea textarea {
    background: var(--bg-card) !important;
    border: 1px solid var(--border) !important;
    border-radius: var(--radius-sm) !important;
    color: var(--text-primary) !important;
    font-family: inherit !important;
}
.stTextInput input:focus, .stTextArea textarea:focus {
    border-color: var(--accent) !important;
    box-shadow: 0 0 0 3px rgba(10,132,255,0.15) !important;
}

/* ── Slider ── */
.stSlider [data-baseweb="slider"] { padding: 0.2rem 0 !important; }

/* ── Progress bar ── */
.stProgress > div > div { background: var(--accent) !important; border-radius: 4px !important; }
.stProgress { background: var(--bg-card) !important; border-radius: 4px !important; }

/* ── Primary button ── */
.stButton > button[kind="primary"] {
    background: var(--accent) !important;
    border: none !important;
    border-radius: var(--radius-sm) !important;
    font-weight: 500 !important;
    font-size: 0.88rem !important;
    letter-spacing: -0.1px !important;
    padding: 0.55rem 1.2rem !important;
    transition: all 0.15s ease !important;
    box-shadow: 0 1px 3px rgba(10,132,255,0.3) !important;
}
.stButton > button[kind="primary"]:hover {
    background: #0971e3 !important;
    box-shadow: 0 2px 8px rgba(10,132,255,0.4) !important;
}
/* Secondary / default button */
.stButton > button:not([kind="primary"]) {
    background: var(--bg-card) !important;
    border: 1px solid var(--border) !important;
    color: var(--text-primary) !important;
    border-radius: var(--radius-sm) !important;
    font-weight: 500 !important;
    font-size: 0.83rem !important;
    transition: all 0.15s ease !important;
}
.stButton > button:not([kind="primary"]):hover {
    background: var(--bg-card-hover) !important;
    border-color: var(--border-strong) !important;
}

/* ── Toggle ── */
.stToggle { margin-top: 0.3rem; }

/* ── Divider ── */
hr { border-color: var(--border) !important; margin: 1rem 0 !important; }

/* ── Evidence tags ── */
.ev-tag {
    display: inline-flex; align-items: center; gap: 0.3rem;
    padding: 0.2rem 0.65rem;
    border-radius: 6px;
    font-size: 0.75rem; font-weight: 500;
    margin: 0.15rem 0.1rem;
}
.ev-admitted { background: rgba(48,209,88,0.12);  color: #30d158; border: 1px solid rgba(48,209,88,0.2); }
.ev-excluded { background: rgba(255,69,58,0.12);  color: #ff453a; border: 1px solid rgba(255,69,58,0.2); }
/* ===== EVIDENCE BOARD ===== */
.evidence-item {
  padding: 12px 14px;
  border-radius: 8px;
  border: 1px solid var(--border);
  background: var(--card);
  transition: all 0.2s;
  cursor: pointer;
  position: relative;
}

.evidence-item:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.06);
}

.evidence-item .ev-status {
  position: absolute;
  top: 8px;
  right: 8px;
  font-size: 0.6rem;
  font-weight: 700;
  padding: 2px 8px;
  border-radius: 10px;
  background: rgba(39, 174, 96, 0.12);
  color: var(--defense);
}

.evidence-item.excluded .ev-status {
  background: rgba(192, 57, 43, 0.12);
  color: var(--prosecutor);
}

.evidence-item .ev-icon {
  font-size: 20px;
  color: var(--gold);
  margin-bottom: 4px;
}

.evidence-item .ev-title {
  font-size: 0.8rem;
  font-weight: 700;
  margin-bottom: 2px;
}

.evidence-item .ev-desc {
  font-size: 0.7rem;
  color: var(--muted);
  line-height: 1.4;
}

.evidence-item .ev-ruling {
  font-size: 0.65rem;
  margin-top: 6px;
  padding-top: 4px;
  border-top: 1px dashed var(--border);
  color: var(--muted);
}

/* ===== RIGHT PANEL ===== */
.right-section {
  margin-bottom: 24px;
}

.right-section .panel-title {
  margin-bottom: 8px;
}

.clerk-summary {
  background: var(--bg);
  border-radius: 8px;
  padding: 12px;
  font-size: 0.8rem;
  line-height: 1.6;
  max-height: 200px;
  overflow-y: auto;
  border-left: 3px solid var(--clerk);
}

/* ===== RESPONSIVE TWEAKS ===== */
@media (max-width: 768px) {
  .msg-row {
    padding: 8px 10px;
    gap: 8px;
  }
  .msg-avatar {
    width: 28px;
    height: 28px;
    font-size: 0.6rem;
  }
  .msg-text {
    font-size: 0.85rem;
  }
  .evidence-grid {
    grid-template-columns: 1fr;
  }
}
</style>
""", unsafe_allow_html=True)

# ─── Demo Data ────────────────────────────────────────────────
from legalist.data import DEMO_CASES

# ─── Agent Mapping ─────────────────────────────────────────────
from legalist.data import AGENT_STYLE, AGENT_NAME_COLOR

def render_msg(agent, text, *, trusted_html: bool = False):
    """Render a single transcript message.

    Args:
        agent: The speaking agent name (used for styling only — always a known string).
        text:  The message body. User-supplied text MUST pass trusted_html=False (default)
               so it is HTML-escaped before injection. Internal/AI-generated HTML fragments
               that are known-safe can pass trusted_html=True.
    """
    abbr, av_cls = AGENT_STYLE.get(agent, ("?", "av-system"))
    name_color = AGENT_NAME_COLOR.get(agent, "#86868b")
    # Sanitise unless the caller explicitly marks the content as trusted HTML
    safe_text = text if trusted_html else _html.escape(str(text))
    return f'''<div class="msg-row">
  <div class="msg-avatar {av_cls}">{abbr}</div>
  <div class="msg-content">
    <div class="msg-name" style="color:{name_color}">{agent}</div>
    <div class="msg-text">{safe_text}</div>
  </div>
</div>'''

# ─── File Parsing ─────────────────────────────────────────────
from legalist.parser import extract_text as _extract_text

def extract_text_from_file(uploaded_file) -> str:
    """Parse PDF, DOCX, or TXT and return plain text."""
    raw = uploaded_file.read()
    return _extract_text(raw, uploaded_file.name)

# ─── Session State ─────────────────────────────────────────────
defaults = {
    "phase": "Setup",
    "case_text": "",
    "case_title": "",
    "transcript_html": [],
    "demo_key": None,
    "trial_step": 0,
    "trial_running": False,
    "verdict_data": None,
    "questions": [],
    "evidence_board": [],
    "multimodal_evidence": [],
    "audio_enabled": False,
    "live_audio_bytes": None,
    "witness_queue": [],
    "graph_state": {},
    "live_step": "opening",
    # Jurisdiction
    "selected_country": "Nigeria",
    "selected_case_type": "---",
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ─── Phase pill rendering ─────────────────────────────────────
PHASE_PILL = {
    "Setup":    ("pill-setup",    "Setup"),
    "Pre-Trial":("pill-pretrial", "Pre-Trial"),
    "Trial":    ("pill-trial",    "Trial Active"),
    "Verdict":  ("pill-verdict",  "Verdict"),
}
pcls, plabel = PHASE_PILL.get(st.session_state.phase, ("pill-setup", st.session_state.phase))
active_dot = '<span class="pill-dot"></span>' if st.session_state.phase == "Trial" else ""

# ─── Top Nav ──────────────────────────────────────────────────
st.markdown(f"""
<div class="nav-bar">
  <div class="nav-logo">
    <div class="nav-logo-icon">⚖️</div>
    <div>
      <div class="nav-logo-text">Codex legalist</div>
      <div class="nav-logo-sub">Autonomous Courtroom Society</div>
    </div>
  </div>
  <span class="nav-pill {pcls}">{active_dot} {plabel}</span>
</div>
""", unsafe_allow_html=True)

# ─── Sidebar ─────────────────────────────────────────────────
with st.sidebar:
    st.markdown('<div class="sidebar-section">Configuration</div>', unsafe_allow_html=True)
    shadow_juries = st.slider("Shadow Juries", 10, 50, 20, 5,
                              help="Independent simulated juries for win-probability analysis.")
    jury_count = st.slider("Jury Panel Size", 6, 15, 12, 1,
                           help="Number of jurors on the main deliberation panel (only applies to jury-enabled jurisdictions).")
    audio_enabled = st.toggle("Audio Playback", value=st.session_state.audio_enabled,
                              help="Narrate trial proceedings via TTS.")
    st.session_state.audio_enabled = audio_enabled

    st.markdown('<div class="sidebar-section">Demo Cases</div>', unsafe_allow_html=True)
    st.caption("Pre-simulated · no API key required")

    def load_demo(key):
        st.session_state.demo_key = key
        st.session_state.case_text = DEMO_CASES[key]["description"]
        st.session_state.case_title = DEMO_CASES[key]["title"]
        st.session_state.questions = DEMO_CASES[key]["questions"]
        st.session_state.phase = "Pre-Trial"
        st.session_state.transcript_html = []
        st.session_state.trial_step = 0
        st.session_state.trial_running = False
        st.session_state.verdict_data = None
        st.session_state.evidence_board = []

    with st.container():
        st.markdown('<div class="demo-btn-wrap">', unsafe_allow_html=True)
        if st.button("💻  State v. Volkov  ·  Ransomware", use_container_width=True):
            load_demo("ransomware")
            st.rerun()
        if st.button("🛢️  CPA v. Meridian  ·  Oil Spill", use_container_width=True):
            load_demo("spill")
            st.rerun()
        if st.button("💉  State v. Blake  ·  Malpractice", use_container_width=True):
            load_demo("clinical")
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="sidebar-section">Session</div>', unsafe_allow_html=True)
    if st.button("Reset", use_container_width=True):
        for k, v in defaults.items():
            st.session_state[k] = v
        st.rerun()

# ─── Main Layout ──────────────────────────────────────────────
col_left, col_right = st.columns([13, 7], gap="large")

# ══ LEFT: Transcript ══════════════════════════════════════════
with col_left:
    phase_label_map = {
        "Setup": "Transcript",
        "Pre-Trial": "Transcript",
        "Trial": "Live Transcript",
        "Verdict": "Trial Transcript",
    }
    pane_label = phase_label_map.get(st.session_state.phase, "Transcript")
    count_tag = f'<span style="color:var(--text-tertiary);font-weight:400">{len(st.session_state.transcript_html)} entries</span>' if st.session_state.transcript_html else ""

    # Build the transcript pane HTML in one go so tags don't break across Streamlit elements
    html_out = f"""<div class="transcript-pane">
  <div class="transcript-header">
    <span>📋 {pane_label}</span>
    {count_tag}
  </div>
  <div class="transcript-body" id="tx-body">"""

    if st.session_state.phase == "Setup":
        html_out += """\n    <div class="empty-state">
      <div class="empty-icon">⚖️</div>
      <div style="font-size:0.95rem;font-weight:500;color:var(--text-secondary)">No trial in session</div>
      <div style="font-size:0.8rem;color:var(--text-tertiary)">Upload a case file or select a demo →</div>
    </div>"""
    elif not st.session_state.transcript_html:
        html_out += """\n    <div class="empty-state">
      <div style="font-size:0.85rem;color:var(--text-tertiary)">Awaiting commencement…</div>
    </div>"""
    else:
        html_out += "\n" + "".join(st.session_state.transcript_html)

    html_out += "\n  </div>\n</div>"
    
    st.markdown(html_out, unsafe_allow_html=True)

# ══ RIGHT: Control Panel ══════════════════════════════════════
with col_right:

    # ── SETUP ──────────────────────────────────────────────────
    if st.session_state.phase == "Setup":
        st.markdown('<div class="card-label" style="margin-top:0">Case Input</div>', unsafe_allow_html=True)

        tab_record, tab_upload, tab_text = st.tabs(["🎙 Record", "📎 Upload", "✏️ Paste"])

        with tab_record:
            st.caption("Describe the case out loud — we'll transcribe and use it as your case facts.")
            live_audio = st.audio_input("Record case description", label_visibility="collapsed")
            if live_audio:
                st.session_state.live_audio_bytes = live_audio.read()
                st.info("Transcribing recording...")
                from src.audio import transcribe_audio
                text = transcribe_audio(st.session_state.live_audio_bytes)
                if text:
                    st.session_state.case_text = text
                    st.success("✓ Recording transcribed successfully.")
                    st.text_area("Transcribed Text", value=text, disabled=True, height=150)
                else:
                    st.error("Failed to transcribe recording. Check API key.")

        with tab_upload:
            st.caption("Upload a case brief **and/or** evidence files in one go.")
            all_files = st.file_uploader(
                "Drop files here",
                type=["pdf", "docx", "txt", "png", "jpg", "jpeg", "mp4", "mp3", "wav"],
                accept_multiple_files=True,
                help="Case docs: PDF · DOCX · TXT  |  Evidence: images, video, audio",
                label_visibility="collapsed"
            )
            if all_files:
                case_docs   = [f for f in all_files if f.name.lower().split(".")[-1] in ("pdf", "docx", "txt")]
                evidence_fx = [f for f in all_files if f not in case_docs]
                if case_docs:
                    case_file = case_docs[0]
                    text = extract_text_from_file(case_file)
                    st.session_state.case_text = text
                    st.success(f"✓ Parsed `{case_file.name}` ({len(text)} chars)")
                if evidence_fx:
                    st.session_state.multimodal_evidence.extend(evidence_fx)
                    st.info(f"✓ Attached {len(evidence_fx)} evidence files.")

        with tab_text:
            st.caption("Paste or type the case facts directly.")
            typed = st.text_area(
                "Case facts",
                value=st.session_state.case_text
                      if not st.session_state.case_text.startswith("[Live recording") else "",
                height=190,
                placeholder="Enter facts, evidence summaries, witness names…",
                label_visibility="collapsed"
            )
            if typed.strip():
                st.session_state.case_text = typed

        st.markdown("<br/>", unsafe_allow_html=True)
        st.markdown('<div class="card-label">Jurisdiction</div>', unsafe_allow_html=True)

        from src.config import JURISDICTIONS, COUNTRY_LIST
        col_country, col_type = st.columns([3, 2])
        with col_country:
            selected_country = st.selectbox(
                "Country",
                options=COUNTRY_LIST,
                index=COUNTRY_LIST.index(st.session_state.get("selected_country", "Nigeria")),
                label_visibility="collapsed",
                help="Sets the applicable rules of evidence, procedure type, and burden of proof."
            )
            st.session_state.selected_country = selected_country
        with col_type:
            selected_case_type = st.selectbox(
                "Case Type",
                options=["Criminal", "Civil"],
                index=0 if st.session_state.get("selected_case_type", "Criminal") == "Criminal" else 1,
                label_visibility="collapsed"
            )
            st.session_state.selected_case_type = selected_case_type

        # Show jurisdiction summary
        jx_info = JURISDICTIONS[selected_country]
        std = jx_info["criminal_standard"] if selected_case_type == "Criminal" else jx_info["civil_standard"]
        st.markdown(
            f'<div class="card" style="margin-top:0.4rem;padding:0.75rem 1rem">'  # noqa
            f'<div style="font-size:0.72rem;color:var(--text-secondary);line-height:1.6">'
            f'{jx_info["flag"]} <strong>{jx_info["system"]}</strong> · {jx_info["procedure"].title()}<br>'
            f'Standard: <em>{std}</em><br>'
            f'Rules: {jx_info["evidence_rules"][:60]}…<br>'
            f'{"Jury trial" if jx_info["jury"] else "Bench trial"} · '
            f'{"Adversarial cross-examination" if jx_info["cross"] else "Judge-led examination"}'
            f'</div></div>',
            unsafe_allow_html=True
        )

        st.markdown("<br/>", unsafe_allow_html=True)
        st.session_state.audio_enabled = st.checkbox("🎙️ Enable Trial Audio (TTS)", value=st.session_state.get("audio_enabled", False))
        can_start = bool(st.session_state.case_text.strip())
        if st.button("Begin Trial →", type="primary", use_container_width=True, disabled=not can_start):
            st.session_state.case_title = case_file.name if 'case_file' in dir() and case_file else "Custom Case"
            # Store jurisdiction into session so graph can read it
            jx = JURISDICTIONS[selected_country]
            st.session_state.jurisdiction_data = {
                "country":                selected_country,
                "jurisdiction_system":    jx["system"],
                "jurisdiction_procedure": jx["procedure"],
                "criminal_standard":      jx["criminal_standard"],
                "civil_standard":         jx["civil_standard"],
                "evidence_rules":         jx["evidence_rules"],
                "jury_enabled":           jx["jury"],
                "cross_examination":      jx["cross"],
                "court_address":          jx["address"],
                "case_type":              selected_case_type,
            }
            st.session_state.phase = "Pre-Trial"
            # Ask the Magistrate LLM for real, case-specific clarifying questions
            with st.spinner("\u2696\ufe0f Magistrate reviewing the case…"):
                try:
                    from src.nodes import magistrate_node
                    _mag_state = {
                        "case_description":     st.session_state.case_text,
                        "transcript":           [], "fact_sheet": "",
                        "admitted_evidence":    [], "excluded_evidence": [],
                        "clarifying_questions": [], "human_answers": {},
                        "witness_queue":         [], "current_witness": None,
                        "examination_phase":     None,
                        "shadow_jury_count":     shadow_juries,
                        "shadow_jury_model":     "qwen-plus-latest",
                        "jury_count":            jury_count,
                        "audio_enabled":         audio_enabled,
                        "deliberation_rounds":   0, "main_verdict": None,
                        "shadow_jury_results":   {}, "multimodal_evidence": [],
                        "errors":                [],
                        **st.session_state.jurisdiction_data,
                    }
                    _mag_result = magistrate_node(_mag_state)
                    _qs = [item["question"] for item in _mag_result.get("clarifying_questions", [])]
                    st.session_state.questions = _qs if _qs else [
                        "What is the timeline of the key events?",
                        "Are there any physical evidence items?",
                        "Who are the key witnesses in this case?",
                        "Is there a prior relationship between the parties?",
                        "What specific legal outcome is being sought?",
                    ]
                    st.session_state.witness_queue = _mag_result.get("witness_queue", [])
                except Exception:
                    st.warning(f"Magistrate unavailable \u2014 using standard questions.")
                    st.session_state.questions = [
                        "What is the timeline of the key events?",
                        "Are there any physical evidence items?",
                        "Who are the key witnesses in this case?",
                        "Is there a prior relationship between the parties?",
                        "What specific legal outcome is being sought?",
                    ]
                    st.session_state.witness_queue = []
            st.rerun()

    # ── PRE-TRIAL ──────────────────────────────────────────────
    elif st.session_state.phase == "Pre-Trial":
        st.markdown('<div class="card-label" style="margin-top:0">Magistrate · Clarifying Questions</div>', unsafe_allow_html=True)
        st.caption("Answer what you can. Leave blank to proceed on existing facts.")

        with st.form("pretrial_form"):
            answers = {}
            for i, q in enumerate(st.session_state.questions):
                st.markdown(f'<div style="font-size:0.78rem;font-weight:500;color:var(--text-secondary);margin:0.6rem 0 0.15rem">{i+1}. {q}</div>', unsafe_allow_html=True)
                answers[q] = st.text_input(f"ans_{i}", key=f"q_{i}", placeholder="Your answer…", label_visibility="collapsed")

            st.markdown('<div style="margin-top:0.8rem;font-size:0.78rem;font-weight:500;color:var(--text-secondary)">🎙 Voice Response (optional)</div>', unsafe_allow_html=True)
            st.caption("Record an answer instead of typing.")
            voice_answer = st.audio_input("Record", label_visibility="collapsed")

            st.markdown("<br/>", unsafe_allow_html=True)
            c1, c2 = st.columns(2)
            submitted = c1.form_submit_button("Submit", type="primary", use_container_width=True)
            skipped   = c2.form_submit_button("Skip →", use_container_width=True)

        if submitted or skipped:
            st.session_state.transcript_html.append(
                render_msg("System", "Pre-Trial Conference concluded. Trial commencing.")
            )
            
            stt_text = ""
            if submitted and voice_answer is not None:
                from src.audio import transcribe_audio
                st.info("Transcribing audio...")
                stt_text = transcribe_audio(voice_answer.getvalue())
            
            for q in st.session_state.questions:
                ans = answers.get(q, "").strip() if submitted else ""
                
                # Combine typed answer and voice answer
                if stt_text:
                    ans = f"{ans} (Voice added: {stt_text})" if ans else stt_text
                    
                display = ans or '<em style="color:var(--text-tertiary)">Unknown — proceeding on existing evidence.</em>'
                st.session_state.transcript_html.append(render_msg("Magistrate", f"<strong>Q:</strong> {q}", trusted_html=True))
                st.session_state.transcript_html.append(render_msg("System",     f"<strong>A:</strong> {display}", trusted_html=True))
                
            st.session_state.phase = "Trial"
            st.session_state.trial_step = 0
            st.session_state.trial_running = True
            # Build the LangGraph state for live (non-demo) trials
            if not st.session_state.demo_key:
                _jx = st.session_state.get("jurisdiction_data", {})
                _ha = {}
                if submitted:
                    for _q in st.session_state.questions:
                        _a = answers.get(_q, "").strip()
                        if stt_text and not _a:
                            _a = stt_text
                        _ha[_q] = _a
                import base64
                _IMAGE_MIMES = {"image/png", "image/jpeg", "image/gif", "image/webp"}
                _raw_evidence = st.session_state.get("multimodal_evidence", [])
                _multimodal_uris = []
                for _ef in _raw_evidence:
                    _mime = getattr(_ef, "type", None) or ""
                    if _mime in _IMAGE_MIMES:
                        _b64 = base64.b64encode(_ef.getvalue()).decode("ascii")
                        _multimodal_uris.append(f"data:{_mime};base64,{_b64}")
                st.session_state.graph_state = {
                    "case_description":     st.session_state.case_text,
                    "transcript":           [],
                    "fact_sheet":           "",
                    "admitted_evidence":    [],
                    "excluded_evidence":    [],
                    "clarifying_questions": [{"question": q} for q in st.session_state.questions],
                    "human_answers":        _ha,
                    "witness_queue":        list(st.session_state.get("witness_queue", [])),
                    "current_witness":      None,
                    "examination_phase":    None,
                    "shadow_jury_count":    shadow_juries,
                    "shadow_jury_model":    "qwen-plus-latest",
                    "jury_count":           jury_count,
                    "audio_enabled":        st.session_state.audio_enabled,
                    "deliberation_rounds":  0,
                    "main_verdict":         None,
                    "shadow_jury_results":  {},
                    "multimodal_evidence":  _multimodal_uris,
                    "errors":               [],
                    **_jx,
                }
                st.session_state.live_step = "opening"
            st.rerun()

    # ── TRIAL ──────────────────────────────────────────────────
    elif st.session_state.phase == "Trial":
        demo_key = st.session_state.demo_key

        if demo_key and demo_key in DEMO_CASES:
            script = DEMO_CASES[demo_key]["trial_script"]
            step   = st.session_state.trial_step
            total  = len(script)

            # Progress
            if step < total:
                cur = script[step]
                progress_val = step / total
                st.progress(progress_val)
                st.markdown(f"""<div class="card">
  <div class="card-label">Trial Progress</div>
  <div style="font-size:0.85rem">Step {step} of {total}</div>
  <div style="font-size:0.75rem;color:var(--text-secondary);margin-top:0.2rem">{cur['phase']} · {cur['agent']}</div>
</div>""", unsafe_allow_html=True)
            else:
                st.progress(1.0)

            # Evidence Board
            st.markdown(f"""<div class="card">
  <div class="card-label">Evidence Board</div>
  {''.join(f'<span class="ev-tag {cls}">{t}</span>' for cls, t in st.session_state.evidence_board)
   if st.session_state.evidence_board else
   '<div style="font-size:0.8rem;color:var(--text-tertiary)">No exhibits yet.</div>'}
</div>""", unsafe_allow_html=True)

            # Auto-play
            if st.session_state.trial_running and step < total:
                entry = script[step]
                st.session_state.transcript_html.append(render_msg(entry["agent"], entry["text"]))

                if "admitted" in entry["text"].lower() and entry["agent"] == "Judge":
                    st.session_state.evidence_board.append(("ev-admitted", entry["text"][:55] + "…"))
                if "sustained" in entry["text"].lower() and entry["agent"] == "Judge":
                    st.session_state.evidence_board.append(("ev-excluded", "Excluded · Sustained"))

                st.session_state.trial_step += 1

                if st.session_state.trial_step >= total:
                    st.session_state.trial_running = False
                    st.session_state.phase = "Verdict"
                    st.session_state.verdict_data = {
                        "verdict":     DEMO_CASES[demo_key]["verdict"],
                        "probability": DEMO_CASES[demo_key]["win_probability"],
                        "sensitivity": DEMO_CASES[demo_key]["sensitivity"],
                        "juries":      shadow_juries,
                        "title":       DEMO_CASES[demo_key]["title"],
                    }

                if st.session_state.get("audio_enabled", False) and entry["agent"] not in ["System", "Fact Checker"]:
                    from src.audio import generate_speech
                    st.info("Generating audio...")
                    audio_bytes = generate_speech(entry["text"])
                    if audio_bytes:
                        import base64
                        b64 = base64.b64encode(audio_bytes).decode()
                        md = f"""
                            <audio autoplay="true">
                            <source src="data:audio/mp3;base64,{b64}" type="audio/mp3">
                            </audio>
                            """
                        st.markdown(md, unsafe_allow_html=True)
                        time.sleep(len(entry["text"]) * 0.06 + 1.5) # Approximate speech duration
                else:
                    time.sleep(0.55)
                    
                st.rerun()

            elif not st.session_state.trial_running and step >= total:
                st.rerun()
        else:
            # ── LIVE TRIAL (LLM-powered, step-by-step) ───────────────────
            from src.nodes import (
                opening_statements_node, evidence_node, witness_node,
                closing_arguments_node, jury_instructions_node,
                jury_deliberation_node, shadow_jury_node,
            )

            _LIVE_STEPS  = ["opening", "evidence", "witness", "closing",
                            "jury_instructions", "jury_deliberation", "shadow_jury"]
            _STEP_LABELS = {
                "opening":           "Opening Statements",
                "evidence":          "Evidence Presentation",
                "witness":           "Witness Examination",
                "closing":           "Closing Arguments",
                "jury_instructions": "Jury Instructions",
                "jury_deliberation": "Jury Deliberation",
                "shadow_jury":       "Shadow Jury Analysis",
            }
            _STEP_NODES  = {
                "opening":           opening_statements_node,
                "evidence":          evidence_node,
                "witness":           witness_node,
                "closing":           closing_arguments_node,
                "jury_instructions": jury_instructions_node,
                "jury_deliberation": jury_deliberation_node,
                "shadow_jury":       shadow_jury_node,
            }

            live_step   = st.session_state.get("live_step", "opening")
            graph_state = st.session_state.get("graph_state", {})

            if not graph_state:
                st.error("Trial state missing. Please start a new case.")
                if st.button("Start Over", key="live_restart"):
                    for _k, _v in defaults.items():
                        st.session_state[_k] = _v
                    st.rerun()
            else:
                step_idx    = _LIVE_STEPS.index(live_step) if live_step in _LIVE_STEPS else 0
                label       = _STEP_LABELS.get(live_step, live_step)

                def _norm_agent(n):
                    """Map node message names to render_msg agent keys."""
                    if n == "Defense Counsel": return "Defense Counsel"
                    if n and n.startswith("Juror"):  return "Juror"
                    return n or "System"

                def _sanitise_content(content):
                    """If the LLM returned raw JSON, render it as human-readable text."""
                    import json as _json
                    if not isinstance(content, str):
                        content = str(content)
                    stripped = content.strip()
                    if stripped.startswith("{") and stripped.endswith("}"):
                        try:
                            data = _json.loads(stripped)
                            # Common structured outputs → prose
                            if "ruling" in data and "rationale" in data:
                                return f"The objection is {data['ruling']}. {data.get('rationale', '')}".strip()
                            if "verdict" in data and "rationale" in data:
                                return f"Verdict: {data['verdict']}. {data.get('rationale', '')}".strip()
                            # Generic: join all values
                            return " | ".join(str(v) for v in data.values() if v)
                        except Exception:
                            pass
                    return content

                st.progress(step_idx / len(_LIVE_STEPS))
                st.markdown(f"""<div class="card">
  <div class="card-label">Live Trial Progress</div>
  <div style="font-size:0.85rem">Phase {step_idx + 1} of {len(_LIVE_STEPS)}</div>
  <div style="font-size:0.75rem;color:var(--text-secondary);margin-top:0.2rem">{label}</div>
</div>""", unsafe_allow_html=True)

                # Evidence Board from live state
                _admitted = graph_state.get("admitted_evidence", [])
                _excluded = graph_state.get("excluded_evidence", [])
                _ev_html  = "".join(
                    f'<span class="ev-tag ev-admitted">{str(e)[:55]}…</span>' for e in _admitted
                ) + "".join(
                    f'<span class="ev-tag ev-excluded">Excluded: {str(e)[:40]}…</span>' for e in _excluded
                )
                st.markdown(f"""<div class="card">
  <div class="card-label">Evidence Board</div>
  {_ev_html or '<div style="font-size:0.8rem;color:var(--text-tertiary)">No exhibits yet.</div>'}
</div>""", unsafe_allow_html=True)



                if st.session_state.trial_running:
                    with st.spinner(f"\u2696\ufe0f {label}…"):
                        _node_fn = _STEP_NODES[live_step]
                        _result  = _node_fn(graph_state)

                        # Merge result into graph_state
                        for _rk, _rv in _result.items():
                            if _rk == "transcript":
                                graph_state["transcript"] = graph_state.get("transcript", []) + _rv
                                for _msg in _rv:
                                    _agent = _norm_agent(getattr(_msg, "name", None) or "System")
                                    st.session_state.transcript_html.append(
                                        render_msg(_agent, _sanitise_content(_msg.content))
                                    )
                            else:
                                graph_state[_rk] = _rv
                        st.session_state.graph_state = graph_state

                        # Decide next step
                        _wq      = graph_state.get("witness_queue", [])
                        _rounds  = graph_state.get("deliberation_rounds", 0)
                        _verdict = graph_state.get("main_verdict")

                        if live_step == "opening":
                            _next = "evidence"
                        elif live_step == "evidence":
                            _next = "witness" if _wq else "closing"
                        elif live_step == "witness":
                            _next = "witness" if _wq else "closing"
                        elif live_step == "closing":
                            if not graph_state.get("jury_enabled", True):
                                # Bench trial: skip jury instructions and deliberations
                                _next = "shadow_jury" 
                            else:
                                _next = "jury_instructions"
                        elif live_step == "jury_instructions":
                            _next = "jury_deliberation"
                        elif live_step == "jury_deliberation":
                            _next = "shadow_jury" if (_verdict or _rounds >= 3) else "jury_deliberation"
                        else:  # shadow_jury
                            _next = "done"

                        if _next == "done":
                            _sjr      = graph_state.get("shadow_jury_results", {})
                            _win_prob = _sjr.get("win_probability", 0.5)
                            _total_j  = _sjr.get("total_juries", shadow_juries)
                            _guilty   = _sjr.get("guilty_votes", 0)
                            _verdict_str = graph_state.get("main_verdict", "No Verdict Reached")
                            _ng = "Not Guilty" in _verdict_str or "Not Liable" in _verdict_str
                            _sensitivity = (
                                f"{_guilty} of {_total_j} shadow juries found the evidence met "
                                f"the burden of proof. "
                                + ("The defence successfully raised doubt." if _ng
                                   else "The prosecution's evidence was compelling.")
                            )
                            st.session_state.verdict_data = {
                                "verdict":     _verdict_str,
                                "probability": _win_prob,
                                "sensitivity": _sensitivity,
                                "juries":      _total_j,
                                "title":       st.session_state.get("case_title", "Live Case"),
                            }
                            st.session_state.phase = "Verdict"
                            st.session_state.trial_running = False
                        else:
                            st.session_state.live_step = _next

                        st.rerun()

    # ── VERDICT ────────────────────────────────────────────────
    elif st.session_state.phase == "Verdict":
        vd = st.session_state.verdict_data
        if vd:
            pct   = int(vd["probability"] * 100)
            is_ng = "NOT GUILTY" in vd["verdict"] or "NOT LIABLE" in vd["verdict"]
            vc    = "#30d158" if is_ng else "#ff453a"
            vbg   = "rgba(48,209,88,0.08)" if is_ng else "rgba(255,69,58,0.08)"
            vborder = "rgba(48,209,88,0.2)" if is_ng else "rgba(255,69,58,0.2)"

            st.markdown(f"""<div class="card" style="background:{vbg};border-color:{vborder};text-align:center;">
  <div class="card-label">Verdict</div>
  <div style="font-size:1.5rem;font-weight:700;color:{vc};margin:0.3rem 0">{vd['verdict']}</div>
  <div style="font-size:0.75rem;color:var(--text-secondary)">{vd.get('title','')}</div>
</div>""", unsafe_allow_html=True)

            gauge_col  = "#0a84ff" if pct < 50 else "#ff9f0a" if pct < 75 else "#ff453a"
            st.markdown(f"""<div class="card">
  <div class="card-label">Shadow Jury Analysis</div>
  <div class="verdict-ring-wrap">
    <div class="verdict-num" style="color:{gauge_col}">{pct}%</div>
    <div class="verdict-sub">Prosecution Win Likelihood</div>
  </div>
</div>""", unsafe_allow_html=True)
            st.progress(vd["probability"])
            st.caption(f"Based on {vd['juries']} simulated shadow juries")

            st.markdown(f"""<div class="card">
  <div class="card-label">Sensitivity Insight</div>
  <div style="font-size:0.83rem;line-height:1.65;color:var(--text-secondary)">{vd['sensitivity']}</div>
</div>""", unsafe_allow_html=True)

            st.markdown("<br/>", unsafe_allow_html=True)
            if st.button("New Trial →", type="primary", use_container_width=True):
                for k, v in defaults.items():
                    st.session_state[k] = v
                st.rerun()
