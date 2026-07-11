"use strict";
// ── UI module — extracted from static/app.js ──

import { State, $, $$, showToast, escapeHtml, sleep, formatDuration, classifyStance, extractExhibitLabel, isTrialConcluded, AGENT_ABBR, AGENT_COLOR, AV_CLASS, JX_DATA, safeJson, toggleTheme } from './state.js';
import { clearTranscript, addTranscriptEntry, addSystemMessage, streamLines, importTranscriptFromGraphState, handleEvidenceFromEntry, syncEvidenceFromState, exportTranscript } from './transcript.js';
import { renderEvidenceBoard, renderObjectionHistory, renderClerkSummary, renderMotionRulings, renderDiscoverySummary } from './evidence.js';
import { buildLiveDeliberationSnapshot, renderShadowJuryConversation, renderVerdictView, renderVerdictCharts, renderJuryGrid, renderDeliberationView, renderConsensusRows, renderDeliberationTranscript, renderCaseRecordSummary, renderMiniChart, requestInsights, renderInsightResults, initInsightButtons, toggleInsightExpand } from './jury.js';

"use strict";

// ── State ────────────────────────────────────────────────────────────────────


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
    const data = await safeJson(res);
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

  renderMotionRulings();
  renderDiscoverySummary();

  if (viewId === "dashboard") {
    loadSaveList();
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
  $("pauseBtn")?.addEventListener("click", () => {
    try { togglePause(); } catch (e) {
      console.error("[Pause] Error:", e);
      showToast("Pause error: " + e.message, "error");
    }
  });
  $("newTrialBtn")?.addEventListener("click", () => {
    try { resetTrialWorkspace(); } catch (e) {
      console.error("[NewTrial] Error:", e);
      showToast("New Trial error: " + e.message, "error");
    }
  });
  $("exportTopBtn")?.addEventListener("click", () => exportTranscript("markdown"));
  $("exportReportBtn")?.addEventListener("click", () => exportTranscript("markdown"));
  $("saveBtn")?.addEventListener("click", saveCurrentTrial);
  $("playBriefBtn")?.addEventListener("click", playAudioBrief);
  $("profileBtn")?.addEventListener("click", () => {
    addSystemMessage("Court profile: JP workspace operator. No courtroom role is assigned to this profile.");
  });
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
  const saveBtn = $("saveBtn");
  if (saveBtn) {
    const noTrial = !State.graphState || Object.keys(State.graphState).length === 0;
    saveBtn.disabled = noTrial;
    saveBtn.style.opacity = noTrial ? "0.55" : "";
  }
}

function togglePause() {
  const hasActiveTrial = State.trialMode && (
    (State.trialMode === "demo" && State.demoScript.length && State.demoRunning) ||
    (State.trialMode === "live" && State.liveStep !== "done")
  );
  if (!hasActiveTrial) {
    showToast("No active trial to pause.", "warning", 2500);
    return;
  }
  State.livePaused = !State.livePaused;
  if (State.demoRunning) State.demoRunning = !State.livePaused;
  const btn = $("pauseBtn");
  if (btn) {
    btn.innerHTML = State.livePaused
      ? '<i class="fas fa-play"></i><span>Resume</span>'
      : '<i class="fas fa-pause"></i><span>Pause</span>';
  }
  showToast(State.livePaused ? "Trial paused" : "Trial resumed", "info", 2000);
  updateNavBar(State.caseTitle, State.jurisdiction, State.livePaused ? "Paused" : "In Trial");
  if (!State.livePaused) {
    if (State.trialMode === "demo" && State.demoScript.length) stepDemo();
    if (State.trialMode === "live" && State.liveStep !== "done") runLiveStep();
  }
}

function resetTrialWorkspace() {
  try {
    State.demoRunning = false;
    State.livePaused = false;
    State.liveRunning = false;
    clearTimeout(State.demoTimer);
    stopMetricsTimer();
    State.caseText = "";
    State.caseTitle = "—";
    State.jurisdiction = "—";
    State.graphState = {};
    State.liveStep = "discovery";
    State.phaseTimings = {};
    State.phaseStartTime = null;
    State.questions = [];
    State.witnessQueue = [];
    State.identifiedEvidence = [];
    State.verdictData = null;
    State.uploadedText = "";
    State.uploadedFiles = [];
    State.trialMode = null;
    const textArea = $("caseTextarea");
    if (textArea) textArea.value = "";
    const uploadInfo = $("uploadInfo");
    if (uploadInfo) uploadInfo.textContent = "";
    const audioInfo = $("audioUploadInfo");
    if (audioInfo) audioInfo.textContent = "";
    const mag = $("magistrateChat");
    if (mag) { mag.style.display = "none"; mag.innerHTML = ""; }
    const reviewEl = $("reviewStep");
    if (reviewEl) { reviewEl.style.display = "none"; reviewEl.innerHTML = ""; }
    const beginBtn = $("beginTrialBtn");
    if (beginBtn) beginBtn.style.display = "";
    const formGrid = document.querySelector(".form-grid");
    if (formGrid) formGrid.style.display = "";
    const pauseBtn = $("pauseBtn");
    if (pauseBtn) pauseBtn.innerHTML = '<i class="fas fa-pause"></i><span>Pause</span>';
    clearTranscript();
    renderVerdictView(null);
    renderDeliberationView();
    updateExportControls();
    updateNavBar("No active case", "Select jurisdiction", "Ready");
    updateWizardSteps(1);
    switchView("setup");
    console.log("[NewTrial] Workspace reset complete.");
  } catch(e) {
    console.error("[NewTrial] resetTrialWorkspace error:", e);
    showToast("Reset error: " + e.message, "error");
  }
}

async function saveCurrentTrial() {
  if (!State.graphState || Object.keys(State.graphState).length === 0) {
    showToast("No active trial to save.", "warning");
    return;
  }
  try {
    const resp = await fetch("/api/trial/save", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        graph_state: State.graphState,
        case_title: State.caseTitle || "Untitled Case",
        country: State.country || "Nigeria",
        current_step: State.liveStep || "discovery",
        elapsed_seconds: State.elapsed || 0,
        phase_timings: State.phaseTimings || {},
      }),
    });
    const data = await resp.json();
    if (resp.ok) {
      showToast(`Trial saved — ID: ${data.save_id}`, "success");
      await loadSaveList();
    } else {
      showToast(`Save failed: ${data.detail || "Unknown error"}`, "error");
    }
  } catch (e) {
    showToast(`Save error: ${e.message}`, "error");
  }
}

async function loadSaveList() {
  try {
    const resp = await fetch("/api/trial/saves");
    const data = await resp.json();
    const list = data.saves || [];
    renderSavedTrials(list);
  } catch (e) {
    // Silently fail — saves list is not critical
  }
}

async function loadTrialById(saveId) {
  try {
    const resp = await fetch(`/api/trial/load/${saveId}`);
    if (!resp.ok) {
      showToast(`Load failed: ${(await resp.json()).detail || "Unknown error"}`, "error");
      return;
    }
    const data = await resp.json();
    State.graphState = data.graph_state || {};
    State.caseTitle = data.case_title || "Loaded Case";
    State.country = data.country || "Nigeria";
    State.liveStep = data.current_step || "discovery";
    State.phaseTimings = data.phase_timings || {};
    State.elapsed = data.elapsed_seconds || 0;
    State.jurisdiction = data.country || "Nigeria";
    State.verdictData = null;

    if (["Guilty", "Liable", "Not Guilty", "Not Liable", "Coupable", "Non coupable"].includes(data.verdict)) {
      State.verdictData = {
        verdict: data.verdict,
        case_title: data.case_title,
        main_verdict: data.verdict,
      };
    }

    clearTranscript();
    updateNavBar(State.caseTitle, State.country, "Loaded");
    updateExportControls();
    populateLegalReference(State.country || "United States");
    switchView("trial");

    if (State.graphState.transcript && Array.isArray(State.graphState.transcript)) {
      importTranscriptFromGraphState(State.graphState.transcript);
    }

    showToast(`Loaded: ${State.caseTitle}`, "success");
    loadSaveList();
  } catch (e) {
    showToast(`Load error: ${e.message}`, "error");
  }
}

function renderSavedTrials(saves) {
  const container = $("dashboardCaseList");
  if (!container) return;
  if (!saves.length) {
    container.innerHTML = `<div style="padding:10px;color:var(--muted);font-size:0.8rem">No saved trials yet.</div>`;
    return;
  }
  container.innerHTML = saves.map(s => {
    const vColor = (s.verdict || "").toUpperCase().includes("NOT GUILTY") || (s.verdict || "").toUpperCase().includes("NOT LIABLE") ? "var(--defense)"
      : (s.verdict || "").toUpperCase().includes("GUILTY") || (s.verdict || "").toUpperCase().includes("LIABLE") ? "var(--prosecutor)"
      : "var(--muted)";
    return `
    <div class="case-row" onclick="loadTrialById('${escapeHtml(s.save_id)}')">
      <div>
        <div class="case-title">${escapeHtml(s.case_title || "Untitled")}</div>
        <div class="case-meta">${escapeHtml(s.country || "")} — ${escapeHtml(s.saved_at || "")}</div>
      </div>
      <div><span class="case-badge badge-trial">${escapeHtml(s.verdict || "In Progress")}</span></div>
      <div></div>
      <div></div>
      <div style="text-align:right;display:flex;gap:4px;">
        <button class="nav-btn" style="font-size:10px;padding:4px 8px" onclick="event.stopPropagation();loadTrialById('${escapeHtml(s.save_id)}')"><i class="fas fa-folder-open"></i> Load</button>
        <button class="nav-btn" style="font-size:10px;padding:4px 8px;background:var(--prosecutor);color:#fff;border:none" onclick="event.stopPropagation();deleteTrial('${escapeHtml(s.save_id)}')"><i class="fas fa-trash"></i></button>
      </div>
    </div>`;
  }).join("");
}

async function deleteTrial(saveId) {
  if (!confirm(`Delete saved trial? This cannot be undone.`)) return;
  try {
    const resp = await fetch(`/api/trial/save/${saveId}`, { method: "DELETE" });
    if (resp.ok) {
      showToast(`Trial deleted.`, "success");
      await loadSaveList();
    } else {
      const data = await resp.json();
      showToast(`Delete failed: ${data.detail || "Unknown error"}`, "error");
    }
  } catch (e) {
    showToast(`Delete error: ${e.message}`, "error");
  }
}


async function loadJurisdictions() {
  try {
    const res = await fetch("/api/jurisdictions");
    const data = await safeJson(res);
    Object.assign(JX_DATA, data.data || {});
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
        const data = await safeJson(res);
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
      State.identifiedEvidence = magData.identified_evidence || [];

      console.log("[Magistrate] Response:", {
        ok: magRes.ok,
        status: magRes.status,
        questions: State.questions.length,
        witnesses: State.witnessQueue,
        missingEvidence: State.missingEvidence,
        missingWitnesses: State.missingWitnesses,
        identifiedEvidence: State.identifiedEvidence,
      });

      // Always show the pre-trial form — never auto-skip
      try {
        renderPreTrialForm();
      } catch (formErr) {
        console.error("[Magistrate] Form render error:", formErr);
        showToast("Form rendering error: " + formErr.message, "error", 6000);
      }
      switchView("setup");
      hideCaseDetailsForm();
      document.querySelector(".magistrate-chat")?.scrollIntoView({ behavior: "smooth" });
    } catch (e) {
      console.error("[Magistrate] Error:", e);
      showToast(`Magistrate error: ${e.message}`, "error", 6000);
      updateWizardSteps(1);
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
      info.textContent = "Recording requires HTTPS or localhost. Use 'Attach File' or 'Upload Audio File' instead.";
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
    showToast("Recording started — speak your case facts", "info", 2500);
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
    const data = await safeJson(res);
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
        const data = await safeJson(res);
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

  // Section 0: Witnesses identified (always shown if present)
  if (State.witnessQueue && State.witnessQueue.length > 0) {
    wizard.innerHTML += `
      <div class="mag-msg" style="margin-bottom:20px;">
        <div class="mag-avatar"><i class="fas fa-users"></i></div>
        <div class="mag-bubble" style="border-left-color:var(--gold);">
          <div class="q-num" style="color:var(--gold);font-weight:700;">Witnesses Identified (${State.witnessQueue.length})</div>
          <div style="margin-bottom:8px;">The Magistrate has identified the following individuals from the case facts for witness examination:</div>
          <div style="display:flex;flex-wrap:wrap;gap:6px;">
            ${State.witnessQueue.map(w => `<span style="background:var(--bg);padding:4px 10px;border-radius:12px;font-size:12px;font-weight:600;">${escapeHtml(w)}</span>`).join("")}
          </div>
        </div>
      </div>`;
  }

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

  // Section 2: Clarifying Questions (or no-questions message)
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
  } else {
    wizard.innerHTML += `
      <div class="mag-msg" style="margin-bottom:16px;">
        <div class="mag-avatar"><i class="fas fa-check-circle" style="color:var(--witness);"></i></div>
        <div class="mag-bubble" style="border-left-color:var(--witness);">
          <div class="q-num" style="color:var(--witness);">✓ Case Facts Sufficient</div>
          <div>The Magistrate has reviewed your case and finds the factual record complete. No further clarifying questions are needed at this stage. You may review and proceed to trial.</div>
        </div>
      </div>`;
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
      const statusEl = document.querySelector(`.pretrial-audio-status[data-q="${idx}"]`);
      const textarea = document.querySelector(`.pretrial-answer[data-q="${idx}"]`);
      await handleAudioRecording(btn, statusEl, textarea);
    });
  });
}

function attachMissingItemsAudioHandlers() {
  $$(".missing-ev-audio-btn").forEach(btn => {
    btn.addEventListener("click", async () => {
      const idx = btn.dataset.missingEv;
      const statusEl = document.querySelector(`.missing-ev-audio-status[data-missing-ev="${idx}"]`);
      const textarea = document.querySelector(`.missing-evidence-answer[data-missing-ev="${idx}"]`);
      await handleAudioRecording(btn, statusEl, textarea);
    });
  });
  
  $$(".missing-wit-audio-btn").forEach(btn => {
    btn.addEventListener("click", async () => {
      const idx = btn.dataset.missingWit;
      const statusEl = document.querySelector(`.missing-wit-audio-status[data-missing-wit="${idx}"]`);
      const textarea = document.querySelector(`.missing-witness-answer[data-missing-wit="${idx}"]`);
      await handleAudioRecording(btn, statusEl, textarea);
    });
  });
}

async function handleAudioRecording(btn, statusEl, textarea) {
  if (!navigator.mediaDevices || !window.MediaRecorder) {
    if (statusEl) {
      statusEl.textContent = "Recording requires HTTPS or localhost";
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
        const data = await safeJson(res);
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
  const evidenceCount = (State.identifiedEvidence || []).length;

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
      
      <div style="display: grid; grid-template-columns: 1fr 1fr 1fr 1fr; gap: 16px; margin-bottom: 20px;">
        <div style="padding: 12px; background: var(--card); border-radius: 8px; text-align: center;">
          <div style="font-size: 24px; font-weight: 700; color: var(--accent);">${answerCount}</div>
          <div style="font-size: 11px; color: var(--muted);">Questions Answered</div>
        </div>
        <div style="padding: 12px; background: var(--card); border-radius: 8px; text-align: center;">
          <div style="font-size: 24px; font-weight: 700; color: var(--accent);">${witnessCount}</div>
          <div style="font-size: 11px; color: var(--muted);">Witnesses Identified</div>
        </div>
        <div style="padding: 12px; background: var(--card); border-radius: 8px; text-align: center;">
          <div style="font-size: 24px; font-weight: 700; color: var(--accent);">${evidenceCount}</div>
          <div style="font-size: 11px; color: var(--muted);">Evidence Items</div>
        </div>
        <div style="padding: 12px; background: var(--card); border-radius: 8px; text-align: center;">
          <div style="font-size: 24px; font-weight: 700; color: var(--accent);">${State.shadowJuries || 20}</div>
          <div style="font-size: 11px; color: var(--muted);">Shadow Juries</div>
        </div>
      </div>

      ${evidenceCount > 0 ? `
      <div style="margin-bottom: 16px;">
        <div style="font-size: 12px; font-weight: 600; color: var(--muted); margin-bottom: 8px;">
          <i class="fas fa-folder-open" style="margin-right: 6px;"></i>Evidence Identified
        </div>
        <div style="display: flex; flex-direction: column; gap: 4px;">
          ${(State.identifiedEvidence || []).map(e => `
            <div style="padding: 6px 10px; background: var(--card); border-radius: 6px; font-size: 12px; color: var(--text); border-left: 3px solid var(--gold);">
              ${escapeHtml(e)}
            </div>
          `).join("")}
        </div>
      </div>
      ` : ""}
      
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
    const data = await safeJson(res);
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
    showToast("Trial commenced — all rise.", "info", 2500);
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
    console.error("[TrialStart] Error:", e);
    showToast(`Trial start error: ${e.message}`, "error", 6000);
    if (submitBtn) { submitBtn.disabled = false; submitBtn.innerHTML = '<i class="fas fa-gavel"></i> Begin Trial'; }
  }
}

// ── Demo case streaming ───────────────────────────────────────────────────────

function initDemoButtons() {
  $("demoTheft")    ?.addEventListener("click", () => loadDemo("theft"));
  $("demoContract") ?.addEventListener("click", () => loadDemo("contract"));
  $("demoVance")    ?.addEventListener("click", () => loadDemo("vance"));
}

// ── Benchmark ─────────────────────────────────────────────────────────────────

function hasCompletedTrial() {
  const gs = State.graphState;
  return gs && Array.isArray(gs.transcript) && gs.transcript.length > 0 && !!gs.main_verdict;
}

function initBenchmarkButtons() {
  $("runBenchmarkBtn")?.addEventListener("click", () => runBenchmark(true));
  $("runBenchmarkLiveBtn")?.addEventListener("click", () => {
    if (!hasCompletedTrial()) {
      showToast("Run a full trial first before using Live benchmark mode.", "warning", 4000);
      return;
    }
    runBenchmark(false);
  });
}

async function runBenchmark(useMock) {
  const caseText = State.caseText || getCaseText();
  if (!caseText.trim()) {
    showToast("Please enter case facts in Setup before running a benchmark.", "warning", 4000);
    return;
  }

  State.benchmarkRunning = true;
  const statusEl = $("benchmarkStatus");
  const btnMock = $("runBenchmarkBtn");
  const btnLive = $("runBenchmarkLiveBtn");
  
  const modeLabel = useMock ? "Mock (no API calls)" : "Live (Qwen API calls)";
  
  if (statusEl) {
    statusEl.innerHTML = `<i class="fas fa-spinner fa-spin"></i> Running benchmark in <strong>${modeLabel}</strong> mode...`;
  }
  if (btnMock) { btnMock.disabled = true; btnMock.style.opacity = "0.5"; }
  if (btnLive) { btnLive.disabled = true; btnLive.style.opacity = "0.5"; }

  const progressEl = $("benchmarkProgress");
  const stepsEl = $("benchProgressSteps");
  const progressTitle = $("benchProgressTitle");
  const progressIcon = $("benchProgressIcon");
  if (progressEl) progressEl.style.display = "";
  if (progressTitle) progressTitle.textContent = `Running benchmark (${modeLabel})...`;
  if (stepsEl) stepsEl.innerHTML = "";

  const params = new URLSearchParams({
    case_description: caseText,
    num_runs: String(useMock ? 3 : 1),
    use_mock: String(useMock),
  });
  if (hasCompletedTrial()) {
    params.set("trial_context", JSON.stringify(State.graphState));
  }

  const url = `/api/benchmark/run-stream?${params}`;
  const evtSource = new EventSource(url);

  const timeoutMs = useMock ? 30000 : 600000;
  let settled = false;
  const timeoutId = setTimeout(() => {
    if (!settled) {
      evtSource.close();
      if (progressEl) progressEl.style.display = "none";
      if (statusEl) statusEl.innerHTML = `<i class="fas fa-times-circle" style="color:var(--prosecutor)"></i> Benchmark timed out.`;
      State.benchmarkRunning = false;
      if (btnMock) { btnMock.disabled = false; btnMock.style.opacity = ""; }
      if (btnLive) { btnLive.disabled = false; btnLive.style.opacity = ""; }
    }
  }, timeoutMs);

  function appendStep(html) {
    if (stepsEl) stepsEl.innerHTML += html;
  }

  evtSource.addEventListener("raw_llm_start", (e) => {
    const d = JSON.parse(e.data);
    appendStep(`<div style="color:var(--muted);margin-top:6px;">⚡ Raw LLM query ${d.run}/${d.total}...</div>`);
  });

  evtSource.addEventListener("raw_llm_done", (e) => {
    const d = JSON.parse(e.data);
    if (d.error) {
      appendStep(`<div style="color:var(--prosecutor);">❌ Raw LLM: ${d.error}</div>`);
    } else {
      const snippet = escapeHtml((d.response || "").slice(0, 120));
      appendStep(`<div style="color:var(--defense);">✅ Raw LLM: "${snippet}${d.response?.length > 120 ? "..." : ""}"</div>`);
    }
  });

  evtSource.addEventListener("single_start", (e) => {
    appendStep(`<div style="color:var(--muted);margin-top:6px;">⚡ Single-Agent trial...</div>`);
  });

  evtSource.addEventListener("single_done", (e) => {
    const d = JSON.parse(e.data);
    if (d.error) {
      appendStep(`<div style="color:var(--prosecutor);">❌ Single-Agent: ${d.error}</div>`);
    } else {
      appendStep(`<div style="color:var(--defense);">✅ Single-Agent: ${escapeHtml(d.verdict || "?")} (${d.time?.toFixed(1) || "?"}s)</div>`);
    }
  });

  evtSource.addEventListener("multi_result", (e) => {
    const d = JSON.parse(e.data);
    if (d.error) {
      appendStep(`<div style="color:var(--prosecutor);">❌ Codex legalist: ${d.error}</div>`);
    } else {
      const src = d.source === "existing_trial" ? " (from existing trial)" : "";
      appendStep(`<div style="color:var(--gold);font-weight:600;">✅ Codex legalist: ${escapeHtml(d.verdict || "?")}${src}</div>`);
    }
  });

  evtSource.addEventListener("complete", (e) => {
    settled = true;
    clearTimeout(timeoutId);
    evtSource.close();
    const data = JSON.parse(e.data);
    State.benchmarkData = data;
    if (progressEl) progressEl.style.display = "none";
    renderBenchmarkView();
    if (statusEl) {
      if (data.errors && data.errors.length > 0) {
        statusEl.innerHTML = `<i class="fas fa-exclamation-triangle" style="color:var(--prosecutor)"></i> Benchmark completed with errors: ${data.errors[0].slice(0, 100)}...`;
      } else {
        statusEl.innerHTML = `<i class="fas fa-check" style="color:var(--defense)"></i> Benchmark complete (${modeLabel}). Results shown below.`;
      }
    }
    State.benchmarkRunning = false;
    if (btnMock) { btnMock.disabled = false; btnMock.style.opacity = ""; }
    if (btnLive) { btnLive.disabled = false; btnLive.style.opacity = ""; }
  });

  evtSource.onerror = () => {
    if (settled) return;
    settled = true;
    clearTimeout(timeoutId);
    evtSource.close();
    if (progressEl) progressEl.style.display = "none";
    if (statusEl) statusEl.innerHTML = `<i class="fas fa-times-circle" style="color:var(--prosecutor)"></i> Benchmark connection lost.`;
    State.benchmarkRunning = false;
    if (btnMock) { btnMock.disabled = false; btnMock.style.opacity = ""; }
    if (btnLive) { btnLive.disabled = false; btnLive.style.opacity = ""; }
  };
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
    const data = await safeJson(res);
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
      sentence:    data.sentence || null,
    };
    State.caseTitle   = data.title;
    State.jurisdiction = data.jurisdiction || "—";
    State.liveStep = "discovery";
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
    console.error("[DemoLoad] Error:", e);
    showToast("Demo load error: " + e.message, "error", 6000);
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
  showToast("Trial completed — court is adjourned.", "success", 4000);

  // Build deliberation_snapshot from the demo's deliberation-transcript entries
  const jurorEntries = State.transcriptEntries.filter(e =>
    (e.agent === "Juror" || e.agent === "Foreperson") &&
    (e.phase === "Jury Deliberation" || e.phase === "Deliberation")
  );

  if (jurorEntries.length > 0) {
    const positions = [];
    let guiltyCount = 0, notGuiltyCount = 0, undecidedCount = 0;
    const cs = State.graphState?.case_type || "Criminal";
    jurorEntries.forEach((entry, idx) => {
      const stance = classifyStance(entry.text);
      if (stance === "guilty") guiltyCount++;
      else if (stance === "not-guilty") notGuiltyCount++;
      else undecidedCount++;
      const jMatch = entry.agent.match(/Juror\s*(\d+)/) || entry.text.match(/Juror\s*#?(\d+)/i);
      const jId = jMatch ? parseInt(jMatch[1]) : idx + 1;
      positions.push({
        juror_id: jId,
        name: `Juror ${jId}`,
        occupation: "Citizen juror",
        persona: "Deliberation",
        stance: stance === "guilty" ? (cs === "Civil" ? "Liable" : "Guilty")
              : stance === "not-guilty" ? (cs === "Civil" ? "Not Liable" : "Not Guilty")
              : "Undecided",
        quote: entry.text.slice(0, 120),
      });
    });
    State.graphState.deliberation_snapshot = {
      type: "jury",
      round: 1,
      total: positions.length,
      guilty_or_liable_count: guiltyCount,
      not_guilty_or_not_liable_count: notGuiltyCount,
      undecided_count: undecidedCount,
      verdict: State.demoVerdictData?.verdict || "Hung",
      rationale: `${guiltyCount} for burden met, ${notGuiltyCount} for burden not met, ${undecidedCount} undecided.`,
      positions,
    };
  }

  // Build shadow_jury_results from demo case data
  const shadowNarrative = State.demoShadowNarrative || [];
  if (shadowNarrative.length > 0) {
    const burdenMetVotes = shadowNarrative.filter(n =>
      /guilty|liable|coupable|incarcération/i.test(n.content || "")
    ).length;
    State.graphState.shadow_jury_results = {
      win_probability: State.demoVerdictData?.probability || 0.5,
      burden_met_votes: burdenMetVotes,
      burden_not_met_votes: shadowNarrative.length - burdenMetVotes,
      hung_votes: 0,
      total_juries: shadowNarrative.length,
      narrative: shadowNarrative.map((n, i) => ({
        name: n.name || `Shadow Juror ${i + 1}`,
        content: n.content || "",
      })),
    };
  }

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


async function runLiveStep() {
  if (State.liveStep === "done" || State.livePaused || State.liveRunning) return;
  State.liveRunning = true;
  State.phaseStartTime = State.phaseStartTime || performance.now();

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
    const data = await safeJson(res);
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
    State.currentWitnessName = data.graph_state?.current_witness || null;

    const now = performance.now();
    if (State.phaseStartTime) {
      const elapsed = ((now - State.phaseStartTime) / 1000).toFixed(1);
      State.phaseTimings[State.liveStep] = (parseFloat(State.phaseTimings[State.liveStep]) || 0) + parseFloat(elapsed);
    }
    State.phaseStartTime = now;

    State.liveStep   = data.next_step;
    State.liveRunning = false;

    // Update evidence board from state
    syncEvidenceFromState(State.graphState);
    renderClerkSummary();
    renderMotionRulings();
    renderDiscoverySummary();

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
      showToast("Trial completed — court is adjourned.", "success", 5000);
      if (data.verdict_data) {
        State.verdictData = data.verdict_data;
        renderVerdictView(data.verdict_data);
        renderDeliberationView();
        updateExportControls();
        saveTrialToDocket();
        setTimeout(() => {
          switchView("verdict");
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
    showToast(`Trial step failed: ${e.message}`, "error");
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
      showToast("Please provide a response to the question.", "warning", 3000);
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
      const data = await safeJson(res);
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
      showToast("Error: " + e.message, "error", 5000);
      submitBtn.disabled = false;
      submitBtn.innerHTML = '<i class="fas fa-paper-plane"></i> Submit Response';
    }
  });
}

// ── Transcript helpers ────────────────────────────────────────────────────────


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
  "discovery":         "Discovery Disclosure",
  "motions":           "Pre-Trial Motions",
  "opening":           "Opening Statements",
  "evidence":          "Evidence Presentation",
  "witness_direct":    "Witness Direct Examination",
  "witness_cross":     "Witness Cross-Examination",
  "witness_redirect":  "Witness Redirect & Impeachment",
  "rebuttal":          "Rebuttal Evidence",
  "closing":           "Closing Arguments",
  "jury_instructions": "Jury Instructions",
  "jury_deliberation": "Jury Deliberation",
  "shadow_jury":       "Shadow Jury Analysis",
  "sentencing":        "Sentencing Hearing",
};

function updateLiveProgress() {
  const STEPS = ["discovery", "motions", "opening", "evidence", "witness_direct", "witness_cross", "witness_redirect", "rebuttal", "closing", "jury_instructions", "jury_deliberation", "shadow_jury", "sentencing"];
  const idx   = STEPS.indexOf(State.liveStep);
  const label = STEP_LABELS[State.liveStep] || State.liveStep;
  const pct   = idx >= 0 ? Math.round(((idx + 1) / STEPS.length) * 100) : 0;

  const lbl = $("liveProgressLabel");
  if (lbl) {
    const elapsed = State.phaseStartTime ? Math.round((performance.now() - State.phaseStartTime) / 1000) : 0;
    const etas = elapsed > 0 ? ` (${elapsed}s elapsed)` : "";
    lbl.textContent = `${label}${etas} — ${idx + 1}/${STEPS.length}`;
  }
}

// ── Verdict view rendering ────────────────────────────────────────────────────


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
    { label: "Codex legalist", value: multiCitations, max: Math.max(rawCitations, singleCitations, multiCitations, 1), cls: "bar-success" },
  ]);
  
  renderBenchmarkBarChart("benchHallucChart", [
    { label: "Raw LLM", value: rawHalluc, max: Math.max(rawHalluc, singleHalluc, multiHalluc, 1), cls: rawHalluc > singleHalluc ? "bar-danger" : "bar-warning" },
    { label: "Single-Agent", value: singleHalluc, max: Math.max(rawHalluc, singleHalluc, multiHalluc, 1), cls: "bar-warning" },
    { label: "Codex legalist", value: multiHalluc, max: Math.max(rawHalluc, singleHalluc, multiHalluc, 1), cls: "bar-success" },
  ]);
  
  // Update sample responses
  const rawSample = $("benchRawSample");
  const rawMeta = $("benchRawMeta");
  if (rawSample && rawResults[0]) {
    const resp = rawResults[0].response || "";
    rawSample.textContent = resp.slice(0, 200) + (resp.length > 200 ? "..." : "");
    if (rawMeta) rawMeta.innerHTML = `<span>${rawHalluc} hallucinations</span><span>${rawCitations} citations</span>`;
  }
  
  const singleSample = $("benchSingleSample");
  const singleMeta = $("benchSingleMeta");
  if (singleSample && singleResults[0]) {
    const resp = singleResults[0].reasoning || singleResults[0].response || "";
    const v = singleResults[0].verdict || "";
    singleSample.innerHTML = `<strong>Verdict:</strong> ${escapeHtml(v)}<br><br>${escapeHtml(resp.slice(0, 300))}${resp.length > 300 ? "..." : ""}`;
    if (singleMeta) singleMeta.innerHTML = `<span>${singleResults[0].time?.toFixed(1) || "?"}s</span><span>${singleHalluc} hallucinations</span><span>${singleCitations} citations</span>`;
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
    "CODEX legalist TRIAL REPORT",
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
  const slug = (State.caseTitle || "codex-legalist-trial").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
  a.href = url;
  a.download = `${slug || "codex-legalist-trial"}-report.txt`;
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
    showToast("Could not load saved trials.", "error", 4000);
    return;
  }
  
  const trial = docket.find(t => t.id === trialId);
  if (!trial) {
    showToast("Trial not found in docket.", "error", 4000);
    return;
  }
  
  if (!trial.fullTranscript || !trial.fullTranscript.length) {
    showToast("This trial cannot be replayed (no transcript data).", "warning", 4000);
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
  State.liveStep = "discovery";
  State.verdictData = null;
  
  State.demoVerdictData = trial.verdictData || {
    verdict: trial.verdict,
    probability: trial.probability,
    sensitivity: trial.sensitivity || "",
    juries: State.shadowJuries,
    title: trial.title,
    sentence: trial.sentence || null,
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


document.addEventListener("DOMContentLoaded", function() {
  const themeBtn = document.getElementById("themeToggle");
  if (themeBtn) themeBtn.addEventListener("click", toggleTheme);
});


export {
    STEP_LABELS,
    appendCaseText,
    attachMissingItemsAudioHandlers,
    attachPreTrialAudioHandlers,
    buildAudioBrief,
    buildTrialReport,
    checkApiHealth,
    clearCaseDocket,
    collectPreTrialAnswers,
    deleteDocketEntry,
    deleteTrial,
    exportTrialReport,
    finishDemo,
    getCaseText,
    handleAudioRecording,
    hideCaseDetailsForm,
    inferAgentRole,
    initBenchmarkButtons,
    initBottomTimeline,
    initCaseTabs,
    initDemoButtons,
    initDrawers,
    initNavActions,
    initSetupForm,
    initSpeedSlider,
    initTabs,
    launchLiveTrial,
    loadDemo,
    loadJurisdictions,
    loadSaveList,
    loadTrialById,
    playAudioBrief,
    populateLegalReference,
    renderAgentRoster,
    renderBenchmarkBarChart,
    renderBenchmarkView,
    renderCaseDocket,
    renderPreTrialForm,
    renderReviewStep,
    renderSavedTrials,
    replaySavedTrial,
    resetTrialWorkspace,
    resizeTimer,
    runBenchmark,
    runLiveStep,
    saveCurrentTrial,
    saveTrialToDocket,
    showHumanInputDialog,
    startMetricsTimer,
    stepDemo,
    stopMetricsTimer,
    switchView,
    syncTimeline,
    toggleObjectionText,
    togglePause,
    toggleVoiceRecording,
    transcribeRecordedAudio,
    updateExportControls,
    updateJxSummary,
    updateLiveProgress,
    updateLiveStepBadge,
    updateMetricsDisplay,
    updateNavBar,
    updateWizardSteps
};
