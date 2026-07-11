"use strict";
// ── TRANSCRIPT module — extracted from static/app.js ──

import { State, $, $$, showToast, escapeHtml, sleep, formatDuration, classifyStance, extractExhibitLabel, isTrialConcluded, AGENT_ABBR, AGENT_COLOR, AV_CLASS, JX_DATA, safeJson, initTheme, toggleTheme } from './state.js';
import { renderObjectionHistory } from './evidence.js';

function importTranscriptFromGraphState(transcriptList) {
  const container = $("transcript");
  if (!container) return;
  container.innerHTML = "";
  if (!transcriptList || transcriptList.length === 0) {
    container.innerHTML = `<div class="no-transcript">Transcript loaded — 0 messages.</div>`;
    return;
  }
  for (const msg of transcriptList) {
    const content = typeof msg.content === "string" ? msg.content : String(msg.content || "");
    const agent = msg.name || msg.agent || "System";
    addTranscriptMessage(agent, content, "");
  }
}


async function exportTranscript(format = "markdown") {
  if (!State.graphState || !State.graphState.transcript) {
    addSystemMessage("No transcript to export.");
    return;
  }
  try {
    const resp = await fetch("/api/trial/transcript?format=" + format, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ graph_state: State.graphState, format }),
    });
    const data = await resp.json();
    const blob = new Blob([data.transcript], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `transcript_${State.caseTitle.replace(/\s+/g, "_")}_${new Date().toISOString().slice(0, 10)}.${format === "markdown" ? "md" : format}`;
    a.click();
    URL.revokeObjectURL(url);
  } catch (e) {
    addSystemMessage(`Export error: ${e.message}`);
  }
}

// ── Jurisdictions ─────────────────────────────────────────────────────────────


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
  const expertWitnesses = State.graphState?.expert_witnesses || [];
  const isExpert = agent === "Witness" && State.currentWitnessName && expertWitnesses.includes(State.currentWitnessName);
  const expertTag = isExpert ? `<span class="expert-badge">EXPERT</span>` : "";
  row.innerHTML = `
    <div class="msg-avatar ${avClass}">${abbr}</div>
    <div class="msg-content">
      <div class="msg-name" style="color:${color}">
        ${escapeHtml(agent)}${expertTag}
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


export {
    clearTranscript,
    addTranscriptEntry,
    addSystemMessage,
    streamLines,
    importTranscriptFromGraphState,
    handleEvidenceFromEntry,
    syncEvidenceFromState,
    exportTranscript
};
