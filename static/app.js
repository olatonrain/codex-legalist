/**
 * static/app.js
 * ─────────────
 * Codex Legalis — Frontend Runtime
 *
 * Handles:
 *  - Demo case streaming (replays scripted trial step-by-step)
 *  - Live LLM trial flow (setup → magistrate → pre-trial → live steps)
 *  - Dramatic opening injection into Live Transcript
 *  - Evidence board rendering
 *  - Phase tab + timeline sync
 *  - Plotly chart rendering (mini-chart, verdict charts)
 */

"use strict";

// ── State ────────────────────────────────────────────────────────────────────

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
  liveStep:       "opening",
  livePaused:     false,
  liveRunning:    false,
  questions:      [],
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
  metrics: { duration: 0, utterances: 0, objections: 0, admitted: 0, total_ev: 0 },
  metricsTimer:   null,
};

// ── Agent colour map (matches CSS vars) ──────────────────────────────────────

const AGENT_COLOR = {
  "Judge":        "#ff9f0a",
  "Prosecutor":   "#ff453a",
  "Defense":      "#0a84ff",
  "Defense Counsel": "#0a84ff",
  "Witness":      "#30d158",
  "Foreperson":   "#bf5af2",
  "Juror":        "#5ac8fa",
  "Fact Checker": "#ff6961",
  "Magistrate":   "#ff9f0a",
  "Clerk":        "#8e44ad",
  "Bailiff":      "#c9a84c",
  "System":       "#48484a",
};

const AGENT_ABBR = {
  "Bailiff":      "BL",
  "Judge":        "JD",
  "Prosecutor":   "PR",
  "Defense":      "DF",
  "Defense Counsel": "DF",
  "Witness":      "WS",
  "Magistrate":   "MG",
  "Foreperson":   "FP",
  "Juror":        "JR",
  "Fact Checker": "FC",
  "Clerk":        "CL",
  "System":       "—",
};

const AV_CLASS = {
  "Bailiff":      "av-system",
  "Judge":        "av-judge",
  "Prosecutor":   "av-prosecutor",
  "Defense":      "av-defense",
  "Defense Counsel": "av-defense",
  "Witness":      "av-witness",
  "Magistrate":   "av-magistrate",
  "Foreperson":   "av-foreperson",
  "Juror":        "av-juror",
  "Fact Checker": "av-checker",
  "Clerk":        "av-system",
  "System":       "av-system",
};

// ── DOM references ────────────────────────────────────────────────────────────

const $ = id => document.getElementById(id);
const $$ = sel => document.querySelectorAll(sel);

// ── Bootstrap ─────────────────────────────────────────────────────────────────

document.addEventListener("DOMContentLoaded", () => {
  initTabs();
  initBottomTimeline();
  initDrawers();
  initSpeedSlider();
  initSetupForm();
  initCaseTabs();
  initDemoButtons();
  initNavActions();
  initBenchmarkButtons();
  loadJurisdictions();
  renderMiniChart();
  renderJuryGrid();
  renderDeliberationView();
  updateExportControls();
  checkApiHealth();
  renderCaseDocket();
  switchView("dashboard");
});

async function checkApiHealth() {
  try {
    const res = await fetch("/api/health");
    const data = await res.json();
    const el   = $("statLlmHealth");
    const sub  = $("statLlmSub");
    if (el)  { el.textContent = "✓ OK"; el.style.color = "var(--defense)"; }
    if (sub) sub.textContent = `v${data.version || "1.0.0"} — All systems nominal`;
  } catch {
    const el  = $("statLlmHealth");
    const sub = $("statLlmSub");
    if (el)  { el.textContent = "!"; el.style.color = "var(--prosecutor)"; }
    if (sub) sub.textContent = "Server unreachable";
  }
}

// ── Tab switching ─────────────────────────────────────────────────────────────

function initTabs() {
  $$(".phase-tab").forEach(tab => {
    tab.addEventListener("click", () => switchView(tab.dataset.view));
  });
}

function switchView(viewId) {
  $$(".phase-tab").forEach(t =>
    t.classList.toggle("active", t.dataset.view === viewId)
  );
  $$(".view").forEach(v =>
    v.classList.toggle("active", v.id === "view-" + viewId)
  );
  syncTimeline(viewId);

  // Show right panel only during active trial phases
  const rightPanel = $("rightPanel");
  if (rightPanel) {
    const showPanel = ["trial", "deliberation", "verdict"].includes(viewId);
    rightPanel.style.display = showPanel ? "" : "none";
    // Also show legal reference once in trial
    const legalRef = $("legalReferenceSection");
    if (legalRef && showPanel) legalRef.style.display = "";
  }

  setTimeout(() => {
    if (viewId === "verdict") renderVerdictView(State.verdictData);
    if (viewId === "deliberation") renderDeliberationView();
    if (viewId === "trial") renderMiniChart();
    if (viewId === "benchmark") renderBenchmarkView();
  }, 50);
}

// ── Bottom timeline ───────────────────────────────────────────────────────────

function initBottomTimeline() {
  $$(".tl-step").forEach(s =>
    s.addEventListener("click", () => switchView(s.dataset.view))
  );
}

function syncTimeline(viewId) {
  const order = ["dashboard", "setup", "trial", "deliberation", "verdict"];
  const idx   = order.indexOf(viewId);
  $$(".tl-step").forEach((s, i) => {
    s.classList.remove("active", "done");
    if (i < idx)      s.classList.add("done");
    else if (i === idx) s.classList.add("active");
  });
  const pct = Math.round((idx / (order.length - 1)) * 100);
  const prog = document.querySelector(".tl-progress");
  if (prog) prog.textContent = `Phase ${idx + 1} of ${order.length} · ${pct}%`;
}

// ── Mobile drawers ────────────────────────────────────────────────────────────

function initDrawers() {
  const leftPanel  = $("leftPanel");
  const rightPanel = $("rightPanel");
  const backdrop   = $("drawerBackdrop");

  function openDrawer(panel) {
    panel.classList.add("open");
    backdrop.classList.add("show");
    document.body.style.overflow = "hidden";
  }
  function closeDrawers() {
    leftPanel.classList.remove("open");
    rightPanel.classList.remove("open");
    backdrop.classList.remove("show");
    document.body.style.overflow = "";
  }

  $("fabAgents")  ?.addEventListener("click", () => openDrawer(leftPanel));
  $("fabContext") ?.addEventListener("click", () => openDrawer(rightPanel));
  $("menuToggle") ?.addEventListener("click", () => openDrawer(leftPanel));
  backdrop        ?.addEventListener("click", closeDrawers);
  $$(".drawer-close").forEach(btn => btn.addEventListener("click", closeDrawers));
  window.addEventListener("resize", () => { if (window.innerWidth > 1024) closeDrawers(); });
}

// ── Speed slider ──────────────────────────────────────────────────────────────

function initSpeedSlider() {
  const slider = $("speedSlider");
  const val    = $("speedVal");
  if (!slider) return;
  slider.addEventListener("input", e => {
    State.demoSpeed = parseFloat(e.target.value);
    if (val) val.textContent = State.demoSpeed.toFixed(1) + "x";
  });
}

function initNavActions() {
  $("pauseBtn")?.addEventListener("click", togglePause);
  $("newTrialBtn")?.addEventListener("click", resetTrialWorkspace);
  $("exportTopBtn")?.addEventListener("click", exportTrialReport);
  $("exportReportBtn")?.addEventListener("click", exportTrialReport);
  $("playBriefBtn")?.addEventListener("click", playAudioBrief);
  $("profileBtn")?.addEventListener("click", () => {
    addSystemMessage("Court profile: JP workspace operator. No courtroom role is assigned to this profile.");
  });
}

function isTrialConcluded() {
  return State.liveStep === "done" || Boolean(State.verdictData);
}

function updateExportControls() {
  const disabled = !isTrialConcluded();
  ["exportTopBtn", "exportReportBtn", "playBriefBtn"].forEach(id => {
    const btn = $(id);
    if (!btn) return;
    btn.disabled = disabled;
    btn.style.opacity = disabled ? "0.55" : "";
    btn.title = disabled ? "Available after the trial concludes" : "";
  });
}

function togglePause() {
  State.livePaused = !State.livePaused;
  if (State.demoRunning) State.demoRunning = !State.livePaused;
  const btn = $("pauseBtn");
  if (btn) {
    btn.innerHTML = State.livePaused
      ? '<i class="fas fa-play"></i><span>Resume</span>'
      : '<i class="fas fa-pause"></i><span>Pause</span>';
  }
  updateNavBar(State.caseTitle, State.jurisdiction, State.livePaused ? "Paused" : "In Trial");
  if (!State.livePaused) {
    if (State.trialMode === "demo" && State.demoScript.length) stepDemo();
    if (State.trialMode === "live" && State.liveStep !== "done") runLiveStep();
  }
}

function resetTrialWorkspace() {
  State.demoRunning = false;
  State.livePaused = false;
  State.liveRunning = false;
  clearTimeout(State.demoTimer);
  stopMetricsTimer();
  State.caseText = "";
  State.caseTitle = "—";
  State.jurisdiction = "—";
  State.graphState = {};
  State.liveStep = "opening";
  State.questions = [];
  State.witnessQueue = [];
  State.verdictData = null;
  State.uploadedText = "";
  State.uploadedFiles = [];
  const textArea = $("caseTextarea");
  if (textArea) textArea.value = "";
  const uploadInfo = $("uploadInfo");
  if (uploadInfo) uploadInfo.textContent = "";
  const audioInfo = $("audioUploadInfo");
  if (audioInfo) audioInfo.textContent = "";
  const mag = $("magistrateChat");
  if (mag) { mag.style.display = "none"; mag.innerHTML = ""; }
  const beginBtn = $("beginTrialBtn");
  if (beginBtn) beginBtn.style.display = "";
  const pauseBtn = $("pauseBtn");
  if (pauseBtn) pauseBtn.innerHTML = '<i class="fas fa-pause"></i><span>Pause</span>';
  clearTranscript();
  renderVerdictView(null);
  renderDeliberationView();
  updateExportControls();
  updateNavBar("No active case", "Select jurisdiction", "Ready");
  updateWizardSteps(1);
  switchView("setup");
}

// ── Jurisdictions ─────────────────────────────────────────────────────────────

let JX_DATA = {};

async function loadJurisdictions() {
  try {
    const res = await fetch("/api/jurisdictions");
    const data = await res.json();
    JX_DATA = data.data || {};
    const sel = $("countrySelect");
    if (sel) {
      data.countries.forEach(c => {
        const opt = document.createElement("option");
        opt.value = c;
        opt.textContent = `${JX_DATA[c]?.flag || ""} ${c}`;
        if (c === "Nigeria") opt.selected = true;
        sel.appendChild(opt);
      });
      sel.addEventListener("change", updateJxSummary);
      updateJxSummary();
    }
  } catch (e) { console.warn("Could not load jurisdictions", e); }
}

function updateJxSummary() {
  const country  = $("countrySelect")?.value || "Nigeria";
  const caseType = $("caseTypeSelect")?.value || "Criminal";
  const jx = JX_DATA[country];
  if (!jx) return;
  State.country  = country;
  State.caseType = caseType;
  const std = caseType === "Criminal" ? jx.criminal_standard : jx.civil_standard;
  const summaryEl = $("jxSummary");
  if (summaryEl) {
    summaryEl.innerHTML = `
      ${jx.flag} <strong>${jx.system}</strong> · ${jx.procedure}<br>
      Standard: <em>${std}</em><br>
      ${jx.jury ? "Jury trial" : "Bench trial"} · ${jx.cross ? "Adversarial cross-examination" : "Judge-led examination"}
    `;
  }
}

// ── Setup form ────────────────────────────────────────────────────────────────

function initSetupForm() {
  const beginBtn = $("beginTrialBtn");
  if (!beginBtn) return;

  $("caseTypeSelect")?.addEventListener("change", updateJxSummary);

  const audioInput = $("audioUploadInput");
  const audioInfo  = $("audioUploadInfo");
  $("recordAudioBtn")?.addEventListener("click", toggleVoiceRecording);
  if (audioInput) {
    audioInput.addEventListener("change", async (e) => {
      const file = e.target.files[0];
      if (!file) return;
      audioInfo.textContent = "Transcribing audio (please wait)...";
      audioInfo.style.color = "var(--defense)";
      
      const formData = new FormData();
      formData.append("file", file);
      
      try {
        const res = await fetch("/api/upload_audio", { method: "POST", body: formData });
        const data = await res.json();
        if (res.ok) {
          appendCaseText(data.text);
          audioInfo.textContent = `Transcribed ${data.char_count} chars from ${data.filename}`;
          audioInfo.style.color = "var(--witness)";
        } else {
          audioInfo.textContent = "Error: " + (data.detail || "Transcription failed");
          audioInfo.style.color = "var(--prosecutor)";
        }
      } catch (err) {
        audioInfo.textContent = "Network error during transcription.";
        audioInfo.style.color = "var(--prosecutor)";
      }
    });
  }

  beginBtn.addEventListener("click", async () => {
    const text = getCaseText();
    if (!text.trim()) return;
    State.caseText  = text;
    State.caseTitle = $("caseTitleInput")?.value.trim() || "Custom Case";
    State.country   = $("countrySelect")?.value || "Nigeria";
    State.caseType  = $("caseTypeSelect")?.value || "Criminal";
    State.shadowJuries = parseInt($("shadowJuriesSelect")?.value || "20", 10);
    State.juryCount    = parseInt($("juryCountSelect")?.value || "12", 10);
    State.trialMode = "live";

    beginBtn.disabled = true;
    beginBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Consulting Magistrate…';
    updateWizardSteps(2);

    try {
      // 1. Magistrate Q&A
      const magRes = await fetch("/api/trial/magistrate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          case_text:  State.caseText,
          country:    State.country,
          case_type:  State.caseType,
          shadow_juries: State.shadowJuries,
          jury_count: State.juryCount,
        }),
      });
      const magData = await magRes.json();
      if (!magRes.ok) throw new Error(magData.detail || "Magistrate request failed");
      State.questions = magData.questions || [];
      State.witnessQueue = magData.witness_queue || [];
      State.missingEvidence = magData.missing_evidence || [];
      State.missingWitnesses = magData.missing_witnesses || [];

      // 2. Show pre-trial Q&A form
      renderPreTrialForm();
      switchView("setup");
      hideCaseDetailsForm();
      document.querySelector(".magistrate-chat")?.scrollIntoView({ behavior: "smooth" });
    } catch (e) {
      alert("Magistrate error: " + e.message);
    } finally {
      beginBtn.disabled = false;
      beginBtn.innerHTML = '<i class="fas fa-balance-scale"></i> Begin Trial →';
    }
  });
}

function updateWizardSteps(activeStep) {
  const steps = [
    { el: $("wstep1"), num: 1, label: "Case Details" },
    { el: $("wstep2"), num: 2, label: "Magistrate Conf." },
    { el: $("wstep3"), num: 3, label: "Review" },
  ];
  steps.forEach(s => {
    if (!s.el) return;
    s.el.className = "wstep";
    const circle = s.el.querySelector(".wstep-circle");
    if (s.num < activeStep) {
      s.el.classList.add("done");
      if (circle) circle.innerHTML = '<i class="fas fa-check" style="font-size:13px"></i>';
    } else if (s.num === activeStep) {
      s.el.classList.add("active");
      if (circle) circle.textContent = s.num;
    } else {
      if (circle) circle.textContent = s.num;
    }
  });
  
  // Hide/show sections based on active step
  const caseDetailsForm = document.querySelector(".form-grid");
  const magistrateChat = $("magistrateChat");
  const reviewStep = $("reviewStep");
  const beginBtn = $("beginTrialBtn");
  
  if (activeStep === 1) {
    if (caseDetailsForm) caseDetailsForm.style.display = "";
    if (magistrateChat) magistrateChat.style.display = "none";
    if (reviewStep) reviewStep.style.display = "none";
    if (beginBtn) {
      beginBtn.style.display = "";
      beginBtn.innerHTML = '<i class="fas fa-arrow-right"></i> Next';
    }
  } else if (activeStep === 2) {
    if (caseDetailsForm) caseDetailsForm.style.display = "none";
    if (magistrateChat) magistrateChat.style.display = "";
    if (reviewStep) reviewStep.style.display = "none";
    if (beginBtn) beginBtn.style.display = "none";
  } else if (activeStep === 3) {
    if (caseDetailsForm) caseDetailsForm.style.display = "none";
    if (magistrateChat) magistrateChat.style.display = "none";
    if (reviewStep) reviewStep.style.display = "";
    if (beginBtn) beginBtn.style.display = "none";
  }
}

function hideCaseDetailsForm() {
  const caseDetailsForm = document.querySelector(".form-grid");
  if (caseDetailsForm) caseDetailsForm.style.display = "none";
  const beginBtn = $("beginTrialBtn");
  if (beginBtn) beginBtn.style.display = "none";
}

function getCaseText() {
  const typed = $("caseTextarea")?.value?.trim() || "";
  return typed || State.uploadedText || "";
}

function appendCaseText(text) {
  const area = $("caseTextarea");
  if (!area || !text) return;
  area.value = area.value.trim() ? `${area.value.trim()}\n\n${text}` : text;
}

async function toggleVoiceRecording() {
  const btn = $("recordAudioBtn");
  const info = $("audioUploadInfo");
  if (!navigator.mediaDevices || !window.MediaRecorder) {
    if (info) {
      info.textContent = "Recording is not supported in this browser. Use Audio File instead.";
      info.style.color = "var(--prosecutor)";
    }
    return;
  }

  if (State.mediaRecorder && State.mediaRecorder.state === "recording") {
    State.mediaRecorder.stop();
    if (btn) btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Transcribing';
    return;
  }

  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    State.audioChunks = [];
    State.mediaRecorder = new MediaRecorder(stream);
    State.mediaRecorder.ondataavailable = event => {
      if (event.data.size > 0) State.audioChunks.push(event.data);
    };
    State.mediaRecorder.onstop = async () => {
      stream.getTracks().forEach(track => track.stop());
      await transcribeRecordedAudio();
      if (btn) btn.innerHTML = '<i class="fas fa-microphone"></i> Record Voice';
    };
    State.mediaRecorder.start();
    if (btn) btn.innerHTML = '<i class="fas fa-stop"></i> Stop Recording';
    if (info) {
      info.textContent = "Recording what happened...";
      info.style.color = "var(--defense)";
    }
  } catch (err) {
    if (info) {
      info.textContent = "Microphone permission was denied or unavailable.";
      info.style.color = "var(--prosecutor)";
    }
  }
}

async function transcribeRecordedAudio() {
  const info = $("audioUploadInfo");
  const blob = new Blob(State.audioChunks, { type: State.audioChunks[0]?.type || "audio/webm" });
  const fd = new FormData();
  fd.append("file", blob, "recorded-case-facts.webm");
  if (info) info.textContent = "Transcribing recording...";
  try {
    const res = await fetch("/api/upload_audio", { method: "POST", body: fd });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Transcription failed");
    appendCaseText(data.text);
    if (info) {
      info.textContent = `Recorded and transcribed ${data.char_count} chars`;
      info.style.color = "var(--witness)";
    }
  } catch (err) {
    if (info) {
      info.textContent = err.message;
      info.style.color = "var(--prosecutor)";
    }
  }
}

// ── Case input tabs ───────────────────────────────────────────────────────────

function initCaseTabs() {
  const uploadZone = $("uploadZone");
  if (uploadZone) {
    uploadZone.addEventListener("change", async e => {
      const file = e.target.files[0];
      if (!file) return;
      const fd = new FormData();
      fd.append("file", file);
      const info = $("uploadInfo");
      try {
        if (info) {
          info.textContent = "Reading file...";
          info.style.color = "var(--defense)";
        }
        const res = await fetch("/api/upload", { method: "POST", body: fd });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || "Upload failed");
        State.uploadedText = [State.uploadedText, data.text || ""].filter(Boolean).join("\n\n");
        State.uploadedFiles.push(file.name);
        appendCaseText(data.text || "");
        if (info) {
          info.textContent = `${State.uploadedFiles.length} file(s) attached`;
          info.style.color = "var(--witness)";
        }
      } catch (err) {
        if (info) {
          info.textContent = err.message;
          info.style.color = "var(--prosecutor)";
        }
      }
    });
  }
}

// ── Pre-trial Q&A rendering ───────────────────────────────────────────────────

function renderPreTrialForm() {
  const wizard = document.querySelector(".magistrate-chat");
  if (!wizard) return;
  
  wizard.style.display = "block";
  const beginBtn = $("beginTrialBtn") || $("beginBtn");
  if (beginBtn) beginBtn.style.display = "none";
  
  wizard.innerHTML = "";

  // Section 1: Missing Evidence & Witnesses (if any)
  const hasMissing = (State.missingEvidence?.length > 0) || (State.missingWitnesses?.length > 0);
  if (hasMissing) {
    let missingHtml = `
      <div class="mag-msg" style="margin-bottom:20px;">
        <div class="mag-avatar" style="background:var(--prosecutor);"><i class="fas fa-exclamation-triangle"></i></div>
        <div class="mag-bubble" style="border-left-color:var(--prosecutor);">
          <div class="q-num" style="color:var(--prosecutor);font-weight:700;">⚠ Missing Items Identified</div>
          <div style="margin-bottom:12px;">The Magistrate has identified gaps in the case record that should be addressed before trial:</div>
    `;
    
    if (State.missingEvidence?.length > 0) {
      missingHtml += `
          <div style="margin-bottom:12px;">
            <div style="font-size:11px;font-weight:700;color:var(--muted);text-transform:uppercase;margin-bottom:6px;">
              <i class="fas fa-folder-open" style="margin-right:4px;"></i>Missing Evidence
            </div>
      `;
      State.missingEvidence.forEach((item, i) => {
        missingHtml += `
            <div style="margin-bottom:10px;padding:8px;background:var(--bg);border-radius:6px;">
              <div style="font-size:12px;font-weight:600;margin-bottom:4px;">${escapeHtml(item)}</div>
              <textarea class="form-input missing-evidence-answer" style="font-size:12px;min-height:60px;resize:vertical;" 
                     placeholder="Provide details or type 'Not available'…" data-missing-ev="${i}"></textarea>
              <div style="display:flex;gap:6px;margin-top:6px;align-items:center;">
                <button class="nav-btn missing-ev-audio-btn" data-missing-ev="${i}" style="padding:4px 8px;font-size:10px;">
                  <i class="fas fa-microphone"></i> Record
                </button>
                <span class="missing-ev-audio-status" data-missing-ev="${i}" style="font-size:10px;color:var(--muted);"></span>
              </div>
            </div>
        `;
      });
      missingHtml += `</div>`;
    }
    
    if (State.missingWitnesses?.length > 0) {
      missingHtml += `
          <div style="margin-bottom:12px;">
            <div style="font-size:11px;font-weight:700;color:var(--muted);text-transform:uppercase;margin-bottom:6px;">
              <i class="fas fa-user-friends" style="margin-right:4px;"></i>Missing Witnesses
            </div>
      `;
      State.missingWitnesses.forEach((item, i) => {
        missingHtml += `
            <div style="margin-bottom:10px;padding:8px;background:var(--bg);border-radius:6px;">
              <div style="font-size:12px;font-weight:600;margin-bottom:4px;">${escapeHtml(item)}</div>
              <textarea class="form-input missing-witness-answer" style="font-size:12px;min-height:60px;resize:vertical;" 
                     placeholder="Provide name/details or type 'Not available'…" data-missing-wit="${i}"></textarea>
              <div style="display:flex;gap:6px;margin-top:6px;align-items:center;">
                <button class="nav-btn missing-wit-audio-btn" data-missing-wit="${i}" style="padding:4px 8px;font-size:10px;">
                  <i class="fas fa-microphone"></i> Record
                </button>
                <span class="missing-wit-audio-status" data-missing-wit="${i}" style="font-size:10px;color:var(--muted);"></span>
              </div>
            </div>
        `;
      });
      missingHtml += `</div>`;
    }
    
    missingHtml += `
        </div>
      </div>
    `;
    wizard.innerHTML += missingHtml;
  }

  // Section 2: Clarifying Questions
  if (State.questions.length > 0) {
    let questionsHtml = `
      <div class="mag-msg">
        <div class="mag-avatar"><i class="fas fa-user-tie"></i></div>
        <div class="mag-bubble">
          <div class="q-num">Clarifying Questions (${State.questions.length})</div>
          <div style="margin-bottom:8px;">The Magistrate has the following questions about the case:</div>
        </div>
      </div>
    `;
    wizard.innerHTML += questionsHtml;

    State.questions.forEach((q, i) => {
      wizard.innerHTML += `
        <div class="mag-msg">
          <div class="mag-avatar"><i class="fas fa-question-circle" style="color:var(--accent);"></i></div>
          <div class="mag-bubble">
            <div class="q-num">Question ${i + 1} of ${State.questions.length}</div>
            <div>${escapeHtml(q)}</div>
            <textarea class="form-input pretrial-answer" style="margin-top:8px;min-height:60px;resize:vertical;" 
                   placeholder="Your answer (optional)…" data-q="${i}"></textarea>
            <div style="display:flex;gap:6px;margin-top:6px;align-items:center;">
              <button class="nav-btn pretrial-audio-btn" data-q="${i}" style="padding:4px 8px;font-size:10px;">
                <i class="fas fa-microphone"></i> Record
              </button>
              <span class="pretrial-audio-status" data-q="${i}" style="font-size:10px;color:var(--muted);"></span>
            </div>
          </div>
        </div>`;
    });
  }

  // Inject submit button
  const submitWrap = document.createElement("div");
  submitWrap.style.cssText = "display:flex;gap:10px;margin-top:16px;";
  submitWrap.innerHTML = `
    <button id="submitPreTrial" class="nav-btn primary" style="flex:1;justify-content:center;background:var(--navy);color:white">
      <i class="fas fa-gavel"></i> Submit & Proceed to Review
    </button>
    <button id="skipPreTrial" class="nav-btn" style="flex:1;justify-content:center">
      Skip →
    </button>`;
  wizard.appendChild(submitWrap);

  // Attach audio button handlers
  attachPreTrialAudioHandlers();
  attachMissingItemsAudioHandlers();

  $("submitPreTrial")?.addEventListener("click", () => {
    collectPreTrialAnswers(false);
    updateWizardSteps(3);
    renderReviewStep();
  });
  $("skipPreTrial")  ?.addEventListener("click", () => {
    collectPreTrialAnswers(true);
    updateWizardSteps(3);
    renderReviewStep();
  });
}

function attachPreTrialAudioHandlers() {
  $$(".pretrial-audio-btn").forEach(btn => {
    btn.addEventListener("click", async () => {
      const idx = btn.dataset.q;
      const statusEl = $(`.pretrial-audio-status[data-q="${idx}"]`);
      const textarea = $(`.pretrial-answer[data-q="${idx}"]`);
      await handleAudioRecording(btn, statusEl, textarea);
    });
  });
}

function attachMissingItemsAudioHandlers() {
  $$(".missing-ev-audio-btn").forEach(btn => {
    btn.addEventListener("click", async () => {
      const idx = btn.dataset.missingEv;
      const statusEl = $(`.missing-ev-audio-status[data-missing-ev="${idx}"]`);
      const textarea = $(`.missing-evidence-answer[data-missing-ev="${idx}"]`);
      await handleAudioRecording(btn, statusEl, textarea);
    });
  });
  
  $$(".missing-wit-audio-btn").forEach(btn => {
    btn.addEventListener("click", async () => {
      const idx = btn.dataset.missingWit;
      const statusEl = $(`.missing-wit-audio-status[data-missing-wit="${idx}"]`);
      const textarea = $(`.missing-witness-answer[data-missing-wit="${idx}"]`);
      await handleAudioRecording(btn, statusEl, textarea);
    });
  });
}

async function handleAudioRecording(btn, statusEl, textarea) {
  if (!navigator.mediaDevices || !window.MediaRecorder) {
    if (statusEl) {
      statusEl.textContent = "Recording not supported";
      statusEl.style.color = "var(--prosecutor)";
    }
    return;
  }

  if (State.mediaRecorder && State.mediaRecorder.state === "recording") {
    State.mediaRecorder.stop();
    btn.innerHTML = '<i class="fas fa-microphone"></i> Record';
    if (statusEl) statusEl.textContent = "Processing...";
    return;
  }

  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    State.audioChunks = [];
    State.mediaRecorder = new MediaRecorder(stream);
    
    State.mediaRecorder.ondataavailable = (e) => {
      State.audioChunks.push(e.data);
    };
    
    State.mediaRecorder.onstop = async () => {
      const audioBlob = new Blob(State.audioChunks, { type: "audio/webm" });
      const fd = new FormData();
      fd.append("file", audioBlob, "recording.webm");
      
      try {
        const res = await fetch("/api/upload_audio", { method: "POST", body: fd });
        const data = await res.json();
        if (res.ok) {
          if (textarea) {
            textarea.value = textarea.value.trim() 
              ? textarea.value.trim() + "\n" + data.text 
              : data.text;
          }
          if (statusEl) {
            statusEl.textContent = `Transcribed ${data.char_count} chars`;
            statusEl.style.color = "var(--witness)";
          }
        } else {
          if (statusEl) {
            statusEl.textContent = "Transcription failed";
            statusEl.style.color = "var(--prosecutor)";
          }
        }
      } catch (err) {
        if (statusEl) {
          statusEl.textContent = "Network error";
          statusEl.style.color = "var(--prosecutor)";
        }
      }
      
      stream.getTracks().forEach(t => t.stop());
      btn.innerHTML = '<i class="fas fa-microphone"></i> Record';
    };
    
    State.mediaRecorder.start();
    btn.innerHTML = '<i class="fas fa-stop"></i> Stop';
    if (statusEl) {
      statusEl.textContent = "Recording...";
      statusEl.style.color = "var(--prosecutor)";
    }
  } catch (err) {
    if (statusEl) {
      statusEl.textContent = "Microphone access denied";
      statusEl.style.color = "var(--prosecutor)";
    }
  }
}

function collectPreTrialAnswers(skip) {
  State.preTrialAnswers = {};
  State.missingEvidenceAnswers = {};
  State.missingWitnessesAnswers = {};
  
  if (!skip) {
    // Collect clarifying question answers
    $$(".pretrial-answer").forEach(inp => {
      const idx = parseInt(inp.dataset.q);
      const q   = State.questions[idx];
      if (inp.value.trim()) State.preTrialAnswers[q] = inp.value.trim();
    });
    
    // Collect missing evidence answers
    $$(".missing-evidence-answer").forEach(inp => {
      const idx = parseInt(inp.dataset.missingEv);
      const item = State.missingEvidence[idx];
      if (inp.value.trim()) State.missingEvidenceAnswers[item] = inp.value.trim();
    });
    
    // Collect missing witness answers
    $$(".missing-witness-answer").forEach(inp => {
      const idx = parseInt(inp.dataset.missingWit);
      const item = State.missingWitnesses[idx];
      if (inp.value.trim()) State.missingWitnessesAnswers[item] = inp.value.trim();
    });
  }
  State.preTrialSkipped = skip;
}

function renderReviewStep() {
  const reviewEl = $("reviewStep");
  if (!reviewEl) return;
  
  reviewEl.style.display = "block";
  
  const answers = State.preTrialAnswers || {};
  const answerCount = Object.keys(answers).length;
  const witnessCount = (State.witnessQueue || []).length;
  
  reviewEl.innerHTML = `
    <div style="padding: 20px; background: var(--bg); border-radius: 12px; border: 1px solid var(--border);">
      <h4 style="font-size: 16px; margin-bottom: 16px; color: var(--text);">
        <i class="fas fa-clipboard-check" style="color: var(--gold); margin-right: 8px;"></i>
        Trial Review
      </h4>
      
      <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 16px;">
        <div style="padding: 12px; background: var(--card); border-radius: 8px;">
          <div style="font-size: 11px; color: var(--muted); text-transform: uppercase; margin-bottom: 4px;">Case Title</div>
          <div style="font-size: 13px; font-weight: 600; color: var(--text);">${escapeHtml(State.caseTitle || "Untitled")}</div>
        </div>
        <div style="padding: 12px; background: var(--card); border-radius: 8px;">
          <div style="font-size: 11px; color: var(--muted); text-transform: uppercase; margin-bottom: 4px;">Jurisdiction</div>
          <div style="font-size: 13px; font-weight: 600; color: var(--text);">${escapeHtml(State.country || "—")}</div>
        </div>
        <div style="padding: 12px; background: var(--card); border-radius: 8px;">
          <div style="font-size: 11px; color: var(--muted); text-transform: uppercase; margin-bottom: 4px;">Case Type</div>
          <div style="font-size: 13px; font-weight: 600; color: var(--text);">${escapeHtml(State.caseType || "Criminal")}</div>
        </div>
        <div style="padding: 12px; background: var(--card); border-radius: 8px;">
          <div style="font-size: 11px; color: var(--muted); text-transform: uppercase; margin-bottom: 4px;">Case Facts</div>
          <div style="font-size: 13px; font-weight: 600; color: var(--text);">${(State.caseText || "").split(/\s+/).length} words</div>
        </div>
      </div>
      
      <div style="display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 16px; margin-bottom: 20px;">
        <div style="padding: 12px; background: var(--card); border-radius: 8px; text-align: center;">
          <div style="font-size: 24px; font-weight: 700; color: var(--accent);">${answerCount}</div>
          <div style="font-size: 11px; color: var(--muted);">Questions Answered</div>
        </div>
        <div style="padding: 12px; background: var(--card); border-radius: 8px; text-align: center;">
          <div style="font-size: 24px; font-weight: 700; color: var(--accent);">${witnessCount}</div>
          <div style="font-size: 11px; color: var(--muted);">Witnesses Identified</div>
        </div>
        <div style="padding: 12px; background: var(--card); border-radius: 8px; text-align: center;">
          <div style="font-size: 24px; font-weight: 700; color: var(--accent);">${State.shadowJuries || 20}</div>
          <div style="font-size: 11px; color: var(--muted);">Shadow Juries</div>
        </div>
      </div>
      
      ${witnessCount > 0 ? `
      <div style="margin-bottom: 16px;">
        <div style="font-size: 12px; font-weight: 600; color: var(--muted); margin-bottom: 8px;">
          <i class="fas fa-user-friends" style="margin-right: 6px;"></i>Witness Queue
        </div>
        <div style="display: flex; flex-wrap: wrap; gap: 6px;">
          ${(State.witnessQueue || []).map(w => `
            <span style="padding: 4px 10px; background: var(--card); border-radius: 16px; font-size: 11px; color: var(--text);">${escapeHtml(w)}</span>
          `).join("")}
        </div>
      </div>
      ` : ""}
      
      <div style="display: flex; gap: 10px; margin-top: 20px;">
        <button id="backToMagistrate" class="nav-btn" style="flex: 1; justify-content: center;">
          <i class="fas fa-arrow-left"></i> Back
        </button>
        <button id="confirmStartTrial" class="nav-btn primary" style="flex: 2; justify-content: center; background: var(--navy); color: white;">
          <i class="fas fa-gavel"></i> Begin Trial
        </button>
      </div>
    </div>
  `;
  
  $("backToMagistrate")?.addEventListener("click", () => {
    updateWizardSteps(2);
  });
  
  $("confirmStartTrial")?.addEventListener("click", () => {
    launchLiveTrial(State.preTrialSkipped);
  });
}

async function launchLiveTrial(skip) {
  const answers = State.preTrialAnswers || {};
  const missingEvAnswers = State.missingEvidenceAnswers || {};
  const missingWitAnswers = State.missingWitnessesAnswers || {};

  const submitBtn = $("confirmStartTrial");
  if (submitBtn) { submitBtn.disabled = true; submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Starting trial…'; }

  try {
    const res = await fetch("/api/trial/start", {
      method:  "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        case_text:     State.caseText,
        case_title:    State.caseTitle,
        country:       State.country,
        case_type:     State.caseType,
        human_answers: answers,
        missing_evidence_answers: missingEvAnswers,
        missing_witnesses_answers: missingWitAnswers,
        witness_queue: State.witnessQueue || [],
        shadow_juries: State.shadowJuries,
        jury_count:    State.juryCount,
      }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Trial start failed");
    State.graphState   = data.graph_state;
    State.liveStep     = "opening";
    State.jurisdiction = data.jurisdiction || "—";
    State.livePaused = false;
    State.liveRunning = false;
    updateWizardSteps(4);

    // Show pre-trial Q&A in transcript
    clearTranscript();
    addSystemMessage("Pre-Trial Conference concluded. Trial commencing.");
    if (!skip) {
      // Show missing items answers first
      Object.entries(missingEvAnswers).forEach(([item, answer]) => {
        addTranscriptEntry("Magistrate", `Missing evidence: ${item}`, "Pre-Trial");
        addTranscriptEntry("System",     `Provided: ${answer}`, "Pre-Trial");
      });
      Object.entries(missingWitAnswers).forEach(([item, answer]) => {
        addTranscriptEntry("Magistrate", `Missing witness: ${item}`, "Pre-Trial");
        addTranscriptEntry("System",     `Provided: ${answer}`, "Pre-Trial");
      });
      // Show clarifying question answers
      Object.entries(answers).forEach(([q, a]) => {
        addTranscriptEntry("Magistrate", `Q: ${q}`, "Pre-Trial");
        addTranscriptEntry("System",     `A: ${a}`, "Pre-Trial");
      });
    }

    // Inject dramatic AI opening lines first
    updateNavBar(State.caseTitle, State.jurisdiction, "In Trial");
    switchView("trial");
    startMetricsTimer();

    // Populate Legal Reference from jurisdiction
    populateLegalReference(State.country);

    // Update Clerk Summary
    const clerkSummary = $("clerkSummary");
    if (clerkSummary) {
      clerkSummary.innerHTML = `
        <p><b>Status:</b> Trial in session.</p>
        <p><b>Case:</b> ${escapeHtml(State.caseTitle)}</p>
        <p><b>Jurisdiction:</b> ${escapeHtml(State.country)} — ${escapeHtml(State.caseType)}</p>
        <p>Objections, evidence rulings, and verdicts will be recorded here automatically.</p>
      `;
    }

    // Stream the dramatic opening line by line with delay
    const lines = data.opening_lines || [];
    await streamLines(lines, 1200);

    // Then begin live LLM steps
    runLiveStep();
  } catch (e) {
    alert("Trial start error: " + e.message);
  }
}

// ── Demo case streaming ───────────────────────────────────────────────────────

function initDemoButtons() {
  $("demoTheft")    ?.addEventListener("click", () => loadDemo("theft"));
  $("demoContract") ?.addEventListener("click", () => loadDemo("contract"));
}

// ── Benchmark ─────────────────────────────────────────────────────────────────

function initBenchmarkButtons() {
  $("runBenchmarkBtn")?.addEventListener("click", () => runBenchmark(true));
  $("runBenchmarkLiveBtn")?.addEventListener("click", () => runBenchmark(false));
}

async function runBenchmark(useMock) {
  const caseText = State.caseText || getCaseText();
  if (!caseText.trim()) {
    alert("Please enter case facts in Setup before running a benchmark.");
    return;
  }

  State.benchmarkRunning = true;
  const statusEl = $("benchmarkStatus");
  const btnMock = $("runBenchmarkBtn");
  const btnLive = $("runBenchmarkLiveBtn");
  
  const modeLabel = useMock ? "Mock (no API calls)" : "Live (Qwen API calls)";
  const timeoutMs = useMock ? 30000 : 600000;
  
  if (statusEl) {
    const timeEstimate = useMock ? "~10 seconds" : "5-10 minutes";
    statusEl.innerHTML = `<i class="fas fa-spinner fa-spin"></i> Running benchmark in <strong>${modeLabel}</strong> mode... (Estimated: ${timeEstimate})`;
  }
  if (btnMock) { btnMock.disabled = true; btnMock.style.opacity = "0.5"; }
  if (btnLive) { btnLive.disabled = true; btnLive.style.opacity = "0.5"; }

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

  try {
    const res = await fetch("/api/benchmark/run", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        case_description: caseText,
        num_runs: useMock ? 3 : 1,
        use_mock: useMock,
      }),
      signal: controller.signal,
    });
    clearTimeout(timeoutId);
    
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Benchmark failed");
    
    State.benchmarkData = data;
    renderBenchmarkView();
    
    if (data.errors && data.errors.length > 0) {
      if (statusEl) statusEl.innerHTML = `<i class="fas fa-exclamation-triangle" style="color:var(--prosecutor)"></i> Benchmark completed with errors: ${data.errors[0].slice(0, 100)}...`;
    } else {
      if (statusEl) statusEl.innerHTML = `<i class="fas fa-check" style="color:var(--defense)"></i> Benchmark complete (${modeLabel}). Results shown below.`;
    }
  } catch (e) {
    clearTimeout(timeoutId);
    let errorMsg = e.message;
    if (e.name === "AbortError") {
      errorMsg = "Benchmark timed out. Live mode requires valid API access and can take several minutes.";
    }
    if (statusEl) statusEl.innerHTML = `<i class="fas fa-times-circle" style="color:var(--prosecutor)"></i> Benchmark error: ${errorMsg}`;
    console.error("Benchmark error:", e);
  } finally {
    State.benchmarkRunning = false;
    if (btnMock) { btnMock.disabled = false; btnMock.style.opacity = ""; }
    if (btnLive) { btnLive.disabled = false; btnLive.style.opacity = ""; }
  }
}

async function loadDemo(key) {
  clearTranscript();
  State.trialMode    = "demo";
  State.demoRunning  = false;
  State.livePaused   = false;
  clearTimeout(State.demoTimer);

  try {
    const res  = await fetch("/api/demo", {
      method:  "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ demo_key: key, shadow_juries: State.shadowJuries }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Demo load failed");

    State.demoScript  = data.script || [];
    State.demoStep    = 0;
    State.demoRunning = true;
    State.demoShadowNarrative = data.shadow_jury_narrative || [];
    State.demoVerdictData = {
      verdict:     data.verdict,
      probability: data.win_probability,
      sensitivity: data.sensitivity,
      juries:      State.shadowJuries,
      title:       data.title,
    };
    State.caseTitle   = data.title;
    State.jurisdiction = data.jurisdiction || "—";
    State.liveStep = "opening";
    State.verdictData = null;
    
    // Mock the graphState for the Demo so the Deliberation UI renders correctly
    State.graphState = {
      jury_enabled: true,
      case_type: key === "contract" ? "Civil" : "Criminal",
      jury_profiles: Array.from({ length: 12 }).map((_, i) => ({
        juror_id: i + 1,
        name: `Juror ${i + 1}`,
        occupation: "Citizen juror",
        persona: "Demo Participant",
        bias: "Awaiting evidence"
      })),
      deliberation_snapshot: {},
      shadow_jury_results: {}
    };
    updateExportControls();

    updateNavBar(data.title, data.jurisdiction, "In Trial");
    switchView("trial");
    startMetricsTimer();
    populateLegalReference(State.country || "Nigeria");
    const clerkSummary = $("clerkSummary");
    if (clerkSummary) {
      clerkSummary.innerHTML = `
        <p><b>Status:</b> Demo trial in session.</p>
        <p><b>Case:</b> ${escapeHtml(data.title)}</p>
        <p><b>Jurisdiction:</b> ${escapeHtml(data.jurisdiction || "—")}</p>
        <p>Watching demo playback. Objections and evidence will be recorded live.</p>
      `;
    }
    stepDemo();
  } catch (e) {
    alert("Demo load error: " + e.message);
  }
}

function stepDemo() {
  if (!State.demoRunning || State.livePaused) return;
  if (State.demoStep >= State.demoScript.length) {
    // Trial complete — show verdict
    finishDemo();
    return;
  }

  const entry = State.demoScript[State.demoStep];
  addTranscriptEntry(entry.agent, entry.text, entry.phase);
  handleEvidenceFromEntry(entry);
  renderDeliberationView();
  State.demoStep++;

  const delay = Math.round(700 / State.demoSpeed);
  State.demoTimer = setTimeout(stepDemo, delay);
}

function finishDemo() {
  State.demoRunning = false;
  State.liveStep = "done";
  stopMetricsTimer();
  if (State.demoVerdictData) {
    State.verdictData = State.demoVerdictData;
    
    const isDefense = State.demoVerdictData.verdict === "NOT GUILTY" || State.demoVerdictData.verdict === "NOT LIABLE";
    const totalJuries = State.shadowJuries || 20;
    const winProb = State.demoVerdictData.probability || 0.5;
    const guiltyVotes = Math.round(winProb * totalJuries);
    
    State.graphState.deliberation_snapshot = {
      type: "jury",
      round: 2,
      total: 12,
      guilty_or_liable_count: isDefense ? 0 : 12,
      not_guilty_or_not_liable_count: isDefense ? 12 : 0,
      undecided_count: 0,
      verdict: State.demoVerdictData.verdict,
      positions: Array.from({ length: 12 }).map((_, i) => ({
        juror_id: i + 1,
        name: `Juror ${i + 1}`,
        occupation: "Citizen juror",
        persona: "Demo Participant",
        stance: State.demoVerdictData.verdict,
        quote: "Agreed with the foreperson."
      }))
    };
    
    State.graphState.shadow_jury_results = {
      win_probability: winProb,
      guilty_votes: guiltyVotes,
      total_juries: totalJuries,
      narrative: State.demoShadowNarrative || [],
    };
    
    renderVerdictView(State.demoVerdictData);
    renderDeliberationView();
    updateExportControls();
    
    if (State.trialMode !== "replay") {
      saveTrialToDocket();
    }
    
    setTimeout(() => {
      switchView("verdict");
      renderShadowJuryConversation();
    }, 800);
  }
}

// ── Live trial step runner ────────────────────────────────────────────────────

function buildLiveDeliberationSnapshot() {
  const jurorEntries = State.transcriptEntries.filter(e =>
    (e.agent === "Juror" || e.agent === "Foreperson") && 
    e.phase === "Jury Deliberation"
  );
  if (!jurorEntries.length) return null;

  const positions = [];
  let guiltyCount = 0, notGuiltyCount = 0, undecidedCount = 0;
  const juryEnabled = State.graphState?.jury_enabled !== false;
  const caseType = State.graphState?.case_type || "Criminal";
  const totalJurors = State.graphState?.jury_count || 12;

  jurorEntries.forEach((entry, idx) => {
    const text = entry.text || "";
    const stance = classifyStance(text);
    const name = entry.agent;
    
    const jurorMatch = name.match(/Juror\s*(\d+)/) || text.match(/Juror\s*#?(\d+)/i);
    const jurorId = jurorMatch ? parseInt(jurorMatch[1]) : idx + 1;

    if (stance === "guilty") guiltyCount++;
    else if (stance === "not-guilty") notGuiltyCount++;
    else undecidedCount++;

    positions.push({
      juror_id: jurorId,
      name: `Juror ${jurorId}`,
      occupation: "Citizen juror",
      persona: "Live deliberation",
      stance: stance === "guilty" ? (caseType === "Civil" ? "Liable" : "Guilty")
            : stance === "not-guilty" ? (caseType === "Civil" ? "Not Liable" : "Not Guilty")
            : "Undecided",
      quote: text.slice(0, 120),
    });
  });

  const total = guiltyCount + notGuiltyCount + undecidedCount;
  let verdict = "Hung";
  const threshold = Math.max(Math.floor(total * 0.75), 1);
  if (guiltyCount >= threshold && undecidedCount === 0) {
    verdict = caseType === "Civil" ? "Liable" : "Guilty";
  } else if (notGuiltyCount >= threshold && undecidedCount === 0) {
    verdict = caseType === "Civil" ? "Not Liable" : "Not Guilty";
  }

  return {
    type: juryEnabled ? "jury" : "bench",
    round: 1,
    total: total || totalJurors,
    guilty_or_liable_count: guiltyCount,
    not_guilty_or_not_liable_count: notGuiltyCount,
    undecided_count: undecidedCount,
    verdict: verdict,
    rationale: `Live tally: ${guiltyCount} for burden met, ${notGuiltyCount} for burden not met, ${undecidedCount} undecided.`,
    positions: positions,
  };
}

async function runLiveStep() {
  if (State.liveStep === "done" || State.livePaused || State.liveRunning) return;
  State.liveRunning = true;

  updateLiveProgress();

  try {
    const res = await fetch("/api/trial/step", {
      method:  "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        live_step:   State.liveStep,
        graph_state: State.graphState,
      }),
    });
    const data = await res.json();
    if (!res.ok) {
      throw new Error(data.detail || "Trial step failed.");
    }

    // Check for pending human question
    if (data.pending_human_question) {
      State.graphState = data.graph_state;
      State.liveRunning = false;
      showHumanInputDialog(data.pending_human_question);
      return;
    }

    // Stream new messages
    const msgs = data.messages || [];
    await streamLines(msgs, 600);

    State.graphState = data.graph_state;
    State.liveStep   = data.next_step;
    State.liveRunning = false;

    // Update evidence board from state
    syncEvidenceFromState(State.graphState);
    renderClerkSummary();

    // Build live deliberation snapshot during jury_deliberation phase
    if (data.current_step === "jury_deliberation" || State.liveStep === "jury_deliberation") {
      const liveSnapshot = buildLiveDeliberationSnapshot();
      if (liveSnapshot && (!State.graphState.deliberation_snapshot || !State.graphState.deliberation_snapshot.positions?.length)) {
        State.graphState.deliberation_snapshot = liveSnapshot;
      }
    }

    // Update shadow jury narrative when shadow_jury step completes
    if (data.current_step === "shadow_jury" || State.liveStep === "shadow_jury") {
      renderShadowJuryConversation();
    }

    renderDeliberationView();
    renderMiniChart();

    // Auto-switch view to deliberation when jury phases start
    if (
      ["jury_deliberation", "shadow_jury", "jury_instructions"].includes(State.liveStep) ||
      (["jury_deliberation", "shadow_jury"].includes(data.current_step || State.liveStep))
    ) {
      const active = document.querySelector(".view.active");
      if (active?.id === "view-trial") {
        switchView("deliberation");
      }
    }

    if (data.next_step === "done") {
      stopMetricsTimer();
      if (data.verdict_data) {
        State.verdictData = data.verdict_data;
        renderVerdictView(data.verdict_data);
        renderDeliberationView();
        updateExportControls();
        saveTrialToDocket();
        setTimeout(() => {
          switchView("verdict");
          // Auto-switch to benchmark and run live benchmark after verdict
          setTimeout(() => {
            switchView("benchmark");
            runBenchmark(false);
          }, 3000);
        }, 1000);
      }
    } else {
      // Short pause between phases
      await sleep(1000);
      runLiveStep();
    }
  } catch (e) {
    State.liveRunning = false;
    console.error("Trial step error:", e);
    addSystemMessage("Trial step failed: " + e.message);
  }
}

function showHumanInputDialog(question) {
  // Create modal overlay
  const overlay = document.createElement("div");
  overlay.id = "humanQuestionOverlay";
  overlay.style.cssText = "position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,0.7);z-index:9999;display:flex;align-items:center;justify-content:center;";
  
  const agentColor = AGENT_COLOR[question.agent] || "var(--gold)";
  
  overlay.innerHTML = `
    <div style="background:var(--card);border-radius:16px;padding:24px;max-width:500px;width:90%;box-shadow:0 20px 60px rgba(0,0,0,0.3);">
      <div style="display:flex;align-items:center;gap:12px;margin-bottom:16px;">
        <div style="width:40px;height:40px;border-radius:50%;background:${agentColor};display:flex;align-items:center;justify-content:center;color:white;font-weight:700;font-size:14px;">
          ${(AGENT_ABBR[question.agent] || "?").substring(0, 2)}
        </div>
        <div>
          <div style="font-size:14px;font-weight:700;color:var(--text);">${escapeHtml(question.agent)}</div>
          <div style="font-size:11px;color:var(--muted);">Needs your input during trial</div>
        </div>
      </div>
      ${question.context ? `<div style="font-size:12px;color:var(--muted);margin-bottom:12px;padding:8px;background:var(--bg);border-radius:6px;">${escapeHtml(question.context)}</div>` : ""}
      <div style="font-size:14px;font-weight:600;color:var(--text);margin-bottom:16px;padding:12px;background:var(--bg);border-radius:8px;border-left:3px solid ${agentColor};">
        ${escapeHtml(question.question)}
      </div>
      <textarea id="humanAnswerInput" style="width:100%;min-height:100px;padding:12px;border:1px solid var(--border);border-radius:8px;font-family:inherit;font-size:13px;resize:vertical;background:var(--bg);color:var(--text);" placeholder="Type your response..."></textarea>
      <div style="display:flex;gap:8px;margin-top:12px;align-items:center;">
        <button id="humanAnswerRecordBtn" class="nav-btn" style="padding:8px 12px;font-size:12px;">
          <i class="fas fa-microphone"></i> Record Audio
        </button>
        <span id="humanAnswerRecordStatus" style="font-size:11px;color:var(--muted);"></span>
      </div>
      <div style="display:flex;gap:10px;margin-top:16px;">
        <button id="humanAnswerSubmitBtn" class="nav-btn primary" style="flex:1;justify-content:center;background:var(--navy);color:white;">
          <i class="fas fa-paper-plane"></i> Submit Response
        </button>
      </div>
    </div>
  `;
  
  document.body.appendChild(overlay);
  
  // Attach handlers
  const submitBtn = $("humanAnswerSubmitBtn");
  const recordBtn = $("humanAnswerRecordBtn");
  const recordStatus = $("humanAnswerRecordStatus");
  const answerInput = $("humanAnswerInput");
  
  recordBtn.addEventListener("click", async () => {
    await handleAudioRecording(recordBtn, recordStatus, answerInput);
  });
  
  submitBtn.addEventListener("click", async () => {
    const answer = answerInput.value.trim();
    if (!answer) {
      alert("Please provide a response");
      return;
    }
    
    submitBtn.disabled = true;
    submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Submitting...';
    
    try {
      const res = await fetch("/api/trial/human_answer", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          graph_state: State.graphState,
          answer: answer,
        }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Failed to submit answer");
      
      State.graphState = data.graph_state;
      overlay.remove();
      
      // Add to transcript
      addTranscriptEntry(question.agent, `Q: ${question.question}`, "Human Input");
      addTranscriptEntry("System", `A: ${answer}`, "Human Input");
      
      // Resume trial
      State.liveRunning = false;
      runLiveStep();
    } catch (e) {
      alert("Error: " + e.message);
      submitBtn.disabled = false;
      submitBtn.innerHTML = '<i class="fas fa-paper-plane"></i> Submit Response';
    }
  });
}

// ── Transcript helpers ────────────────────────────────────────────────────────

function clearTranscript() {
  State.transcriptEntries = [];
  State.evidenceBoard     = [];
  State.objectionHistory  = [];
  State.metrics = { duration: 0, utterances: 0, objections: 0, admitted: 0, total_ev: 0 };

  const body = $("transcriptBody");
  if (body) body.innerHTML = "";

  renderEvidenceBoard();
  renderObjectionHistory();
  renderAgentRoster();
}

function addTranscriptEntry(agent, text, phase) {
  const color   = AGENT_COLOR[agent]  || "#86868b";
  const abbr    = AGENT_ABBR[agent]   || "?";
  const avClass = AV_CLASS[agent]     || "av-system";
  const now     = new Date();
  const time    = now.toTimeString().slice(0, 5);

  const entry = { agent, text, phase, time };
  State.transcriptEntries.push(entry);
  State.metrics.utterances++;

  const body = $("transcriptBody");
  if (!body) return;

  const row = document.createElement("div");
  row.className = "msg-row";
  row.innerHTML = `
    <div class="msg-avatar ${avClass}">${abbr}</div>
    <div class="msg-content">
      <div class="msg-name" style="color:${color}">
        ${escapeHtml(agent)}
        ${phase ? `<span class="role-tag ${avClass}">${escapeHtml(phase)}</span>` : ""}
        <span style="font-size:0.65rem;color:var(--text-tertiary);font-weight:400;margin-left:auto">${time}</span>
      </div>
      <div class="msg-text">${escapeHtml(text)}</div>
    </div>`;
  body.appendChild(row);
  body.scrollTop = body.scrollHeight;

  // Update count in header
  const countEl = $("transcriptCount");
  if (countEl) countEl.textContent = State.transcriptEntries.length + " entries";

  // Track objections
  if (
    text.toLowerCase().includes("objection") &&
    ["Prosecutor", "Defense", "Defense Counsel"].includes(agent)
  ) {
    State.metrics.objections++;
    State.objectionHistory.push({ who: agent, text, ruling: "Recorded", time });
    renderObjectionHistory();
    updateMetricsDisplay();
  }
  
  renderAgentRoster(agent);
}

function addSystemMessage(text) {
  addTranscriptEntry("System", text, "System");
}

async function streamLines(lines, delayMs) {
  for (const line of lines) {
    addTranscriptEntry(line.agent, line.text, line.phase || "");
    await sleep(delayMs);
  }
}

// ── Evidence board ────────────────────────────────────────────────────────────

function handleEvidenceFromEntry(entry) {
  const text  = entry.text.toLowerCase();
  const agent = entry.agent;

  if (agent === "Judge" && text.includes("admitted")) {
    const label = extractExhibitLabel(entry.text);
    State.metrics.admitted++;
    State.metrics.total_ev++;
    State.evidenceBoard.push({ label, desc: entry.text.slice(0, 60) + "…", status: "admitted" });
    renderEvidenceBoard();
    updateMetricsDisplay();
  }
  if (agent === "Judge" && (text.includes("sustained") || text.includes("excluded"))) {
    const label = extractExhibitLabel(entry.text) || "Exhibit";
    State.metrics.total_ev++;
    State.evidenceBoard.push({ label, desc: "Excluded · Inadmissible", status: "excluded" });
    State.objectionHistory.push({ who: "Judge (Ruling)", text: entry.text, ruling: "Sustained" });
    renderEvidenceBoard();
    renderObjectionHistory();
    updateMetricsDisplay();
  }
}

function extractExhibitLabel(text) {
  const m = text.match(/Exhibit\s+([A-Z])/i);
  return m ? `Exhibit ${m[1]}` : "Evidence";
}

function syncEvidenceFromState(gs) {
  const admitted = gs.admitted_evidence || [];
  const excluded = gs.excluded_evidence || [];
  State.evidenceBoard = [
    ...admitted.map(e => ({ label: extractExhibitLabel(String(e)), desc: String(e).slice(0, 60), status: "admitted" })),
    ...excluded.map(e => ({ label: extractExhibitLabel(String(e)) || "Excluded", desc: String(e).slice(0, 60), status: "excluded" })),
  ];
  State.metrics.admitted  = admitted.length;
  State.metrics.total_ev  = admitted.length + excluded.length;
  renderEvidenceBoard();
  updateMetricsDisplay();
}

function renderEvidenceBoard() {
  const grid = $("evidenceGrid");
  if (!grid) return;

  if (!State.evidenceBoard.length) {
    grid.innerHTML = '<div style="font-size:0.8rem;color:var(--muted);grid-column:1/-1">No exhibits yet.</div>';
    return;
  }

  const ICONS = { document: "fa-file-contract", video: "fa-video", fingerprint: "fa-fingerprint", phone: "fa-phone", default: "fa-folder-open" };
  grid.innerHTML = State.evidenceBoard.map(ev => {
    const cls   = ev.status === "admitted" ? "" : "excluded";
    const icon  = ev.desc.toLowerCase().includes("video") ? ICONS.video
                : ev.desc.toLowerCase().includes("phone") ? ICONS.phone
                : ev.desc.toLowerCase().includes("fingerprint") ? ICONS.fingerprint
                : ICONS.default;
    return `
      <div class="evidence-item ${cls}">
        <div class="ev-status">${ev.status.toUpperCase()}</div>
        <div class="ev-icon"><i class="fas ${icon}"></i></div>
        <div class="ev-title">${escapeHtml(ev.label)}</div>
        <div class="ev-desc">${escapeHtml(ev.desc)}</div>
        <div class="ev-ruling">Status: ${ev.status === "admitted" ? "Admitted into evidence" : "Ruled inadmissible"}</div>
      </div>`;
  }).join("");
}

// ── Nav bar updater ───────────────────────────────────────────────────────────

function updateNavBar(title, jurisdiction, status) {
  const caseEl = $("navCaseTitle");
  const jxEl   = $("navJurisdiction");
  const statEl = $("navStatus");
  if (caseEl)  caseEl.textContent  = title;
  if (jxEl)    jxEl.textContent    = jurisdiction;
  if (statEl) {
    statEl.innerHTML = `<span class="status-badge"><span class="dot"></span>${escapeHtml(status)}</span>`;
  }
}

// ── Live progress display ─────────────────────────────────────────────────────

const STEP_LABELS = {
  "opening":           "Opening Statements",
  "evidence":          "Evidence Presentation",
  "witness":           "Witness Examination",
  "closing":           "Closing Arguments",
  "jury_instructions": "Jury Instructions",
  "jury_deliberation": "Jury Deliberation",
  "shadow_jury":       "Shadow Jury Analysis",
};

function updateLiveProgress() {
  const STEPS = ["opening", "evidence", "witness", "closing", "jury_instructions", "jury_deliberation", "shadow_jury"];
  const idx   = STEPS.indexOf(State.liveStep);
  const label = STEP_LABELS[State.liveStep] || State.liveStep;
  const pct   = Math.round(((idx + 1) / STEPS.length) * 100);

  const lbl = $("liveProgressLabel");
  if (lbl) lbl.textContent = `${label} (${idx + 1}/${STEPS.length})`;
}

// ── Verdict view rendering ────────────────────────────────────────────────────

function renderShadowJuryConversation() {
  const el = $("shadowJuryNarrative");
  if (!el) return;
  const sjr = State.graphState?.shadow_jury_results;
  const narrative = sjr?.narrative || [];
  const totalJuries = sjr?.total_juries || State.shadowJuries || 0;
  
  // Show live progress during shadow_jury step
  if (State.liveStep === "shadow_jury" && !narrative.length) {
    el.innerHTML = `
      <div style="text-align:center;padding:30px;color:var(--muted);">
        <i class="fas fa-spinner fa-spin" style="font-size:32px;color:var(--gold);margin-bottom:15px;display:block;"></i>
        <div style="font-size:0.9rem;font-weight:600;color:var(--text);">Running ${totalJuries} Shadow Juries...</div>
        <div style="font-size:0.75rem;margin-top:8px;">Each shadow jury independently evaluates the evidence</div>
        <div style="font-size:0.7rem;margin-top:4px;color:var(--muted);">This may take a moment...</div>
      </div>
    `;
    return;
  }
  
  if (!narrative.length) {
    el.innerHTML = '<div style="font-size:0.8rem;color:var(--muted);padding:10px">Shadow jury results will appear here after deliberation.</div>';
    return;
  }
  
  el.innerHTML = narrative.map(v => {
    const upperContent = v.content.toUpperCase();
    const isGuilty = upperContent.includes("VOTE: GUILTY") || upperContent.includes("VOTE: LIABLE");
    const isNotGuilty = upperContent.includes("NOT GUILTY") || upperContent.includes("NOT LIABLE");
    const color = isGuilty ? "var(--prosecutor)" : isNotGuilty ? "var(--defense)" : "var(--muted)";
    return `
      <div class="bubble" style="border-left-color:${color};margin-bottom:12px;padding:12px 14px;">
        <div class="speaker" style="color:${color};font-weight:600;margin-bottom:6px;">${escapeHtml(v.name)}</div>
        <div style="font-size:0.85rem;line-height:1.5;color:var(--text);">${escapeHtml(v.content)}</div>
      </div>
    `;
  }).join("");
}

function renderVerdictView(vd) {
  if (!vd) {
    const vText = $("verdictText");
    const vSub  = $("verdictSub");
    const gNum  = $("gaugeNumber");
    const gSub  = $("gaugeSub");
    if (vText) { vText.textContent = "—"; vText.style.color = "var(--gold)"; }
    if (vSub)  vSub.textContent = "Awaiting verdict...";
    if (gNum)  gNum.textContent = "—";
    if (gSub)  gSub.textContent = "Run a trial to see results";
    renderVerdictCharts(null);
    renderCaseRecordSummary();
    renderShadowJuryConversation();
    return;
  }
  const verdict = String(vd.verdict || "No Verdict Reached");
  const upper = verdict.toUpperCase();
  const isDefense = upper.includes("NOT GUILTY") || upper.includes("NOT LIABLE");
  const color  = isDefense ? "#30d158" : "#ff453a";
  const pct    = Math.round(((vd.probability ?? 0) || 0) * 100);

  const vText = $("verdictText");
  const vSub  = $("verdictSub");
  if (vText) { vText.textContent = verdict; vText.style.color = color; }
  if (vSub)  vSub.textContent = vd.sensitivity || "";

  const gNum  = $("gaugeNumber");
  const gSub  = $("gaugeSub");
  const sjr = State.graphState?.shadow_jury_results || {};
  if (gNum)  { gNum.textContent = pct + "%"; gNum.style.color = pct < 50 ? "#0a84ff" : pct < 75 ? "#ff9f0a" : "#ff453a"; }
  if (gSub)  gSub.textContent = `${sjr.guilty_votes || 0} of ${vd.juries || sjr.total_juries || State.shadowJuries || 0} shadow juries found burden met`;

  renderVerdictCharts(pct);
  renderCaseRecordSummary();
  renderShadowJuryConversation();
}

// ── Benchmark View ─────────────────────────────────────────────────────────────

function renderBenchmarkView() {
  const data = State.benchmarkData;
  
  // Show/hide sections based on whether we have data
  const tableCard = $("benchmarkTableCard");
  const charts = $("benchmarkCharts");
  const samples = $("benchmarkSamples");
  
  if (!data) {
    if (tableCard) tableCard.style.display = "none";
    if (charts) charts.style.display = "none";
    if (samples) samples.style.display = "none";
    return;
  }
  
  if (tableCard) tableCard.style.display = "";
  if (charts) charts.style.display = "";
  if (samples) samples.style.display = "";
  
  // Extract values
  const rawCitations = Math.round(data.raw_llm?.avg_evidence_citations || 0);
  const singleCitations = Math.round(data.single_agent?.avg_evidence_citations || 0);
  const multiCitations = Math.round(data.multi_agent?.avg_evidence_citations || 0);
  
  const rawHalluc = Math.round(data.raw_llm?.avg_hallucinations || 0);
  const singleHalluc = Math.round(data.single_agent?.avg_hallucinations || 0);
  const multiHalluc = Math.round(data.multi_agent?.avg_hallucinations || 0);
  
  const rawResults = data.raw_llm?.results || [];
  const singleResults = data.single_agent?.results || [];
  const multiResults = data.multi_agent?.results || [];
  
  const singleVerdicts = singleResults.map(r => r.verdict);
  const multiVerdicts = multiResults.map(r => r.verdict);
  const singleConsistency = singleVerdicts.length ? (singleVerdicts.filter(v => v === singleVerdicts[0]).length / singleVerdicts.length * 100) : 0;
  const multiConsistency = multiVerdicts.length ? (multiVerdicts.filter(v => v === multiVerdicts[0]).length / multiVerdicts.length * 100) : 0;
  
  const multiShadowConsensus = Math.round((data.multi_agent?.avg_shadow_jury_consensus || 0) * 100);
  
  // Update table
  const setCell = (id, val, cls) => {
    const el = $(id);
    if (el) {
      el.textContent = val;
      if (cls) el.className = cls;
    }
  };
  
  setCell("benchRawCitations", rawCitations);
  setCell("benchSingleCitations", singleCitations);
  setCell("benchMultiCitations", multiCitations, "benchmark-highlight");
  
  setCell("benchRawHalluc", rawHalluc, rawHalluc > 5 ? "benchmark-warning" : "");
  setCell("benchSingleHalluc", singleHalluc);
  setCell("benchMultiHalluc", multiHalluc, "benchmark-highlight");
  
  setCell("benchRawConsistency", "N/A");
  setCell("benchSingleConsistency", Math.round(singleConsistency) + "%");
  setCell("benchMultiConsistency", Math.round(multiConsistency) + "%", "benchmark-highlight");
  
  setCell("benchRawShadow", "N/A");
  setCell("benchSingleShadow", "N/A");
  setCell("benchMultiShadow", multiShadowConsensus + "%", "benchmark-highlight");
  
  // Response times (if available)
  const rawTime = rawResults[0]?.time;
  const singleTime = singleResults[0]?.time;
  const multiTime = multiResults[0]?.time;
  setCell("benchRawTime", rawTime ? rawTime.toFixed(1) + "s" : "—", rawTime ? "benchmark-highlight" : "");
  setCell("benchSingleTime", singleTime ? singleTime.toFixed(1) + "s" : "—");
  setCell("benchMultiTime", multiTime ? multiTime.toFixed(1) + "s" : "—");
  
  // Update bar charts
  renderBenchmarkBarChart("benchCitationsChart", [
    { label: "Raw LLM", value: rawCitations, max: Math.max(rawCitations, singleCitations, multiCitations, 1), cls: "" },
    { label: "Single-Agent", value: singleCitations, max: Math.max(rawCitations, singleCitations, multiCitations, 1), cls: "" },
    { label: "Codex Legalis", value: multiCitations, max: Math.max(rawCitations, singleCitations, multiCitations, 1), cls: "bar-success" },
  ]);
  
  renderBenchmarkBarChart("benchHallucChart", [
    { label: "Raw LLM", value: rawHalluc, max: Math.max(rawHalluc, singleHalluc, multiHalluc, 1), cls: rawHalluc > singleHalluc ? "bar-danger" : "bar-warning" },
    { label: "Single-Agent", value: singleHalluc, max: Math.max(rawHalluc, singleHalluc, multiHalluc, 1), cls: "bar-warning" },
    { label: "Codex Legalis", value: multiHalluc, max: Math.max(rawHalluc, singleHalluc, multiHalluc, 1), cls: "bar-success" },
  ]);
  
  // Update sample responses
  const rawSample = $("benchRawSample");
  const rawMeta = $("benchRawMeta");
  if (rawSample && rawResults[0]) {
    const resp = rawResults[0].response || "";
    rawSample.textContent = resp.slice(0, 200) + (resp.length > 200 ? "..." : "");
    if (rawMeta) rawMeta.innerHTML = `<span>${rawHalluc} hallucinations</span><span>${rawCitations} citations</span>`;
  }
  
  const multiSample = $("benchMultiSample");
  const multiMeta = $("benchMultiMeta");
  if (multiSample && multiResults[0]) {
    const verdict = multiResults[0].verdict || "Unknown";
    const reasoning = multiResults[0].reasoning || "";
    multiSample.innerHTML = `
      <strong>Verdict:</strong> ${escapeHtml(verdict)}<br>
      <strong>Shadow Jury Consensus:</strong> ${multiShadowConsensus}%<br>
      <strong>Evidence Citations:</strong> ${multiCitations}<br>
      <strong>Transcript Length:</strong> ${multiResults[0].transcript_length || 0} messages
    `;
    if (multiMeta) multiMeta.innerHTML = `<span>${multiResults[0].transcript_length || 0}+ messages</span><span>${multiCitations} citations</span><span>${multiHalluc} hallucinations</span>`;
  }
}

function renderBenchmarkBarChart(containerId, items) {
  const container = $(containerId);
  if (!container) return;
  
  container.innerHTML = items.map(item => {
    const pct = item.max > 0 ? Math.round((item.value / item.max) * 100) : 0;
    return `
      <div class="bar-item">
        <div class="bar-label">${escapeHtml(item.label)}</div>
        <div class="bar-container">
          <div class="bar ${item.cls}" style="width: ${pct}%">
            <span class="bar-value">${item.value}</span>
          </div>
        </div>
      </div>
    `;
  }).join("");
}

// ── Metrics timer ─────────────────────────────────────────────────────────────

function startMetricsTimer() {
  State.metrics.duration = 0;
  State.metricsTimer = setInterval(() => {
    State.metrics.duration++;
    updateMetricsDisplay();
  }, 1000);
}

function stopMetricsTimer() {
  clearInterval(State.metricsTimer);
}

function updateMetricsDisplay() {
  const d   = State.metrics.duration;
  const hrs = String(Math.floor(d / 3600)).padStart(2, "0");
  const min = String(Math.floor((d % 3600) / 60)).padStart(2, "0");
  const sec = String(d % 60).padStart(2, "0");

  const dur  = $("metricDuration");
  const utt  = $("metricUtterances");
  const obj  = $("metricObjections");
  const ev   = $("metricEvidence");

  if (dur)  dur.textContent  = `${hrs}:${min}:${sec}`;
  if (utt)  utt.textContent  = State.metrics.utterances;
  if (obj)  obj.textContent  = State.metrics.objections;
  if (ev)   ev.textContent   = `${State.metrics.admitted} / ${State.metrics.total_ev}`;
}

// ── Live progress bar injection ───────────────────────────────────────────────

// This hook manages the "live step" label shown in the trial view right panel
function updateLiveStepBadge(label) {
  const el = $("liveStepBadge");
  if (el) el.textContent = label;
}

// ── Plotly charts ─────────────────────────────────────────────────────────────

function renderMiniChart() {
  const el = $("mini-chart");
  if (!el || typeof Plotly === "undefined") return;
  const isMobile = window.innerWidth < 768;
  const phaseOrder = ["Opening Statements", "Evidence Presentation", "Witness Examination", "Closing Arguments", "Jury Instructions", "Jury Deliberation", "Shadow Jury Analysis"];
  const phaseCounts = phaseOrder.map(phase => State.transcriptEntries.filter(e => e.phase === phase).length);
  const labels = phaseOrder.map(p => p.replace(" Presentation", "").replace(" Statements", ""));
  const hasData = phaseCounts.some(Boolean);
  const y = hasData ? phaseCounts : [0];
  const x = hasData ? labels : ["Awaiting trial"];
  Plotly.newPlot(el, [{
    x,
    y,
    type: "bar",
    marker: { color: "#C9A84C" },
    text: y,
    textposition: "outside",
    hovertemplate: "%{x}<br>%{y} transcript entries<extra></extra>",
    line: { color: "#C9A84C", width: 3 },
  }], {
    margin: { t: 10, r: 10, b: 30, l: 35 },
    xaxis: { tickfont: { size: isMobile ? 9 : 10, family: "Inter" }, gridcolor: "#E1E8ED" },
    yaxis: { tickfont: { size: 9, family: "JetBrains Mono" }, rangemode: "tozero", gridcolor: "#E1E8ED",
             title: { text: isMobile ? "" : "Live entries", font: { size: 10 } } },
    paper_bgcolor: "transparent", plot_bgcolor: "transparent", showlegend: false,
  }, { responsive: true, displayModeBar: false });
}

function renderVerdictCharts(pct = null) {
  const isMobile = window.innerWidth < 768;
  if (typeof Plotly === "undefined") return;
  const hasVerdict = pct !== null && !Number.isNaN(pct);
  const value = hasVerdict ? pct : 0;

  // Gauge
  const gauge = $("gaugeChart");
  if (gauge) {
    Plotly.newPlot(gauge, [{
      type: "indicator", mode: "gauge+number", value,
      number: { suffix: "%", font: { size: isMobile ? 28 : 36, family: "Playfair Display", color: "#1A2A3A" } },
      title: { text: hasVerdict ? "Burden Met Probability" : "Awaiting Shadow Jury", font: { size: isMobile ? 11 : 13, family: "Inter" } },
      gauge: {
        axis: { range: [0, 100], tickfont: { size: 9 } },
        bar: { color: "#1A2A3A" },
        steps: [{ range: [0, 40], color: "#FADBD8" }, { range: [40, 65], color: "#F9E79F" }, { range: [65, 100], color: "#D5F5E3" }],
        threshold: { line: { color: "#C9A84C", width: 4 }, thickness: 0.8, value },
      },
    }], { margin: { t: 40, b: 20, l: 40, r: 40 }, paper_bgcolor: "transparent", plot_bgcolor: "transparent" },
    { responsive: true, displayModeBar: false });
  }

  // Evidence record matrix
  const heatmap = $("heatmapChart");
  if (heatmap) {
    const admitted = State.graphState?.admitted_evidence || [];
    const excluded = State.graphState?.excluded_evidence || [];
    const rows = [
      ["Admitted evidence", admitted.length],
      ["Excluded evidence", excluded.length],
      ["Objections", State.metrics.objections],
      ["Witnesses queued", (State.graphState?.witness_queue || []).length],
    ];
    Plotly.newPlot(heatmap, [{
      x: rows.map(r => r[0]),
      y: rows.map(r => r[1]),
      type: "bar",
      marker: { color: ["#27AE60", "#C0392B", "#F39C12", "#2980B9"] },
      text: rows.map(r => r[1]),
      textposition: "outside",
      hovertemplate: "%{x}: %{y}<extra></extra>",
    }], {
      margin: { t: 10, r: 10, b: 55, l: 35 },
      xaxis: { tickfont: { size: isMobile ? 9 : 10, family: "Inter" } },
      yaxis: { tickfont: { size: isMobile ? 9 : 10, family: "Inter" }, rangemode: "tozero" },
      paper_bgcolor: "transparent", plot_bgcolor: "transparent",
    }, { responsive: true, displayModeBar: false });
  }

  // Vote bar
  const voteChart = $("voteChart");
  if (voteChart) {
    const sjr = State.graphState?.shadow_jury_results || {};
    const total = State.verdictData?.juries || sjr.total_juries || State.shadowJuries || 0;
    const guilty  = sjr.guilty_votes ?? Math.round((value / 100) * total);
    const ng      = sjr.not_guilty_votes ?? (hasVerdict ? Math.max(total - guilty, 0) : 0);
    const hung    = sjr.hung_votes ?? 0;
    Plotly.newPlot(voteChart, [{
      x: ["Burden Met","Burden Not Met","Hung/Errors"], y: [guilty, ng, hung],
      type: "bar", marker: { color: ["#C0392B","#27AE60","#F39C12"] },
      text: [guilty, ng, hung], textposition: "outside",
      textfont: { family: "JetBrains Mono", size: isMobile ? 10 : 12, color: "#1A2A3A" },
    }], {
      margin: { t: 20, r: 10, b: 40, l: 35 },
      xaxis: { tickfont: { size: isMobile ? 10 : 11, family: "Inter" } },
      yaxis: { tickfont: { size: 10, family: "JetBrains Mono" }, title: { text: isMobile ? "" : "Shadow Juries", font: { size: 10 } } },
      paper_bgcolor: "transparent", plot_bgcolor: "transparent", showlegend: false,
    }, { responsive: true, displayModeBar: false });
  }
}

// ── Jury grid ──────────────────────────────────────────────────────────────────

function renderJuryGrid() {
  const grid = $("juryGrid");
  if (!grid) return;
  const snapshot = State.graphState?.deliberation_snapshot || {};
  const profiles = State.graphState?.jury_profiles || [];
  const positions = snapshot.positions || [];
  const jurors = positions.length
    ? positions.map((position, index) => ({
        n: position.juror_id || index + 1,
        name: position.name || `Juror ${position.juror_id || index + 1}`,
        trait: [position.occupation, position.persona].filter(Boolean).join(" · ") || "Deliberation",
        stance: classifyStance(position.stance || position.quote),
        quote: position.quote || position.bias || "",
      }))
    : profiles.map((profile, index) => ({
        n: profile.juror_id || index + 1,
        name: profile.name || `Juror ${profile.juror_id || index + 1}`,
        trait: [profile.occupation, profile.persona].filter(Boolean).join(" · ") || "Awaiting deliberation",
        stance: "undecided",
        quote: profile.bias || "Awaiting the judge's instructions.",
      }));

  if (!jurors.length) {
    const juryEnabled = State.graphState?.jury_enabled;
    grid.innerHTML = `
      <div class="juror-card undecided" style="grid-column:1/-1">
        <div class="juror-head">
          <div class="juror-avatar"><i class="fas fa-balance-scale"></i></div>
          <div>
            <div class="juror-name">${juryEnabled === false ? "Bench trial" : "Awaiting deliberation"}</div>
            <div class="juror-trait">${juryEnabled === false ? "No jury panel is configured for this jurisdiction." : "Juror positions will appear after the deliberation phase."}</div>
          </div>
        </div>
      </div>`;
    // Update panel header to show bench trial label
    const panelHeader = $("juryPanelHeader");
    if (panelHeader) panelHeader.textContent = juryEnabled === false ? "Bench Trial" : "Jury Panel";
    return;
  }

  // Update panel header with live juror count from demo style: "Jury Panel (12 Jurors)"
  const panelHeader = $("juryPanelHeader");
  if (panelHeader) {
    const n = jurors.length;
    panelHeader.textContent = `Jury Panel (${n} Juror${n !== 1 ? "s" : ""})`;
  }

  grid.innerHTML = jurors.map(j => {
    const label = j.stance === "guilty" ? "Guilty" : j.stance === "not-guilty" ? "Not Guilty" : "Undecided";
    const icon  = j.stance === "guilty" ? "fa-times" : j.stance === "not-guilty" ? "fa-check" : "fa-question";
    return `
      <div class="juror-card ${j.stance}">
        <div class="juror-head">
          <div class="juror-avatar">${escapeHtml(String(j.n))}</div>
          <div><div class="juror-name">${escapeHtml(j.name)}</div><div class="juror-trait">${escapeHtml(j.trait)}</div></div>
        </div>
        <div class="juror-stance ${j.stance}"><i class="fas ${icon}"></i> ${label}</div>
        <div class="juror-quote">"${escapeHtml(j.quote)}"</div>
      </div>`;
  }).join("");
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

let resizeTimer;
window.addEventListener("resize", () => {
  clearTimeout(resizeTimer);
  resizeTimer = setTimeout(() => {
    const active = document.querySelector(".view.active");
    if (active?.id === "view-trial")   renderMiniChart();
    if (active?.id === "view-verdict") renderVerdictCharts();
  }, 200);
});

// ── Objections ────────────────────────────────────────────────────────────────

function renderObjectionHistory() {
  const container = $("objectionHistoryContainer");
  if (!container) return;
  
  if (State.objectionHistory.length === 0) {
    container.innerHTML = `<div style="font-size:0.78rem;color:var(--muted)">No objections yet.</div>`;
    return;
  }
  
  container.innerHTML = State.objectionHistory.map((obj, idx) => {
    const fullText = obj.text || "";
    const truncated = fullText.length > 120 ? fullText.slice(0, 120) + "..." : fullText;
    const needsToggle = fullText.length > 120;
    const rulingCls = (obj.ruling || "").toLowerCase().includes("sustained") ? "sustained" 
                    : (obj.ruling || "").toLowerCase().includes("overruled") ? "overruled" : "";
    
    return `
    <div class="obj-item">
      <div class="obj-who">${escapeHtml(obj.who || obj.agent || "Unknown")}</div>
      <div class="obj-reason">${escapeHtml(truncated)}</div>
      ${needsToggle ? `<button class="obj-toggle" onclick="toggleObjectionText(${idx}, this)" style="background:none;border:none;color:var(--accent);font-size:0.7rem;cursor:pointer;padding:0;margin-bottom:4px">Show more</button>` : ""}
      <div class="obj-ruling">
        <span class="ruling-result ${rulingCls}">${escapeHtml((obj.ruling || "Recorded").toUpperCase())}</span>
        ${obj.time ? `<span style="font-size:0.65rem;color:var(--muted);margin-left:6px">${obj.time}</span>` : ""}
      </div>
    </div>`;
  }).join("");
}

function toggleObjectionText(idx, btn) {
  const obj = State.objectionHistory[idx];
  if (!obj) return;
  const reasonEl = btn.previousElementSibling;
  const fullText = obj.text || "";
  const truncated = fullText.slice(0, 120) + "...";
  const isExpanded = btn.textContent === "Show less";
  
  if (isExpanded) {
    reasonEl.textContent = truncated;
    btn.textContent = "Show more";
  } else {
    reasonEl.textContent = fullText;
    btn.textContent = "Show less";
  }
}

function renderClerkSummary() {
  const el = $("clerkSummary");
  if (!el) return;
  const factSheet = State.graphState?.fact_sheet || "";
  const admitted = State.graphState?.admitted_evidence || [];
  const excluded = State.graphState?.excluded_evidence || [];
  el.innerHTML = `
    <p><b>Status:</b> ${escapeHtml(State.liveStep === "done" ? "Trial completed" : State.livePaused ? "Paused" : "Trial in session")}.</p>
    <p><b>Case:</b> ${escapeHtml(State.caseTitle || "Untitled case")}</p>
    <p><b>Jurisdiction:</b> ${escapeHtml(State.country)} - ${escapeHtml(State.caseType)}</p>
    ${factSheet ? `<p><b>Fact sheet:</b> ${escapeHtml(factSheet)}</p>` : ""}
    <p><b>Evidence:</b> ${admitted.length} admitted, ${excluded.length} excluded.</p>
  `;
}

function renderDeliberationView() {
  const benchNotice = $("benchNotice");
  if (benchNotice) {
    const juryEnabled = State.graphState?.jury_enabled;
    benchNotice.style.display = juryEnabled === false ? "block" : "none";
  }
  const liveBadge = $("deliberationLiveBadge");
  if (liveBadge) {
    const isLive = State.liveStep === "jury_deliberation" || State.liveStep === "shadow_jury";
    liveBadge.style.display = isLive ? "inline" : "none";
  }
  renderConsensusRows();
  renderJuryGrid();
  renderDeliberationTranscript();
}

function renderConsensusRows() {
  const rows = $("consensusRows");
  const clock = $("deliberationClock");
  if (!rows) return;
  const snapshot = State.graphState?.deliberation_snapshot || {};
  const sjr = State.graphState?.shadow_jury_results || {};
  const total = snapshot.total || sjr.total_juries || State.verdictData?.juries || 0;
  const burdenMet = snapshot.guilty_or_liable_count ?? sjr.guilty_votes ?? null;
  const burdenNotMet = snapshot.not_guilty_or_not_liable_count ?? (burdenMet === null ? null : Math.max(total - burdenMet, 0));
  const undecided = snapshot.undecided_count ?? (total && burdenMet !== null ? 0 : 1);
  const status = snapshot.verdict
    ? `${snapshot.type === "bench" ? "Bench verdict" : "Jury status"}: ${snapshot.verdict}`
    : "Awaiting deliberation";
  if (clock) clock.textContent = State.metrics.duration ? `${formatDuration(State.metrics.duration)} elapsed · ${status}` : status;

  if (!total || burdenMet === null) {
    rows.innerHTML = '<div style="font-size:0.8rem;color:var(--muted)">No live deliberation or shadow jury result yet.</div>';
    return;
  }

  const pctMet = total ? Math.round((burdenMet / total) * 100) : 0;
  const pctNot = total ? Math.round((burdenNotMet / total) * 100) : 0;
  const pctUnd = total ? Math.round((undecided / total) * 100) : 0;
  const jxLabel = snapshot.type === "bench"
    ? (State.graphState?.case_type === "Civil" ? ["Liable", "Not Liable"] : ["Guilty", "Not Guilty"])
    : State.graphState?.case_type === "Civil"
      ? ["Liable", "Not Liable"]
      : ["Guilty", "Not Guilty"];
  const [metLabel, notMetLabel] = jxLabel;
  rows.innerHTML = `
    <div class="meter-row"><div class="meter-label" style="color:var(--prosecutor)">${metLabel}</div><div class="meter-bar"><div class="meter-fill g" style="width:${pctMet}%">${burdenMet}</div></div></div>
    <div class="meter-row"><div class="meter-label" style="color:var(--defense)">${notMetLabel}</div><div class="meter-bar"><div class="meter-fill ng" style="width:${pctNot}%">${burdenNotMet}</div></div></div>
    <div class="meter-row"><div class="meter-label" style="color:var(--witness)">Undecided</div><div class="meter-bar"><div class="meter-fill u" style="width:${pctUnd}%">${undecided}</div></div></div>
    ${snapshot.rationale ? `<div style="font-size:0.82rem;color:var(--muted);line-height:1.45;margin-top:8px">${escapeHtml(snapshot.rationale)}</div>` : ""}
  `;
}

function renderDeliberationTranscript() {
  const el = $("deliberationTranscriptContainer");
  if (!el) return;
  const snapshot = State.graphState?.deliberation_snapshot || {};
  const snapshotEntries = (snapshot.positions || []).map(position => ({
    agent: position.name || `Juror ${position.juror_id}`,
    phase: snapshot.type === "bench" ? "Bench Deliberation" : `Round ${snapshot.round || 1}`,
    text: `${position.quote || ""} Vote: ${position.stance || "Undecided"}.`,
  }));
  const entries = snapshotEntries.length ? snapshotEntries : State.transcriptEntries.filter(e =>
    /deliberation|shadow jury|jury instructions|verdict/i.test(e.phase || "") ||
    (e.phase === "Jury Deliberation" && e.agent !== "Judge" && e.agent !== "System")
  );
  if (!entries.length) {
    el.innerHTML = '<div style="font-size:0.8rem;color:var(--muted);padding:10px">Awaiting deliberation phase.</div>';
    return;
  }
  el.innerHTML = entries.map(e => {
    const color = AGENT_COLOR[e.agent] || "var(--gold)";
    return `
      <div class="bubble" style="border-left-color:${color};margin-bottom:10px">
        <div class="speaker" style="color:${color}">${escapeHtml(e.agent)} <span class="tag" style="background:rgba(0,0,0,0.06);color:${color}">${escapeHtml(e.phase || "Deliberation")}</span></div>
        ${escapeHtml(e.text)}
      </div>
    `;
  }).join("");
}

function renderCaseRecordSummary() {
  const el = $("caseRecordSummary");
  if (!el) return;
  const admitted = State.graphState?.admitted_evidence || [];
  const excluded = State.graphState?.excluded_evidence || [];
  const verdict = State.verdictData?.verdict || State.graphState?.main_verdict || "Awaiting verdict";
  const items = [
    `<span class="cite">Verdict</span> - ${escapeHtml(verdict)}`,
    `<span class="cite">Transcript</span> - ${State.transcriptEntries.length} recorded entries across the live trial.`,
    `<span class="cite">Evidence</span> - ${admitted.length} admitted and ${excluded.length} excluded items in the current record.`,
  ];
  if (State.graphState?.fact_sheet) {
    items.push(`<span class="cite">Clerk fact sheet</span> - ${escapeHtml(State.graphState.fact_sheet)}`);
  }
  el.innerHTML = items.map(item => `<div class="precedent-item">${item}</div>`).join("");
}

function formatDuration(totalSeconds) {
  const hrs = String(Math.floor(totalSeconds / 3600)).padStart(2, "0");
  const min = String(Math.floor((totalSeconds % 3600) / 60)).padStart(2, "0");
  const sec = String(totalSeconds % 60).padStart(2, "0");
  return `${hrs}:${min}:${sec}`;
}

// ── Agent Roster ─────────────────────────────────────────────────────────────

function renderAgentRoster(speakingAgent = null) {
  const container = $("agentRosterContainer");
  if (!container) return;

  const uniqueAgents = Array.from(new Set(State.transcriptEntries.map(e => e.agent))).filter(a => a !== "System");
  const activeAgent = speakingAgent || State.transcriptEntries.at(-1)?.agent || null;
  
  // Base setup agents
  const agentsToRender = [
    { name: "Judge", role: "Presiding court", key: "Judge" },
    { name: State.caseType === "Civil" ? "Plaintiff Counsel" : "Prosecutor", role: State.caseType === "Civil" ? "Claimant advocate" : "State counsel", key: "Prosecutor" },
    { name: "Defense", role: "Respondent counsel", key: "Defense" },
    { name: "Court Clerk", role: "Record keeper", key: "Clerk" },
    ...uniqueAgents
      .filter(a => !["Judge", "Prosecutor", "Defense", "Defense Counsel", "Clerk", "Bailiff"].includes(a))
      .map(a => ({ name: a, role: inferAgentRole(a), key: a }))
  ];

  container.innerHTML = agentsToRender.map(agent => {
    const color = AGENT_COLOR[agent.key] || "#86868b";
    const abbr = AGENT_ABBR[agent.key] || agent.name.substring(0, 2).toUpperCase();
    const isSpeaking = activeAgent === agent.key || activeAgent === agent.name || (activeAgent === "Defense Counsel" && agent.key === "Defense");
    const isVoting = /Juror|Foreperson/.test(agent.key) && /deliberation/i.test(State.transcriptEntries.at(-1)?.phase || "");
    const statusClass = isSpeaking ? "st-speaking" : isVoting ? "st-voting" : "st-idle";
    const statusText = isSpeaking ? "Speaking" : isVoting ? "Voting" : "Idle";
    const speakingClass = isSpeaking ? "speaking" : "";

    return `
      <div class="agent-card ${speakingClass}" style="border-left-color:${color}">
        <div class="agent-head">
          <div class="agent-avatar" style="background:${color}">${abbr}</div>
          <div class="agent-info"><div class="agent-name">${escapeHtml(agent.name)}</div><div class="agent-role">${escapeHtml(agent.role)}</div></div>
        </div>
        <div class="agent-status"><span class="status-dot ${statusClass}"></span> ${statusText}</div>
      </div>
    `;
  }).join("");
}

function inferAgentRole(agent) {
  if (agent.startsWith("Juror")) return "Fact finder";
  if (agent === "Foreperson") return "Jury foreperson";
  if (agent === "Witness") return "Witness testimony";
  if (agent === "Fact Checker") return "Record verification";
  if (agent === "Magistrate") return "Pre-trial questions";
  if (agent === "Bailiff") return "Court order";
  return "Participant";
}

function buildTrialReport() {
  const admitted = State.graphState?.admitted_evidence || [];
  const excluded = State.graphState?.excluded_evidence || [];
  const verdict = State.verdictData?.verdict || State.graphState?.main_verdict || "Pending";
  const lines = [
    "CODEX LEGALIS TRIAL REPORT",
    `Case: ${State.caseTitle || "Untitled case"}`,
    `Jurisdiction: ${State.jurisdiction || State.country}`,
    `Case type: ${State.caseType}`,
    `Generated: ${new Date().toLocaleString()}`,
    "",
    "SUMMARY",
    `Verdict: ${verdict}`,
    `Utterances: ${State.metrics.utterances}`,
    `Objections: ${State.metrics.objections}`,
    `Evidence: ${admitted.length} admitted, ${excluded.length} excluded`,
    State.graphState?.fact_sheet ? `Fact sheet: ${State.graphState.fact_sheet}` : "",
    "",
    "ADMITTED EVIDENCE",
    ...(admitted.length ? admitted.map((e, i) => `${i + 1}. ${e}`) : ["None recorded."]),
    "",
    "EXCLUDED EVIDENCE",
    ...(excluded.length ? excluded.map((e, i) => `${i + 1}. ${e}`) : ["None recorded."]),
    "",
    "TRANSCRIPT",
    ...State.transcriptEntries.map(e => `[${e.time}] [${e.phase || "Trial"}] ${e.agent}: ${e.text}`),
  ].filter(line => line !== "");
  return lines.join("\n");
}

function exportTrialReport() {
  if (!isTrialConcluded()) {
    addSystemMessage("Export is available only after the trial has concluded.");
    return;
  }
  const report = buildTrialReport();
  const blob = new Blob([report], { type: "text/plain;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  const slug = (State.caseTitle || "codex-legalis-trial").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
  a.href = url;
  a.download = `${slug || "codex-legalis-trial"}-report.txt`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

function buildAudioBrief() {
  const verdict = State.verdictData?.verdict || State.graphState?.main_verdict || "no verdict has been reached";
  const admitted = State.graphState?.admitted_evidence?.length || 0;
  const excluded = State.graphState?.excluded_evidence?.length || 0;
  const latest = State.transcriptEntries.slice(-5).map(e => `${e.agent} said: ${e.text}`).join(" ");
  return `Trial brief for ${State.caseTitle || "the current case"}. Jurisdiction: ${State.jurisdiction || State.country}. The current verdict is ${verdict}. The record contains ${admitted} admitted evidence items, ${excluded} excluded evidence items, and ${State.metrics.objections} objections. Recent courtroom activity: ${latest || "No transcript entries have been recorded yet."}`;
}

function playAudioBrief() {
  if (!isTrialConcluded()) {
    addSystemMessage("Audio brief is available only after the trial has concluded.");
    return;
  }
  const text = buildAudioBrief();
  if (!("speechSynthesis" in window)) {
    addSystemMessage("Audio brief is not supported in this browser.");
    return;
  }
  window.speechSynthesis.cancel();
  const utterance = new SpeechSynthesisUtterance(text);
  utterance.rate = 0.95;
  utterance.pitch = 1;
  window.speechSynthesis.speak(utterance);
}

// ── Utilities ─────────────────────────────────────────────────────────────────

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

function populateLegalReference(country) {
  const container = $("legalReferenceLinks");
  if (!container) return;
  const jx = JX_DATA[country];
  if (!jx) {
    container.innerHTML = '<div style="font-size:0.78rem;color:var(--muted)">Jurisdiction registry not loaded.</div>';
    return;
  }
  const standard = State.caseType === "Civil" ? jx.civil_standard : jx.criminal_standard;
  const refs = [
    ["Configured source", "Internal jurisdiction registry, not live external legal research"],
    ["System", jx.system],
    ["Procedure", jx.procedure],
    ["Standard", standard],
    ["Evidence rules", jx.evidence_rules],
    ["Fact finder", jx.jury ? "Jury enabled" : "Bench/panel trial"],
    ["Examination", jx.cross ? "Adversarial cross-examination" : "Judge-led questioning"],
    ["Court address", jx.address],
  ];

  container.innerHTML = refs.map(([rule, desc]) =>
    `<div class="law-link"><span class="rule">${escapeHtml(rule)}</span> - ${escapeHtml(desc)}</div>`
  ).join("");
}

// ── Case Docket (localStorage persistence) ────────────────────────────────────

const DOCKET_KEY = "legalis_case_docket";

function saveTrialToDocket() {
  const caseTitle = State.caseTitle || "Untitled Case";
  const verdictData = State.verdictData || State.demoVerdictData;
  if (!verdictData) return;
  
  const trial = {
    id: Date.now().toString(36) + Math.random().toString(36).slice(2, 7),
    title: caseTitle,
    jurisdiction: State.jurisdiction || "—",
    verdict: verdictData.verdict || "Unknown",
    probability: verdictData.probability || 0,
    sensitivity: verdictData.sensitivity || "",
    date: new Date().toISOString(),
    mode: State.trialMode || "live",
    transcriptCount: State.transcriptEntries.length,
    objections: State.metrics.objections,
    admitted: State.metrics.admitted,
    fullTranscript: State.transcriptEntries.map(e => ({
      agent: e.agent,
      text: e.text,
      phase: e.phase,
    })),
    verdictData: verdictData,
    shadowJuryNarrative: State.demoShadowNarrative || State.graphState?.shadow_jury_results?.narrative || [],
    deliberationSnapshot: State.graphState?.deliberation_snapshot || null,
    caseDescription: State.caseText || "",
  };
  
  let docket = [];
  try {
    docket = JSON.parse(localStorage.getItem(DOCKET_KEY) || "[]");
  } catch {}
  
  docket.unshift(trial);
  if (docket.length > 50) docket = docket.slice(0, 50);
  
  try {
    localStorage.setItem(DOCKET_KEY, JSON.stringify(docket));
  } catch (e) {
    console.warn("Could not save trial to docket (storage full?):", e);
  }
  renderCaseDocket();
}

function renderCaseDocket() {
  const container = $("dashboardCaseList");
  if (!container) return;
  
  let docket = [];
  try {
    docket = JSON.parse(localStorage.getItem(DOCKET_KEY) || "[]");
  } catch {}
  
  if (!docket.length) {
    container.innerHTML = `<div style="padding: 20px; color: var(--muted); font-size: 0.8rem; text-align: center;">
      <i class="fas fa-folder-open" style="font-size: 24px; margin-bottom: 8px; display: block; opacity: 0.5;"></i>
      No past trials yet. Run a demo or start a new trial to see results here.
    </div>`;
    return;
  }
  
  container.innerHTML = docket.map(trial => {
    const date = new Date(trial.date);
    const dateStr = date.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
    const verdict = trial.verdict || "Unknown";
    const isDefense = verdict.toUpperCase().includes("NOT GUILTY") || verdict.toUpperCase().includes("NOT LIABLE");
    const verdictColor = isDefense ? "var(--defense)" : "var(--prosecutor)";
    const prob = Math.round((trial.probability || 0) * 100);
    const hasReplay = trial.fullTranscript && trial.fullTranscript.length > 0;
    
    return `
    <div class="case-card" style="padding: 12px; margin-bottom: 10px; background: var(--bg); border-radius: 8px; border-left: 3px solid ${verdictColor}; position: relative;">
      <button onclick="deleteDocketEntry('${trial.id}')" style="position:absolute;top:8px;right:8px;background:none;border:none;color:var(--muted);cursor:pointer;font-size:14px;padding:4px 8px;border-radius:4px;transition:all 0.2s;" onmouseover="this.style.color='var(--prosecutor)';this.style.background='rgba(192,57,43,0.1)'" onmouseout="this.style.color='var(--muted)';this.style.background='none'" title="Delete this trial">
        <i class="fas fa-times"></i>
      </button>
      <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 6px; padding-right: 30px;">
        <div style="font-size: 0.85rem; font-weight: 600; color: var(--text); flex: 1; ${hasReplay ? 'cursor: pointer;' : ''}" ${hasReplay ? `onclick="replaySavedTrial('${trial.id}')"` : ''}>${escapeHtml(trial.title)}</div>
        <div style="font-size: 0.65rem; color: var(--muted); margin-left: 8px;">${dateStr}</div>
      </div>
      <div style="font-size: 0.7rem; color: var(--muted); margin-bottom: 8px;">${escapeHtml(trial.jurisdiction)}</div>
      <div style="display: flex; gap: 12px; flex-wrap: wrap; align-items: center;">
        <span style="font-size: 0.75rem; font-weight: 700; color: ${verdictColor};">${escapeHtml(verdict)}</span>
        <span style="font-size: 0.65rem; color: var(--muted);">${prob}% burden met</span>
        <span style="font-size: 0.65rem; color: var(--muted);">${trial.transcriptCount || 0} entries</span>
        <span style="font-size: 0.65rem; color: var(--muted);">${trial.objections || 0} objections</span>
        <span style="font-size: 0.65rem; color: var(--muted); text-transform: uppercase;">${trial.mode || "live"}</span>
        ${hasReplay ? '<span style="font-size: 0.65rem; color: var(--accent);"><i class="fas fa-play-circle"></i> Click to replay</span>' : ''}
      </div>
    </div>`;
  }).join("");
}

function deleteDocketEntry(trialId) {
  if (!confirm("Delete this trial from the Case Docket?")) return;
  
  let docket = [];
  try {
    docket = JSON.parse(localStorage.getItem(DOCKET_KEY) || "[]");
  } catch {
    return;
  }
  
  docket = docket.filter(t => t.id !== trialId);
  localStorage.setItem(DOCKET_KEY, JSON.stringify(docket));
  renderCaseDocket();
}

function replaySavedTrial(trialId) {
  let docket = [];
  try {
    docket = JSON.parse(localStorage.getItem(DOCKET_KEY) || "[]");
  } catch {
    alert("Could not load saved trials.");
    return;
  }
  
  const trial = docket.find(t => t.id === trialId);
  if (!trial) {
    alert("Trial not found.");
    return;
  }
  
  if (!trial.fullTranscript || !trial.fullTranscript.length) {
    alert("This trial cannot be replayed (no transcript data).");
    return;
  }
  
  clearTranscript();
  State.trialMode = "replay";
  State.demoRunning = false;
  State.livePaused = false;
  clearTimeout(State.demoTimer);
  
  State.demoScript = trial.fullTranscript;
  State.demoStep = 0;
  State.demoRunning = true;
  State.caseTitle = trial.title;
  State.jurisdiction = trial.jurisdiction;
  State.liveStep = "opening";
  State.verdictData = null;
  
  State.demoVerdictData = trial.verdictData || {
    verdict: trial.verdict,
    probability: trial.probability,
    sensitivity: trial.sensitivity || "",
    juries: State.shadowJuries,
    title: trial.title,
  };
  
  State.demoShadowNarrative = trial.shadowJuryNarrative || [];
  
  if (trial.caseDescription) {
    State.caseText = trial.caseDescription;
  }
  
  updateNavBar(trial.title, trial.jurisdiction, "Replaying");
  switchView("trial");
  
  setTimeout(() => stepDemo(), 500);
}

function clearCaseDocket() {
  if (!confirm("Clear all saved trials from the Case Docket?")) return;
  localStorage.removeItem(DOCKET_KEY);
  renderCaseDocket();
}

// ── Dark Mode Toggle ──────────────────────────────────────────────────────────

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

document.addEventListener("DOMContentLoaded", function() {
  const themeBtn = document.getElementById("themeToggle");
  if (themeBtn) themeBtn.addEventListener("click", toggleTheme);
});
