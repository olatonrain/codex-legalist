"use strict";
// ── JURY module — extracted from static/app.js ──

import { State, $, $$, showToast, escapeHtml, sleep, formatDuration, classifyStance, extractExhibitLabel, isTrialConcluded, AGENT_ABBR, AGENT_COLOR, AV_CLASS, JX_DATA, safeJson, initTheme, toggleTheme } from './state.js';
import { addTranscriptEntry } from './transcript.js';


function buildLiveDeliberationSnapshot() {
  const jurorEntries = State.transcriptEntries.filter(e =>
    (e.agent === "Juror" || e.agent === "Foreperson") && 
    (e.phase === "Jury Deliberation" || e.phase === "Deliberation")
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
    const sentCard = $("sentencingCard");
    if (sentCard) sentCard.style.display = "none";
    const actualJuryCard = $("actualJuryCard");
    if (actualJuryCard) actualJuryCard.style.display = "none";
    renderVerdictCharts(null);
    renderCaseRecordSummary();
    renderShadowJuryConversation();
    return;
  }
  const verdict = String(vd.verdict || "No Verdict Reached");
  const upper = verdict.toUpperCase();
  const isDefense = upper.includes("NOT GUILTY") || upper.includes("NOT LIABLE");
  const color  = isDefense ? "#30d158" : "#ff453a";

  const vText = $("verdictText");
  const vSub  = $("verdictSub");
  if (vText) { vText.textContent = verdict; vText.style.color = color; }
  if (vSub)  vSub.textContent = vd.sensitivity || "";

  const sentCard = $("sentencingCard");
  if (sentCard) {
    const isSentencing = upper.includes("GUILTY") || upper.includes("LIABLE");
    if (isSentencing && vd.sentence) {
      sentCard.style.display = "";
      const sText = $("sentenceText");
      const sTerm = $("sentenceTerm");
      const sRationale = $("sentenceRationale");
      if (sText) sText.textContent = vd.sentence.sentence || "";
      if (sTerm) sTerm.textContent = vd.sentence.term || "";
      if (sRationale) sRationale.textContent = vd.sentence.rationale || "";
    } else {
      sentCard.style.display = "none";
    }
  }

  const actualJury = vd.actual_jury || {};
  const actualJuryCard = $("actualJuryCard");
  if (actualJuryCard && actualJury.total) {
    actualJuryCard.style.display = "";
    const burdenMet = actualJury.guilty_or_liable_count || 0;
    const burdenNot = actualJury.not_guilty_or_not_liable_count || 0;
    const undecided = actualJury.undecided_count || 0;
    const total = actualJury.total;
    const caseType = State.graphState?.case_type || "Criminal";
    const metLabel = caseType === "Civil" ? "Liable" : "Guilty";
    const notMetLabel = caseType === "Civil" ? "Not Liable" : "Not Guilty";

    const breakdownEl = $("juryVoteBreakdown");
    if (breakdownEl) {
      const pctMet = Math.round((burdenMet / total) * 100);
      const pctNot = Math.round((burdenNot / total) * 100);
      const pctUnd = Math.round((undecided / total) * 100);
      breakdownEl.innerHTML = `
        <div style="display:flex;gap:12px;flex-wrap:wrap;margin-bottom:8px;">
          <div style="flex:1;min-width:100px;padding:10px;background:rgba(192,57,43,0.1);border-radius:6px;text-align:center;">
            <div style="font-size:1.5rem;font-weight:700;color:var(--prosecutor);">${burdenMet}</div>
            <div style="font-size:0.75rem;color:var(--muted);">${metLabel} (${pctMet}%)</div>
          </div>
          <div style="flex:1;min-width:100px;padding:10px;background:rgba(39,174,96,0.1);border-radius:6px;text-align:center;">
            <div style="font-size:1.5rem;font-weight:700;color:var(--defense);">${burdenNot}</div>
            <div style="font-size:0.75rem;color:var(--muted);">${notMetLabel} (${pctNot}%)</div>
          </div>
          ${undecided > 0 ? `
          <div style="flex:1;min-width:100px;padding:10px;background:rgba(243,156,18,0.1);border-radius:6px;text-align:center;">
            <div style="font-size:1.5rem;font-weight:700;color:var(--witness);">${undecided}</div>
            <div style="font-size:0.75rem;color:var(--muted);">Undecided (${pctUnd}%)</div>
          </div>` : ""}
        </div>
        <div style="font-size:0.75rem;color:var(--muted);">
          ${actualJury.type === "bench" ? "Bench trial" : `Jury deliberation (${actualJury.round || 1} round${actualJury.round !== 1 ? "s" : ""})`}
          · ${total} juror${total !== 1 ? "s" : ""}
        </div>
      `;
    }

    const rationaleEl = $("forepersonRationale");
    if (rationaleEl) {
      const rationale = actualJury.rationale || "";
      rationaleEl.innerHTML = rationale
        ? `<i class="fas fa-quote-left" style="color:var(--gold);margin-right:6px;font-size:0.7rem;"></i>${escapeHtml(rationale)}`
        : "";
      rationaleEl.style.display = rationale ? "" : "none";
    }
  } else if (actualJuryCard) {
    actualJuryCard.style.display = "none";
  }

  const gNum  = $("gaugeNumber");
  const gSub  = $("gaugeSub");
  const pct = actualJury.total
    ? Math.round(((actualJury.guilty_or_liable_count || 0) / actualJury.total) * 100)
    : Math.round(((vd.probability ?? 0) || 0) * 100);
  const sjr = State.graphState?.shadow_jury_results || {};
  if (gNum)  { gNum.textContent = pct + "%"; gNum.style.color = pct < 50 ? "#0a84ff" : pct < 75 ? "#ff9f0a" : "#ff453a"; }
  if (gSub)  {
    if (actualJury.total) {
      gSub.textContent = `${actualJury.guilty_or_liable_count || 0} of ${actualJury.total} jurors found burden met`;
    } else {
      gSub.textContent = `${sjr.burden_met_votes ?? sjr.guilty_votes ?? 0} of ${vd.juries || sjr.total_juries || State.shadowJuries || 0} shadow juries found burden met`;
    }
  }

  renderVerdictCharts(pct);
  renderCaseRecordSummary();
  renderShadowJuryConversation();
}

// ── Benchmark View ─────────────────────────────────────────────────────────────


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
    const actualJury = State.verdictData?.actual_jury || {};
    const sjr = State.graphState?.shadow_jury_results || {};
    const useActual = actualJury.total > 0;
    const total = useActual ? actualJury.total : (State.verdictData?.juries || sjr.total_juries || State.shadowJuries || 0);
    const guilty  = useActual ? (actualJury.guilty_or_liable_count || 0) : (sjr.guilty_votes ?? Math.round((value / 100) * total));
    const ng      = useActual ? (actualJury.not_guilty_or_not_liable_count || 0) : (sjr.not_guilty_votes ?? (hasVerdict ? Math.max(total - guilty, 0) : 0));
    const hung    = useActual ? (actualJury.undecided_count || 0) : (sjr.hung_votes ?? 0);
    const chartTitle = useActual ? "Jury Vote Distribution" : "Shadow Jury Vote Distribution";
    Plotly.newPlot(voteChart, [{
      x: ["Burden Met","Burden Not Met","Undecided"], y: [guilty, ng, hung],
      type: "bar", marker: { color: ["#C0392B","#27AE60","#F39C12"] },
      text: [guilty, ng, hung], textposition: "outside",
      textfont: { family: "JetBrains Mono", size: isMobile ? 10 : 12, color: "#1A2A3A" },
    }], {
      margin: { t: 20, r: 10, b: 40, l: 35 },
      xaxis: { tickfont: { size: isMobile ? 10 : 11, family: "Inter" } },
      yaxis: { tickfont: { size: 10, family: "JetBrains Mono" }, title: { text: isMobile ? "" : (useActual ? "Jurors" : "Shadow Juries"), font: { size: 10 } } },
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
    ? positions.map((position, index) => {
        const backendStance = (position.stance || "").toUpperCase();
        let stance;
        if (backendStance.includes("NOT GUILTY") || backendStance.includes("NOT LIABLE")) {
          stance = "not-guilty";
        } else if (backendStance.includes("GUILTY") || backendStance.includes("LIABLE")) {
          stance = "guilty";
        } else if (backendStance.includes("UNDECIDED") || backendStance.includes("HUNG")) {
          stance = "undecided";
        } else {
          stance = classifyStance(position.quote || position.stance);
        }
        return {
          n: position.juror_id || index + 1,
          name: position.name || `Juror ${position.juror_id || index + 1}`,
          trait: [position.occupation, position.persona].filter(Boolean).join(" · ") || "Deliberation",
          stance: stance,
          quote: position.quote || position.bias || "",
        };
      })
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
  const sjBurdenMet = sjr.burden_met_votes ?? sjr.guilty_votes ?? null;
  const burdenMet = snapshot.guilty_or_liable_count ?? sjBurdenMet;
  const sjBurdenNot = sjr.burden_not_met_votes ?? (sjBurdenMet !== null ? Math.max(total - sjBurdenMet, 0) : null);
  const burdenNotMet = snapshot.not_guilty_or_not_liable_count ?? sjBurdenNot;
  const undecided = snapshot.undecided_count ?? (total && burdenMet !== null ? 0 : 0);
  const status = snapshot.verdict
    ? `${snapshot.type === "bench" ? "Bench verdict" : "Jury status"}: ${snapshot.verdict}`
    : sjr.total_juries ? `Shadow jury: ${sjBurdenMet} of ${sjr.total_juries} found burden met`
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
  const shadowNarrative = State.graphState?.shadow_jury_results?.narrative || [];
  const snapshotEntries = (snapshot.positions || []).map(position => ({
    agent: position.name || `Juror ${position.juror_id}`,
    phase: snapshot.type === "bench" ? "Bench Deliberation" : `Round ${snapshot.round || 1}`,
    text: `${position.quote || ""} Vote: ${position.stance || "Undecided"}.`,
  }));
  const entries = snapshotEntries.length ? snapshotEntries : State.transcriptEntries.filter(e =>
    /deliberation|shadow jury|jury instructions|verdict/i.test(e.phase || "") ||
    ((e.phase === "Jury Deliberation" || e.phase === "Deliberation") && e.agent !== "Judge" && e.agent !== "System")
  );
  // Fallback: show shadow jury narrative from graph state
  if (!entries.length && shadowNarrative.length) {
    el.innerHTML = shadowNarrative.map(s => {
      const agentName = s.name || "Shadow Juror";
      const color = AGENT_COLOR[agentName] || "var(--gold)";
      return `
        <div class="bubble" style="border-left-color:${color};margin-bottom:10px">
          <div class="speaker" style="color:${color}">${escapeHtml(agentName)} <span class="tag" style="background:rgba(0,0,0,0.06);color:${color}">Shadow Jury</span></div>
          ${escapeHtml(s.content || "")}
        </div>`;
    }).join("");
    return;
  }
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


export {
    buildLiveDeliberationSnapshot,
    renderShadowJuryConversation,
    renderVerdictView,
    renderVerdictCharts,
    renderJuryGrid,
    renderDeliberationView,
    renderConsensusRows,
    renderDeliberationTranscript,
    renderCaseRecordSummary,
    renderMiniChart,
    requestInsights,
    renderInsightResults,
    initInsightButtons,
    toggleInsightExpand
};
