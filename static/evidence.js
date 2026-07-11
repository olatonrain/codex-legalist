"use strict";
// ── EVIDENCE module — extracted from static/app.js ──

import { State, $, $$, showToast, escapeHtml, sleep, formatDuration, classifyStance, extractExhibitLabel, isTrialConcluded, AGENT_ABBR, AGENT_COLOR, AV_CLASS, JX_DATA, safeJson, initTheme, toggleTheme } from './state.js';

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


function renderObjectionHistory() {
  const container = $("objectionHistoryContainer");
  if (!container) return;

  const structuredObjs = State.graphState?.objection_history || [];
  const liveObjs = State.objectionHistory || [];
  const allObjs = [...liveObjs];

  for (const sobj of structuredObjs) {
    const exists = allObjs.some(o => o.text && o.text.includes(sobj.evidence));
    if (!exists) {
      allObjs.push({
        who: sobj.objector || "Unknown",
        text: `${sobj.objection_type ? sobj.objection_type.toUpperCase() : "Objection"} — ${sobj.rationale || ""}`,
        ruling: sobj.ruling || "Recorded",
        objection_type: sobj.objection_type || "objection",
        rule_cited: sobj.rule_cited || "",
        ruling_rationale: sobj.ruling_rationale || "",
        source: "structured",
      });
    }
  }

  if (allObjs.length === 0) {
    container.innerHTML = `<div style="font-size:0.78rem;color:var(--muted)">No objections yet.</div>`;
    return;
  }

  container.innerHTML = allObjs.reverse().map((obj, idx) => {
    const fullText = obj.text || "";
    const truncated = fullText.length > 120 ? fullText.slice(0, 120) + "..." : fullText;
    const rulingCls = (obj.ruling || "").toLowerCase().includes("sustained") ? "sustained"
                    : (obj.ruling || "").toLowerCase().includes("overruled") ? "overruled" : "";
    const objType = obj.objection_type || "";
    const objTypeLabel = objType ? `<span class="obj-type-badge">${objType.toUpperCase()}</span>` : "";
    const ruleCited = obj.rule_cited ? `<div style="font-size:0.65rem;color:var(--gold);margin-top:2px;">${escapeHtml(obj.rule_cited)}</div>` : "";

    return `
    <div class="obj-item">
      <div class="obj-who">${escapeHtml(obj.who || obj.agent || "Unknown")} ${objTypeLabel}</div>
      <div class="obj-reason">${escapeHtml(truncated)}</div>${ruleCited}
      <div class="obj-ruling">
        <span class="ruling-result ${rulingCls}">${escapeHtml((obj.ruling || "Recorded").toUpperCase())}</span>
        ${obj.time ? `<span style="font-size:0.65rem;color:var(--muted);margin-left:6px">${obj.time}</span>` : ""}
      </div>
    </div>`;
  }).join("");
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

function renderMotionRulings() {
  const container = $("motionRulingsContainer");
  const section = $("motionRulingsSection");
  if (!container || !section) return;
  const rulings = State.graphState?.motion_rulings || [];
  if (rulings.length === 0) {
    section.style.display = "none";
    return;
  }
  section.style.display = "";
  container.innerHTML = rulings.map(r => {
    const granted = (r.ruling || "").toUpperCase() === "GRANTED";
    const color = granted ? "var(--defense)" : "var(--prosecutor)";
    return `
    <div class="obj-item" style="border-left-color:${color};margin-bottom:8px">
      <div class="obj-who">${escapeHtml(r.movant || "Unknown")} — ${escapeHtml(r.motion_type || "Motion")}</div>
      <div class="obj-reason" style="font-size:0.7rem;">${escapeHtml((r.arguing || "").slice(0, 100))}</div>
      <div class="obj-ruling">
        <span class="ruling-result ${granted ? 'overruled' : 'sustained'}">${escapeHtml((r.ruling || "").toUpperCase())}</span>
      </div>
      <div style="font-size:0.65rem;color:var(--muted);margin-top:2px;">${escapeHtml((r.rationale || "").slice(0, 120))}</div>
    </div>`;
  }).join("");
}

function renderDiscoverySummary() {
  const container = $("discoveryContainer");
  const section = $("discoverySection");
  if (!container || !section) return;
  const prosDisc = State.graphState?.disclosed_prosecution || [];
  const defDisc = State.graphState?.disclosed_defense || [];
  if (prosDisc.length === 0 && defDisc.length === 0) {
    section.style.display = "none";
    return;
  }
  section.style.display = "";
  container.innerHTML = `
    ${prosDisc.length ? `<div style="margin-bottom:8px"><b style="color:var(--prosecutor);font-size:0.7rem;">PROSECUTION</b>${prosDisc.map(i => `<div class="obj-item" style="font-size:0.7rem;border-left-color:var(--prosecutor);padding:6px 8px;margin:3px 0">${escapeHtml(i)}</div>`).join("")}</div>` : ""}
    ${defDisc.length ? `<div><b style="color:var(--defense);font-size:0.7rem;">DEFENCE</b>${defDisc.map(i => `<div class="obj-item" style="font-size:0.7rem;border-left-color:var(--defense);padding:6px 8px;margin:3px 0">${escapeHtml(i)}</div>`).join("")}</div>` : ""}
  `;
}


export {
    renderEvidenceBoard,
    renderObjectionHistory,
    renderClerkSummary,
    renderMotionRulings,
    renderDiscoverySummary
};
