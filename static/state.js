"use strict";
// ── STATE module — extracted from static/app.js ──



const State = {
  phase:          "setup",      // setup | pretrial | trial | deliberation | verdict
  caseText:       "",
  caseTitle:      "—",
  jurisdiction:   "—",
  country:        "Nigeria",
  caseType:       "Criminal",
  transcriptEntries: [],
  evidenceBoard:  [],           // [{ label, desc, status }]
  objectionHistory: [],
  trialMode:      null,         // "demo" | "live"
  demoScript:     [],
  demoStep:       0,
  demoRunning:    false,
  demoTimer:      null,
  demoSpeed:      1.0,
  demoVerdictData: null,
  demoShadowNarrative: [],
  graphState:     {},
  liveStep:       "discovery",
  livePaused:     false,
  liveRunning:    false,
  questions:       [],
  identifiedEvidence: [],
  missingEvidence: [],
  missingWitnesses: [],
  missingEvidenceAnswers: {},
  missingWitnessesAnswers: {},
  shadowJuries:   20,
  juryCount:      12,
  uploadedText:    "",
  uploadedFiles:   [],
  mediaRecorder:   null,
  audioChunks:     [],
  verdictData:    null,
  benchmarkData:  null,
  benchmarkRunning: false,
  currentWitnessName: null,
  phaseTimings: {},
  phaseStartTime: null,
  metrics: { duration: 0, utterances: 0, objections: 0, admitted: 0, total_ev: 0 },
  metricsTimer:   null,
};

// ── Agent styling — sourced from backend /api/agent-styles (with hardcoded fallbacks) ─────

// Fallback defaults (kept in sync with legalist/data.py)
const _FALLBACK_AGENT_STYLE = {
    "Bailiff":      { abbr: "BL",  avClass: "av-system",   color: "#c9a84c" },
    "Judge":        { abbr: "JD",  avClass: "av-judge",    color: "#ff9f0a" },
    "Prosecutor":   { abbr: "PR",  avClass: "av-prosecutor", color: "#ff453a" },
    "Defense":      { abbr: "DF",  avClass: "av-defense",  color: "#0a84ff" },
    "Defense Counsel": { abbr: "DF", avClass: "av-defense", color: "#0a84ff" },
    "Witness":      { abbr: "WS",  avClass: "av-witness",  color: "#30d158" },
    "Magistrate":   { abbr: "MG",  avClass: "av-magistrate", color: "#ff9f0a" },
    "Foreperson":   { abbr: "FP",  avClass: "av-foreperson", color: "#bf5af2" },
    "Juror":        { abbr: "JR",  avClass: "av-juror",    color: "#5ac8fa" },
    "Fact Checker": { abbr: "FC",  avClass: "av-checker",  color: "#ff6961" },
    "Clerk":        { abbr: "CL",  avClass: "av-system",   color: "#8e44ad" },
    "System":       { abbr: "—",   avClass: "av-system",   color: "#48484a" },
};

function _getAgentStyles() {
    // Prefer backend-provided styles (loaded by app.js on startup)
    const backend = window.AGENT_STYLES || {};
    if (backend.styles && Object.keys(backend.styles).length) {
        // Build avClasses/abbrs from backend styles if missing
        const avClasses = backend.avClasses || {};
        const abbrs = backend.abbrs || {};
        if (!backend.avClasses || !backend.abbrs) {
            for (const [agent, cfg] of Object.entries(backend.styles)) {
                if (!avClasses[agent]) avClasses[agent] = cfg.avClass;
                if (!abbrs[agent]) abbrs[agent] = cfg.abbr;
            }
            backend.avClasses = avClasses;
            backend.abbrs = abbrs;
        }
        return backend;
    }
    // Build from fallback
    const styles = {};
    const colors = {};
    const avClasses = {};
    const abbrs = {};
    for (const [agent, cfg] of Object.entries(_FALLBACK_AGENT_STYLE)) {
        styles[agent] = { abbr: cfg.abbr, avClass: cfg.avClass };
        colors[agent] = cfg.color;
        avClasses[agent] = cfg.avClass;
        abbrs[agent] = cfg.abbr;
    }
    return { styles, colors, avClasses, abbrs };
}

// Lazy getters — resolve at call time so backend styles are picked up after load
function getAgentStyle(agent) {
    const s = _getAgentStyles().styles[agent];
    return s || { abbr: "?", avClass: "av-system" };
}
function getAgentColor(agent) {
    return _getAgentStyles().colors[agent] || "#86868b";
}
function getAgentAbbr(agent) {
    return _getAgentStyles().abbrs[agent] || "?";
}
function getAgentAvClass(agent) {
    return _getAgentStyles().avClasses[agent] || "av-system";
}

// ── DOM references ────────────────────────────────────────────────────────────

const $ = id => document.getElementById(id);
const $$ = sel => document.querySelectorAll(sel);

/** Safely parse a fetch Response as JSON, throwing the raw text on parse failure. */
async function safeJson(res) {
  const text = await res.text();
  try {
    return JSON.parse(text);
  } catch {
    throw new Error(text.slice(0, 500));
  }
}

// ── Bootstrap ─────────────────────────────────────────────────────────────────


function isTrialConcluded() {
  return State.liveStep === "done" || Boolean(State.verdictData);
}


function showToast(message, type = "info", duration = 4000) {
  let container = document.getElementById("toastContainer");
  if (!container) {
    container = document.createElement("div");
    container.id = "toastContainer";
    container.style.cssText = "position:fixed;top:16px;right:16px;z-index:9999;display:flex;flex-direction:column;gap:8px;max-width:380px;pointer-events:none;";
    document.body.appendChild(container);
  }
  const colors = {
    success: { bg: "#30d158", fg: "#000" },
    error:   { bg: "#ff453a", fg: "#fff" },
    warning: { bg: "#ff9f0a", fg: "#000" },
    info:    { bg: "#0a84ff", fg: "#fff" },
  };
  const c = colors[type] || colors.info;
  const toast = document.createElement("div");
  toast.style.cssText = `background:${c.bg};color:${c.fg};padding:10px 14px;border-radius:8px;font-size:0.82rem;font-weight:500;pointer-events:auto;box-shadow:0 4px 16px rgba(0,0,0,0.3);animation:fadeIn 0.25s ease-out;opacity:1;transition:opacity 0.3s;cursor:pointer;`;
  const icons = { success: "fa-check-circle", error: "fa-exclamation-circle", warning: "fa-exclamation-triangle", info: "fa-info-circle" };
  toast.innerHTML = `<i class="fas ${icons[type] || icons.info}" style="margin-right:6px"></i> ${escapeHtml(message)}`;
  toast.addEventListener("click", () => {
    toast.style.opacity = "0";
    setTimeout(() => toast.remove(), 300);
  });
  container.appendChild(toast);
  setTimeout(() => {
    toast.style.opacity = "0";
    setTimeout(() => toast.remove(), 300);
  }, duration);
}


let JX_DATA = {};


function extractExhibitLabel(text) {
  const m = text.match(/Exhibit\s+([A-Z])/i);
  return m ? `Exhibit ${m[1]}` : "Evidence";
}


function classifyStance(text) {
  const upper = String(text || "").toUpperCase();
  
  if (upper.includes("NOT GUILTY") || upper.includes("NOT LIABLE") || upper.includes("ACQUIT")) return "not-guilty";
  if (upper.includes("GUILTY") || upper.includes("LIABLE") || upper.includes("BURDEN MET")) return "guilty";
  
  if (upper.includes("REASONABLE DOUBT") || upper.includes("BURDEN NOT MET") || 
      upper.includes("INSUFFICIENT") || upper.includes("DOUBT") ||
      upper.includes("NOT PROVEN") || upper.includes("INNOCENT")) return "not-guilty";
  
  if (upper.includes("CONVINCED") || upper.includes("SATISFIED") || 
      upper.includes("EVIDENCE SHOWS") || upper.includes("PROVEN")) return "guilty";
  
  return "undecided";
}

// Removed hardcoded rotating agent animation as it is now dynamic

// ── Resize chart re-render ────────────────────────────────────────────────────


function formatDuration(totalSeconds) {
  const hrs = String(Math.floor(totalSeconds / 3600)).padStart(2, "0");
  const min = String(Math.floor((totalSeconds % 3600) / 60)).padStart(2, "0");
  const sec = String(totalSeconds % 60).padStart(2, "0");
  return `${hrs}:${min}:${sec}`;
}

// ── Agent Roster ─────────────────────────────────────────────────────────────


function escapeHtml(str) {
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function sleep(ms) {
  return new Promise(res => setTimeout(res, ms));
}

// ── Legal Reference (jurisdiction-aware) ──────────────────────────────────────


const DOCKET_KEY = "legalist_case_docket";


(function initTheme() {
  const saved = localStorage.getItem("theme");
  const theme = saved || "light";
  document.documentElement.setAttribute("data-theme", theme);
  updateThemeIcon(theme);
})();

function toggleTheme() {
  const current = document.documentElement.getAttribute("data-theme");
  const next = current === "dark" ? "light" : "dark";
  document.documentElement.setAttribute("data-theme", next);
  localStorage.setItem("theme", next);
  updateThemeIcon(next);
}

function updateThemeIcon(theme) {
  const btn = document.getElementById("themeToggle");
  if (!btn) return;
  const icon = btn.querySelector("i");
  if (!icon) return;
  icon.className = theme === "dark" ? "fas fa-sun" : "fas fa-moon";
}


export {
    $,
    $$,
    State,
    JX_DATA,
    DOCKET_KEY,

    getAgentStyle,
    getAgentColor,
    getAgentAbbr,
    getAgentAvClass,

    showToast,
    sleep,
    escapeHtml,
    safeJson,
    isTrialConcluded,
    classifyStance,
    formatDuration,
    extractExhibitLabel,
    toggleTheme,
    updateThemeIcon
};
